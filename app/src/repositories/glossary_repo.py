"""Glossary repository — CRUD for glossary_terms table."""

from src.database import get_db


async def create_term(series_id: int, data: dict) -> dict:
    db = await get_db()
    cursor = await db.execute(
        "INSERT INTO glossary_terms (series_id, term_source, term_translation, notes) VALUES (?, ?, ?, ?)",
        (series_id, data["term_source"], data["term_translation"], data.get("notes")),
    )
    await db.commit()
    return await get_term_by_id(cursor.lastrowid)


async def get_term_by_id(term_id: int) -> dict | None:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM glossary_terms WHERE id = ?", (term_id,))
    row = await cursor.fetchone()
    return dict(row) if row else None


async def get_terms_by_series(series_id: int) -> list[dict]:
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM glossary_terms WHERE series_id = ? ORDER BY id",
        (series_id,),
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def update_term(term_id: int, updates: dict) -> dict | None:
    db = await get_db()
    sets = []
    vals = []
    for k, v in updates.items():
        if v is not None:
            sets.append(f"{k} = ?")
            vals.append(v)
    if not sets:
        return await get_term_by_id(term_id)
    vals.append(term_id)
    await db.execute(
        f"UPDATE glossary_terms SET {', '.join(sets)} WHERE id = ?",
        vals,
    )
    await db.commit()
    return await get_term_by_id(term_id)


async def delete_term(term_id: int) -> bool:
    db = await get_db()
    cursor = await db.execute("DELETE FROM glossary_terms WHERE id = ?", (term_id,))
    await db.commit()
    return cursor.rowcount > 0


async def upsert_term(series_id: int, term_source: str, term_translation: str, notes: str | None = None) -> dict:
    """Insert or update a glossary term (used by extractor)."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM glossary_terms WHERE series_id = ? AND term_source = ?",
        (series_id, term_source),
    )
    existing = await cursor.fetchone()
    if existing:
        return await update_term(existing["id"], {"term_translation": term_translation, "notes": notes})
    return await create_term(series_id, {"term_source": term_source, "term_translation": term_translation, "notes": notes})
