"""Router for database snapshot export and restore operations."""

import json
import logging
import os
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import UTC, datetime
from typing import Any

import aiosqlite
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse

from src.database import DATABASE_PATH, get_db
from src.services import job_worker

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/snapshots", tags=["Snapshots"])

TABLES_IN_ORDER = [
    "system_prompts",
    "platforms",
    "models",
    "settings",
    "series",
    "glossary_terms",
    "characters",
    "chapters",
    "jobs",
]


def _cleanup_file(path: str) -> None:
    """Remove a temporary file or directory after download/processing."""
    try:
        if os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=True)
        elif os.path.exists(path):
            os.remove(path)
    except Exception as e:  # noqa: BLE001
        logger.warning("Failed to clean up temp path %s: %s", path, e)



@router.get("/info")
async def get_snapshot_info(db: aiosqlite.Connection = Depends(get_db)) -> dict[str, Any]:  # noqa: B008
    """Get database file information and row counts for all tables."""
    table_counts = {}
    for table in TABLES_IN_ORDER:
        try:
            cursor = await db.execute(f"SELECT COUNT(*) FROM {table}")
            row = await cursor.fetchone()
            table_counts[table] = row[0] if row else 0
        except sqlite3.Error:
            table_counts[table] = 0

    db_size = DATABASE_PATH.stat().st_size if DATABASE_PATH.exists() else 0
    last_modified = (
        datetime.fromtimestamp(DATABASE_PATH.stat().st_mtime, tz=UTC).isoformat()
        if DATABASE_PATH.exists()
        else None
    )

    return {
        "database_file": str(DATABASE_PATH.name),
        "database_size_bytes": db_size,
        "database_size_human": f"{db_size / (1024 * 1024):.2f} MB" if db_size > 0 else "0.00 MB",
        "last_modified": last_modified,
        "tables": table_counts,
    }


