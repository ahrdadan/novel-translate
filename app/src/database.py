"""Database connection and schema initialization (SQLite + aiosqlite)."""

from pathlib import Path

import aiosqlite

DATABASE_PATH = Path(__file__).parent.parent / "data" / "novel_trans.db"

_db: aiosqlite.Connection | None = None


async def get_db() -> aiosqlite.Connection:
    """Return the singleton database connection."""
    if _db is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _db



async def init_db() -> None:
    """Open the database and create all tables/indexes if they don't exist."""
    global _db

    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

    _db = await aiosqlite.connect(str(DATABASE_PATH))
    _db.row_factory = aiosqlite.Row

    await _db.execute("PRAGMA journal_mode = WAL")
    await _db.execute("PRAGMA foreign_keys = ON")

    await _db.executescript(_SCHEMA_SQL)
    await _apply_migrations(_db)
    await _db.execute(f"INSERT OR IGNORE INTO system_prompts (id, name, prompt_text, is_default) VALUES (1, 'default', '{_DEFAULT_PROMPT_TEXT.replace("'", "''")}', 1)")
    await _db.execute("INSERT OR IGNORE INTO settings (id, max_concurrent_jobs, default_system_prompt_id) VALUES (1, 3, 1)")
    await _db.commit()


async def _apply_migrations(db: aiosqlite.Connection) -> None:
    """Apply schema migrations for new columns if database already exists."""
    # Check settings columns
    cursor = await db.execute("PRAGMA table_info(settings)")
    settings_cols = [r["name"] for r in await cursor.fetchall()]
    if settings_cols and "default_system_prompt_id" not in settings_cols:
        await db.execute("ALTER TABLE settings ADD COLUMN default_system_prompt_id INTEGER REFERENCES system_prompts(id)")
    if settings_cols and "is_paused" not in settings_cols:
        await db.execute("ALTER TABLE settings ADD COLUMN is_paused INTEGER DEFAULT 0")
    if settings_cols and "allow_concurrent_different_models" not in settings_cols:
        await db.execute("ALTER TABLE settings ADD COLUMN allow_concurrent_different_models INTEGER DEFAULT 0")

    # Check series columns
    cursor = await db.execute("PRAGMA table_info(series)")
    series_cols = [r["name"] for r in await cursor.fetchall()]
    if series_cols and "system_prompt_id" not in series_cols:
        await db.execute("ALTER TABLE series ADD COLUMN system_prompt_id INTEGER REFERENCES system_prompts(id)")

    # Check jobs columns
    cursor = await db.execute("PRAGMA table_info(jobs)")
    jobs_cols = [r["name"] for r in await cursor.fetchall()]
    if jobs_cols and "system_prompt_ref" not in jobs_cols:
        await db.execute("ALTER TABLE jobs ADD COLUMN system_prompt_ref TEXT")
    if jobs_cols and "strategy" not in jobs_cols:
        await db.execute("ALTER TABLE jobs ADD COLUMN strategy TEXT DEFAULT 'pipeline'")
    if jobs_cols and "extract" not in jobs_cols:
        await db.execute("ALTER TABLE jobs ADD COLUMN extract INTEGER DEFAULT 1")

    # Check chapters columns
    cursor = await db.execute("PRAGMA table_info(chapters)")
    chapters_cols = [r["name"] for r in await cursor.fetchall()]
    if chapters_cols and "error" not in chapters_cols:
        await db.execute("ALTER TABLE chapters ADD COLUMN error TEXT")



async def close_db() -> None:
    """Close the database connection."""
    global _db
    if _db is not None:
        await _db.close()
        _db = None


