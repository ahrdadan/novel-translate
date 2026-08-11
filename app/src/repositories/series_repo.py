"""Series repository — CRUD for the series table."""

from datetime import UTC, datetime

from src.database import get_db


async def create_series(data: dict) -> dict:
    db = await get_db()
    cols = list(data.keys())
    placeholders = ", ".join(["?"] * len(cols))
    col_names = ", ".join(cols)
    cursor = await db.execute(
        f"INSERT INTO series ({col_names}) VALUES ({placeholders})",
        list(data.values()),
    )
    await db.commit()
    return await get_series_by_id(cursor.lastrowid)


async def get_series_by_id(series_id: int) -> dict | None:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM series WHERE id = ?", (series_id,))
    row = await cursor.fetchone()
    return dict(row) if row else None


async def get_series_by_name(name: str) -> dict | None:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM series WHERE name = ?", (name,))
    row = await cursor.fetchone()
    return dict(row) if row else None



async def get_all_series() -> list[dict]:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM series ORDER BY id")
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def update_series(series_id: int, updates: dict) -> dict | None:
    db = await get_db()
    sets = []
    vals = []
    for k, v in updates.items():
        if v is not None:
            sets.append(f"{k} = ?")
            vals.append(v)
    if not sets:
        return await get_series_by_id(series_id)
    sets.append("updated_at = ?")
    vals.append(datetime.now(UTC).isoformat())
    vals.append(series_id)
    await db.execute(
        f"UPDATE series SET {', '.join(sets)} WHERE id = ?",
        vals,
    )
    await db.commit()
    return await get_series_by_id(series_id)


async def delete_series(series_id: int) -> bool:
    db = await get_db()
    cursor = await db.execute("DELETE FROM series WHERE id = ?", (series_id,))
    await db.commit()
    return cursor.rowcount > 0


async def get_series_status(series_id: int) -> dict | None:
    """Get series with chapter count stats."""
    db = await get_db()
    series = await get_series_by_id(series_id)
    if not series:
        return None

    cursor = await db.execute(
        "SELECT COUNT(*) as total FROM chapters WHERE series_id = ?", (series_id,)
    )
    total = (await cursor.fetchone())["total"]

    cursor = await db.execute(
        "SELECT COUNT(*) as c FROM chapters WHERE series_id = ? AND status = 'translated'",
        (series_id,),
    )
    translated = (await cursor.fetchone())["c"]

    cursor = await db.execute(
        "SELECT COUNT(*) as c FROM chapters WHERE series_id = ? AND status = 'pending'",
        (series_id,),
    )
    pending = (await cursor.fetchone())["c"]

    cursor = await db.execute(
        "SELECT COUNT(*) as c FROM chapters WHERE series_id = ? AND status = 'failed'",
        (series_id,),
    )
    failed = (await cursor.fetchone())["c"]

    return {
        "id": series["id"],
        "name": series["name"],
        "status": series["status"],
        "last_translated_chapter": series["last_translated_chapter"],
        "total_chapters": total,
        "translated_chapters": translated,
        "pending_chapters": pending,
        "failed_chapters": failed,
    }
