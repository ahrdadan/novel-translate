"""Platform repository — CRUD for the platforms table."""

from datetime import UTC, datetime

from src.database import get_db


async def create_platform(
    name: str,
    api_key: str | None = None,
    api_type: str = "chat-completions",
) -> dict:
    db = await get_db()
    cursor = await db.execute(
        "INSERT INTO platforms (name, api_key, api_type) VALUES (?, ?, ?)",
        (name, api_key, api_type),
    )
    await db.commit()
    return await get_platform_by_id(cursor.lastrowid)


async def get_platform_by_id(platform_id: int) -> dict | None:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM platforms WHERE id = ?", (platform_id,))
    row = await cursor.fetchone()
    return dict(row) if row else None


async def get_platform_by_name(name: str) -> dict | None:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM platforms WHERE name = ?", (name,))
    row = await cursor.fetchone()
    return dict(row) if row else None


async def get_all_platforms() -> list[dict]:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM platforms ORDER BY id")
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def update_platform(platform_id: int, updates: dict) -> dict | None:
    db = await get_db()
    sets = []
    vals = []
    for k, v in updates.items():
        if v is not None:
            sets.append(f"{k} = ?")
            vals.append(v)
    if not sets:
        return await get_platform_by_id(platform_id)
    sets.append("updated_at = ?")
    vals.append(datetime.now(UTC).isoformat())
    vals.append(platform_id)
    await db.execute(
        f"UPDATE platforms SET {', '.join(sets)} WHERE id = ?",
        vals,
    )
    await db.commit()
    return await get_platform_by_id(platform_id)


async def delete_platform(platform_id: int) -> bool:
    db = await get_db()
    cursor = await db.execute("DELETE FROM platforms WHERE id = ?", (platform_id,))
    await db.commit()
    return cursor.rowcount > 0
