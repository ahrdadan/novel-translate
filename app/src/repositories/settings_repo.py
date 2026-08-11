"""Settings repository — single-row global configuration."""

from datetime import UTC, datetime

from src.database import get_db


async def get_settings() -> dict:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM settings WHERE id = 1")
    row = await cursor.fetchone()
    return dict(row) if row else {"id": 1, "max_concurrent_jobs": 1}


async def update_settings(updates: dict) -> dict:
    db = await get_db()
    sets = []
    vals = []
    for k, v in updates.items():
        if v is not None:
            sets.append(f"{k} = ?")
            vals.append(v)
    if not sets:
        return await get_settings()
    sets.append("updated_at = ?")
    vals.append(datetime.now(UTC).isoformat())
    await db.execute(
        f"UPDATE settings SET {', '.join(sets)} WHERE id = 1",
        vals,
    )
    await db.commit()
    return await get_settings()
