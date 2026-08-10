"""Model repository — CRUD for the models table."""

from datetime import UTC, datetime

from src.database import get_db


async def create_model(
    platform_id: int,
    name: str,
    url: str | None = None,
) -> dict:
    db = await get_db()
    cursor = await db.execute(
        "INSERT INTO models (platform_id, name, url) VALUES (?, ?, ?)",
        (platform_id, name, url),
    )
    await db.commit()
    return await get_model_by_id(cursor.lastrowid)


async def get_model_by_id(model_id: int) -> dict | None:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM models WHERE id = ?", (model_id,))
    row = await cursor.fetchone()
    return dict(row) if row else None


async def get_model_detail(model_id: int) -> dict | None:
    """Get model with platform info (for flat /models endpoint)."""
    db = await get_db()
    cursor = await db.execute(
        """
        SELECT m.*, p.name AS platform_name, p.api_type AS platform_api_type
        FROM models m
        JOIN platforms p ON m.platform_id = p.id
        WHERE m.id = ?
        """,
        (model_id,),
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def get_model_by_platform_and_name(platform_id: int, name: str) -> dict | None:
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM models WHERE platform_id = ? AND name = ?",
        (platform_id, name),
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def get_models_by_platform(platform_id: int) -> list[dict]:
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM models WHERE platform_id = ? ORDER BY id",
        (platform_id,),
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_all_models() -> list[dict]:
    """Flat list of all models across all platforms."""
    db = await get_db()
    cursor = await db.execute(
        """
        SELECT m.*, p.name AS platform_name, p.api_type AS platform_api_type
        FROM models m
        JOIN platforms p ON m.platform_id = p.id
        ORDER BY m.id
        """
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def update_model(model_id: int, updates: dict) -> dict | None:
    db = await get_db()
    sets = []
    vals = []
    for k, v in updates.items():
        if v is not None:
            sets.append(f"{k} = ?")
            vals.append(v)
    if not sets:
        return await get_model_by_id(model_id)
    sets.append("updated_at = ?")
    vals.append(datetime.now(UTC).isoformat())
    vals.append(model_id)
    await db.execute(
        f"UPDATE models SET {', '.join(sets)} WHERE id = ?",
        vals,
    )
    await db.commit()
    return await get_model_by_id(model_id)


async def delete_model(model_id: int) -> bool:
    db = await get_db()
    cursor = await db.execute("DELETE FROM models WHERE id = ?", (model_id,))
    await db.commit()
    return cursor.rowcount > 0
