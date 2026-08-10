"""Chapter repository — CRUD for the chapters table."""

from datetime import UTC, datetime

from src.database import get_db


async def create_chapter(data: dict) -> dict:
    db = await get_db()
    cols = list(data.keys())
    placeholders = ", ".join(["?"] * len(cols))
    col_names = ", ".join(cols)
    cursor = await db.execute(
        f"INSERT INTO chapters ({col_names}) VALUES ({placeholders})",
        list(data.values()),
    )
    await db.commit()
    return await get_chapter_by_id(cursor.lastrowid)


async def get_chapter_by_id(chapter_id: int) -> dict | None:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM chapters WHERE id = ?", (chapter_id,))
    row = await cursor.fetchone()
    return dict(row) if row else None


async def get_chapter(series_id: int, chapter_number: int) -> dict | None:
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM chapters WHERE series_id = ? AND chapter_number = ?",
        (series_id, chapter_number),
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def get_chapters_by_series(series_id: int) -> list[dict]:
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM chapters WHERE series_id = ? ORDER BY chapter_number",
        (series_id,),
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def update_chapter(chapter_id: int, updates: dict) -> dict | None:
    db = await get_db()
    sets = []
    vals = []
    for k, v in updates.items():
        sets.append(f"{k} = ?")
        vals.append(v)
    if not sets:
        return await get_chapter_by_id(chapter_id)
    sets.append("updated_at = ?")
    vals.append(datetime.now(UTC).isoformat())
    vals.append(chapter_id)
    await db.execute(
        f"UPDATE chapters SET {', '.join(sets)} WHERE id = ?",
        vals,
    )
    await db.commit()
    return await get_chapter_by_id(chapter_id)


async def delete_chapter(chapter_id: int) -> bool:
    db = await get_db()
    cursor = await db.execute("DELETE FROM chapters WHERE id = ?", (chapter_id,))
    await db.commit()
    return cursor.rowcount > 0


async def get_previous_chapter_summary(series_id: int, chapter_number: int) -> str | None:
    """Get the chapter_summary of the previous chapter for context."""
    db = await get_db()
    cursor = await db.execute(
        """
        SELECT chapter_summary FROM chapters
        WHERE series_id = ? AND chapter_number < ? AND chapter_summary IS NOT NULL
        ORDER BY chapter_number DESC LIMIT 1
        """,
        (series_id, chapter_number),
    )
    row = await cursor.fetchone()
    return row["chapter_summary"] if row else None