@router.get("/export")
async def export_snapshot(
    background_tasks: BackgroundTasks,
    format: str = Query("zip", enum=["zip", "json"], description="Export format: zip or json"),
    db: aiosqlite.Connection = Depends(get_db),  # noqa: B008
):
    """Export database snapshot as a downloadable ZIP archive or JSON file."""
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    temp_dir = tempfile.mkdtemp(prefix="snapshot_export_")

    if format == "zip":
        backup_db_path = os.path.join(temp_dir, "novel_trans.db")
        # Perform safe online backup using SQLite backup API
        async with aiosqlite.connect(backup_db_path) as backup_db:
            await db.backup(backup_db)

        # Collect table stats for manifest
        manifest_data = {
            "created_at": datetime.now(UTC).isoformat(),
            "app": "Novel Translation API",
            "version": "1.0.0",
            "format": "zip",
            "tables": {},
        }
        for table in TABLES_IN_ORDER:
            cursor = await db.execute(f"SELECT COUNT(*) FROM {table}")
            row = await cursor.fetchone()
            manifest_data["tables"][table] = row[0] if row else 0

        manifest_path = os.path.join(temp_dir, "manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as f:  # noqa: ASYNC230
            json.dump(manifest_data, f, indent=2)

        zip_filename = f"snapshot_{timestamp}.zip"
        zip_path = os.path.join(temp_dir, zip_filename)

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(backup_db_path, arcname="novel_trans.db")
            zipf.write(manifest_path, arcname="manifest.json")

        background_tasks.add_task(_cleanup_file, temp_dir)
        return FileResponse(
            path=zip_path,
            filename=zip_filename,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{zip_filename}"'},
        )

    else:  # format == "json"
        export_data: dict[str, Any] = {
            "created_at": datetime.now(UTC).isoformat(),
            "app": "Novel Translation API",
            "version": "1.0.0",
            "tables": {},
        }

        for table in TABLES_IN_ORDER:
            cursor = await db.execute(f"SELECT * FROM {table}")
            rows = await cursor.fetchall()
            export_data["tables"][table] = [dict(row) for row in rows]

        json_filename = f"snapshot_{timestamp}.json"
        json_path = os.path.join(temp_dir, json_filename)
        with open(json_path, "w", encoding="utf-8") as f:  # noqa: ASYNC230
            json.dump(export_data, f, indent=2, ensure_ascii=False)

        background_tasks.add_task(_cleanup_file, temp_dir)
        return FileResponse(
            path=json_path,
            filename=json_filename,
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{json_filename}"'},
        )


@router.post("/restore")
async def restore_snapshot(
    file: UploadFile = File(...),  # noqa: B008
    db: aiosqlite.Connection = Depends(get_db),  # noqa: B008
):
    """Restore database from an uploaded ZIP archive or JSON snapshot file."""
    filename = file.filename or ""
    temp_dir = tempfile.mkdtemp(prefix="snapshot_restore_")

    try:
        upload_path = os.path.join(temp_dir, filename)
        with open(upload_path, "wb") as buffer:  # noqa: ASYNC230
            shutil.copyfileobj(file.file, buffer)

        restored_counts: dict[str, int] = {}

        if filename.endswith(".zip") or zipfile.is_zipfile(upload_path):
            with zipfile.ZipFile(upload_path, "r") as zipf:
                zipf.extractall(temp_dir)

            extracted_db = os.path.join(temp_dir, "novel_trans.db")
            if not os.path.exists(extracted_db):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid snapshot ZIP: 'novel_trans.db' not found in archive.",
                )

            # Read table counts and restore online using SQLite backup API
            async with aiosqlite.connect(extracted_db) as temp_conn:
                # CLEANUP: Remove stuck jobs from the snapshot so they don't resume after restore
                await temp_conn.execute("DELETE FROM jobs WHERE status IN ('processing', 'queued')")
                await temp_conn.execute("UPDATE chapters SET status = 'failed' WHERE status NOT IN ('completed', 'translated')")
                await temp_conn.commit()

                for table in TABLES_IN_ORDER:
                    try:
                        cursor = await temp_conn.execute(f"SELECT COUNT(*) FROM {table}")
                        row = await cursor.fetchone()
                        restored_counts[table] = row[0] if row else 0
                    except sqlite3.Error:
                        restored_counts[table] = 0

                # Abort any running tasks in the current live instance
                job_worker.abort_all_running_jobs()

                # Perform safe online restore
                await temp_conn.backup(db)

                # Apply schema migrations to upgrade older snapshots to current schema
                from src.database import _apply_migrations
                await _apply_migrations(db)

        elif filename.endswith(".json"):
            with open(upload_path, "r", encoding="utf-8") as f:  # noqa: ASYNC230
                json_data = json.load(f)

            if "tables" not in json_data or not isinstance(json_data["tables"], dict):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid snapshot JSON: 'tables' key missing or invalid.",
                )

            tables_data = json_data["tables"]

            # Disable foreign keys during restore
            await db.execute("PRAGMA foreign_keys = OFF")
            try:
                # Abort any running tasks in the current live instance
                job_worker.abort_all_running_jobs()

                # Truncate tables in reverse dependency order
                for table in reversed(TABLES_IN_ORDER):
                    await db.execute(f"DELETE FROM {table}")

                # Insert data
                for table in TABLES_IN_ORDER:
                    rows = tables_data.get(table, [])
                    if not rows:
                        restored_counts[table] = 0
                        continue

                    # CLEANUP: Remove stuck jobs from snapshot data
                    if table == "jobs":
                        rows = [r for r in rows if r.get("status") not in ("processing", "queued")]
                        if not rows:
                            restored_counts[table] = 0
                            continue
                    elif table == "chapters":
                        for row in rows:
                            if row.get("status") not in ("completed", "translated"):
                                row["status"] = "failed"

                    columns = list(rows[0].keys())
                    placeholders = ", ".join(["?"] * len(columns))
                    cols_str = ", ".join(columns)
                    sql = f"INSERT INTO {table} ({cols_str}) VALUES ({placeholders})"

                    for row in rows:
                        values = [row[col] for col in columns]
                        await db.execute(sql, values)

                    restored_counts[table] = len(rows)

                await db.commit()

                # Apply schema migrations to upgrade older snapshots to current schema
                from src.database import _apply_migrations
                await _apply_migrations(db)
            finally:
                await db.execute("PRAGMA foreign_keys = ON")

        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported file format. Please upload a .zip or .json snapshot.",
            )

        return {
            "status": "success",
            "message": "Snapshot database restored successfully.",
            "restored_at": datetime.now(UTC).isoformat(),
            "file_restored": filename,
            "restored_tables": restored_counts,
        }

    finally:
        _cleanup_file(temp_dir)