# ---------------------------------------------------------------------------
# Full DDL from PRD v2 §2 + System Prompts
# ---------------------------------------------------------------------------
_DEFAULT_PROMPT_TEXT = """You are a professional literary translator specializing in novel translation, writing with the sensibility of a native Indonesian author.

Rules:
- Translate naturally and idiomatically into fluent, contemporary Indonesian — avoid stiff, literal, or overly wordy "translated" phrasing.
- Preserve the author's voice: writing style, tone, register, and atmosphere.
- Do NOT summarize, shorten, paraphrase away detail, add explanations, or remove information.
- Keep each character's distinct voice and speech register consistent through diction and sentence structure, NOT through pronoun switching.
- Use "aku" as the default first-person pronoun, including its natural contracted forms ("kudengar", "kutahu"), and "kau"/"kamu" as the default second-person pronoun. Use "saya"/"Anda" only in clearly formal contexts. NEVER use slang/informal pronouns such as "gue", "gw", "lu", "elu", "situ".
- Keep dialogue formatting, punctuation style, and paragraph breaks exactly as in the original.
- Keep proper nouns entirely UNCHANGED (names, locations, organizations, factions).
- Do NOT translate honorifics, titles, cultivation stages, or martial arts/magic techniques. Keep them in English (e.g., "Young Master", "Senior Brother", "Duke", "Fireball") or in Romanized/Latin format if translating directly from Japanese/Korean/Chinese.
- Localize interjections, curses, and onomatopoeia naturally, matching the original's intensity.
- Do not censor explicit, violent, or sensitive content.
- Make dialogue and internal monologue sound like something an Indonesian speaker would actually say/think.
- Preserve any HTML tags or Markdown formatting (e.g. *italics*, **bold**) exactly in the output, correctly positioned.
- Output ONLY the translated text corresponding to "CURRENT TEXT TO TRANSLATE", formatted as valid markdown — no explanations, notes, or commentary."""

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS system_prompts (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    prompt_text TEXT NOT NULL,
    is_default INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS platforms (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    api_key TEXT,
    api_type TEXT NOT NULL DEFAULT 'chat-completions',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS models (
    id INTEGER PRIMARY KEY,
    platform_id INTEGER NOT NULL REFERENCES platforms(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(platform_id, name)
);

CREATE TABLE IF NOT EXISTS settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    max_concurrent_jobs INTEGER NOT NULL DEFAULT 3,
    default_translation_model_id INTEGER REFERENCES models(id),
    default_extraction_model_id INTEGER REFERENCES models(id),
    default_system_prompt_id INTEGER REFERENCES system_prompts(id) DEFAULT 1,
    is_paused INTEGER DEFAULT 0,
    allow_concurrent_different_models INTEGER DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE IF NOT EXISTS series (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    original_title TEXT,
    author TEXT,
    title_alts TEXT,
    description TEXT,
    status TEXT DEFAULT 'ongoing',
    summary TEXT DEFAULT '',
    translation_model_id INTEGER REFERENCES models(id),
    extraction_model_id INTEGER REFERENCES models(id),
    system_prompt_id INTEGER REFERENCES system_prompts(id),
    last_translated_chapter INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS glossary_terms (
    id INTEGER PRIMARY KEY,
    series_id INTEGER NOT NULL REFERENCES series(id) ON DELETE CASCADE,
    term_source TEXT NOT NULL,
    term_translation TEXT NOT NULL,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(series_id, term_source)
);

CREATE TABLE IF NOT EXISTS characters (
    id INTEGER PRIMARY KEY,
    series_id INTEGER NOT NULL REFERENCES series(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    translated_name TEXT,
    gender TEXT,
    speech_style TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(series_id, name)
);

CREATE TABLE IF NOT EXISTS chapters (
    id INTEGER PRIMARY KEY,
    series_id INTEGER NOT NULL REFERENCES series(id) ON DELETE CASCADE,
    chapter_number INTEGER NOT NULL,
    title TEXT,
    source_text TEXT NOT NULL,
    source_language TEXT,
    translated_text TEXT,
    chapter_summary TEXT,
    status TEXT DEFAULT 'pending',
    error TEXT,
    extract_status TEXT DEFAULT 'pending',
    translated_by_model_id INTEGER REFERENCES models(id),
    translated_by_model_name TEXT,
    translated_by_platform_name TEXT,
    extracted_by_model_id INTEGER REFERENCES models(id),
    extracted_by_model_name TEXT,
    translated_at TIMESTAMP,
    extracted_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(series_id, chapter_number)
);

CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY,
    series_id INTEGER NOT NULL REFERENCES series(id) ON DELETE CASCADE,
    chapter_number INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    force_translate INTEGER DEFAULT 0,
    force_summary INTEGER DEFAULT 0,
    extract INTEGER DEFAULT 1,
    translation_model_ref TEXT,
    extraction_model_ref TEXT,
    system_prompt_ref TEXT,
    strategy TEXT DEFAULT 'pipeline',
    result TEXT,
    error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_chapters_status ON chapters(status);
CREATE INDEX IF NOT EXISTS idx_chapters_series ON chapters(series_id, chapter_number);
CREATE INDEX IF NOT EXISTS idx_glossary_series ON glossary_terms(series_id);
CREATE INDEX IF NOT EXISTS idx_characters_series ON characters(series_id);
CREATE INDEX IF NOT EXISTS idx_models_platform ON models(platform_id);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_series ON jobs(series_id, chapter_number);
"""

