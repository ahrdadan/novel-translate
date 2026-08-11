"""System prompt repository — CRUD for system_prompts table."""

from datetime import UTC, datetime

from src.database import get_db


async def create_prompt(
    name: str,
    prompt_text: str,
    is_default: bool = False,
) -> dict:
    db = await get_db()
    if is_default:
        await db.execute("UPDATE system_prompts SET is_default = 0")

    cursor = await db.execute(
        "INSERT INTO system_prompts (name, prompt_text, is_default) VALUES (?, ?, ?)",
        (name, prompt_text, 1 if is_default else 0),
    )
    await db.commit()
    prompt = await get_prompt_by_id(cursor.lastrowid)
    return prompt  # type: ignore


async def get_prompt_by_id(prompt_id: int) -> dict | None:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM system_prompts WHERE id = ?", (prompt_id,))
    row = await cursor.fetchone()
    return dict(row) if row else None


async def get_prompt_by_name(name: str) -> dict | None:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM system_prompts WHERE name = ?", (name,))
    row = await cursor.fetchone()
    return dict(row) if row else None


async def get_default_prompt() -> dict | None:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM system_prompts WHERE is_default = 1 LIMIT 1")
    row = await cursor.fetchone()
    if row:
        return dict(row)
    # Fallback to id=1 or first available
    cursor = await db.execute("SELECT * FROM system_prompts ORDER BY id ASC LIMIT 1")
    row = await cursor.fetchone()
    return dict(row) if row else None


async def get_all_prompts() -> list[dict]:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM system_prompts ORDER BY id ASC")
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def update_prompt(prompt_id: int, updates: dict) -> dict | None:
    db = await get_db()
    if updates.get("is_default"):
        await db.execute("UPDATE system_prompts SET is_default = 0")

    sets = []
    vals = []
    for k, v in updates.items():
        if v is not None:
            if k == "is_default":
                v = 1 if v else 0
            sets.append(f"{k} = ?")
            vals.append(v)

    if not sets:
        return await get_prompt_by_id(prompt_id)

    sets.append("updated_at = ?")
    vals.append(datetime.now(UTC).isoformat())
    vals.append(prompt_id)

    await db.execute(
        f"UPDATE system_prompts SET {', '.join(sets)} WHERE id = ?",
        vals,
    )
    await db.commit()
    return await get_prompt_by_id(prompt_id)


async def delete_prompt(prompt_id: int) -> bool:
    db = await get_db()
    cursor = await db.execute("DELETE FROM system_prompts WHERE id = ?", (prompt_id,))
    await db.commit()
    return cursor.rowcount > 0


async def set_default_prompt(prompt_id: int) -> dict | None:
    db = await get_db()
    await db.execute("UPDATE system_prompts SET is_default = 0")
    await db.execute(
        "UPDATE system_prompts SET is_default = 1, updated_at = ? WHERE id = ?",
        (datetime.now(UTC).isoformat(), prompt_id),
    )
    await db.commit()
    return await get_prompt_by_id(prompt_id)
