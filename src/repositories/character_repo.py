"""Character repository — CRUD for the characters table."""

from src.database import get_db


async def create_character(series_id: int, data: dict) -> dict:
    db = await get_db()
    cursor = await db.execute(
        """INSERT INTO characters (series_id, name, translated_name, gender, speech_style, notes)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            series_id,
            data["name"],
            data.get("translated_name"),
            data.get("gender"),
            data.get("speech_style"),
            data.get("notes"),
        ),
    )
    await db.commit()
    return await get_character_by_id(cursor.lastrowid)


async def get_character_by_id(char_id: int) -> dict | None:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM characters WHERE id = ?", (char_id,))
    row = await cursor.fetchone()
    return dict(row) if row else None


async def get_characters_by_series(series_id: int) -> list[dict]:
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM characters WHERE series_id = ? ORDER BY id",
        (series_id,),
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def update_character(char_id: int, updates: dict) -> dict | None:
    db = await get_db()
    sets = []
    vals = []
    for k, v in updates.items():
        if v is not None:
            sets.append(f"{k} = ?")
            vals.append(v)
    if not sets:
        return await get_character_by_id(char_id)
    vals.append(char_id)
    await db.execute(
        f"UPDATE characters SET {', '.join(sets)} WHERE id = ?",
        vals,
    )
    await db.commit()
    return await get_character_by_id(char_id)


async def delete_character(char_id: int) -> bool:
    db = await get_db()
    cursor = await db.execute("DELETE FROM characters WHERE id = ?", (char_id,))
    await db.commit()
    return cursor.rowcount > 0


async def upsert_character(series_id: int, name: str, **kwargs) -> dict:
    """Insert or update a character (used by extractor)."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM characters WHERE series_id = ? AND name = ?",
        (series_id, name),
    )
    existing = await cursor.fetchone()
    if existing:
        return await update_character(existing["id"], kwargs)
    return await create_character(series_id, {"name": name, **kwargs})
