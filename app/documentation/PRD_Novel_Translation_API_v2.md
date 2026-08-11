# PRD v2: AI Novel Translation API (FastAPI + SQLite, Job Queue, Multi-Platform Model)

> Dokumen ini menggantikan/meng-update PRD v1 pada bagian: model config (jadi Platform + Model), job queue (async translate), dan settings. Bagian yang tidak disebut ulang di sini (system prompts, html_parser, extraction flow inti) tetap berlaku dari v1.

## 1. Ringkasan Perubahan dari v1

| Aspek | v1 | v2 |
|---|---|---|
| Model config | 1 tabel flat `model_configs` (purpose melekat per model) | 2 tabel: `platforms` (kredensial) → `models` (anak, banyak model per platform). Satu model bisa dipakai untuk translate ATAU extract, ditentukan saat request. |
| Default model | flag `is_global_default` di tabel model | dipindah ke tabel `settings` (`default_translation_model_id`, `default_extraction_model_id`) |
| API format | asumsi OpenAI chat-completions saja | dukung `chat-completions`, `responses`, `messages` (Anthropic-style), fallback ke `chat-completions` |
| Translate single chapter | selalu synchronous | 2 mode: `sync` (blocking, hasil langsung) dan `async` (return job, polling) |
| Translate batch | endpoint batch dengan range/list | **dihapus**. Client loop manual per chapter, tiap request bisa `async` sehingga backend tetap jalan paralel (maks. dikonfigurasi) tanpa client menunggu |
| Job queue | tidak ada | tabel `jobs` + in-process semaphore (maks N job berjalan bersamaan, dikonfigurasi lewat `/settings`) + **worker loop saat startup** yang scan job `queued`/`processing` untuk resume setelah server restart |
| Model custom saat request | tidak ada | bisa kirim `model_id` (referensi) ATAU definisi inline platform+model baru (create-or-append, dengan overwrite parsial kalau field dikirim ulang) |

## 2. Skema Database (Final)

```sql
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- =========================================================
-- PLATFORMS (kredensial + tipe API, induk dari models)
-- =========================================================
CREATE TABLE platforms (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,             -- misal "aihubmix", "openai"
    api_key TEXT,                          -- plain text
    api_type TEXT NOT NULL DEFAULT 'chat-completions',  -- chat-completions | responses | messages
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =========================================================
-- MODELS (anak dari platform, banyak model per platform)
-- =========================================================
CREATE TABLE models (
    id INTEGER PRIMARY KEY,
    platform_id INTEGER NOT NULL REFERENCES platforms(id) ON DELETE CASCADE,
    name TEXT NOT NULL,                    -- misal "gpt-5.5-free"
    url TEXT,                              -- base_url khusus model ini (opsional, override platform kalau perlu)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(platform_id, name)
);

-- =========================================================
-- SETTINGS (single row, konfigurasi global backend)
-- =========================================================
CREATE TABLE settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),   -- dipaksa hanya 1 baris
    max_concurrent_jobs INTEGER NOT NULL DEFAULT 3,
    default_translation_model_id INTEGER REFERENCES models(id),
    default_extraction_model_id INTEGER REFERENCES models(id),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
INSERT INTO settings (id, max_concurrent_jobs) VALUES (1, 3);

-- =========================================================
-- SERIES
-- =========================================================
CREATE TABLE series (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    original_title TEXT,
    author TEXT,
    title_alts TEXT,                        -- JSON array string
    description TEXT,
    status TEXT DEFAULT 'ongoing',          -- ongoing | completed | dropped
    summary TEXT DEFAULT '',                -- manual, diedit user
    translation_model_id INTEGER REFERENCES models(id),  -- override default settings, per series
    extraction_model_id INTEGER REFERENCES models(id),   -- override default settings, per series
    last_translated_chapter INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =========================================================
-- GLOSSARY
-- =========================================================
CREATE TABLE glossary_terms (
    id INTEGER PRIMARY KEY,
    series_id INTEGER NOT NULL REFERENCES series(id) ON DELETE CASCADE,
    term_source TEXT NOT NULL,
    term_translation TEXT NOT NULL,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(series_id, term_source)
);

-- =========================================================
-- CHARACTERS
-- =========================================================
CREATE TABLE characters (
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

-- =========================================================
-- CHAPTERS
-- =========================================================
CREATE TABLE chapters (
    id INTEGER PRIMARY KEY,
    series_id INTEGER NOT NULL REFERENCES series(id) ON DELETE CASCADE,
    chapter_number INTEGER NOT NULL,
    title TEXT,

    source_text TEXT NOT NULL,
    source_language TEXT,                   -- "auto" saat create -> resolved jadi kode bahasa

    translated_text TEXT,
    chapter_summary TEXT,

    status TEXT DEFAULT 'pending',          -- pending | translated | failed
    extract_status TEXT DEFAULT 'pending',  -- pending | done | skipped | failed

    -- snapshot model yang benar-benar dipakai (audit trail)
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

-- =========================================================
-- JOBS (async translate tracking)
-- =========================================================
CREATE TABLE jobs (
    id INTEGER PRIMARY KEY,
    series_id INTEGER NOT NULL REFERENCES series(id) ON DELETE CASCADE,
    chapter_number INTEGER NOT NULL,

    status TEXT NOT NULL DEFAULT 'queued',  -- queued | processing | completed | failed

    -- parameter request yang disimpan supaya worker bisa jalankan/resume
    force_translate INTEGER DEFAULT 0,
    force_summary INTEGER DEFAULT 0,
    extract INTEGER DEFAULT 1,
    translation_model_ref TEXT,             -- JSON: {"model_id": 5} atau {"platform": {...}, "model": {...}}
    extraction_model_ref TEXT,

    result TEXT,                            -- JSON hasil lengkap (translated_text, chapter_summary, dll) saat completed
    error TEXT,                             -- pesan error saat failed

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE INDEX idx_chapters_status ON chapters(status);
CREATE INDEX idx_chapters_series ON chapters(series_id, chapter_number);
CREATE INDEX idx_glossary_series ON glossary_terms(series_id);
CREATE INDEX idx_characters_series ON characters(series_id);
CREATE INDEX idx_models_platform ON models(platform_id);
CREATE INDEX idx_jobs_status ON jobs(status);
CREATE INDEX idx_jobs_series ON jobs(series_id, chapter_number);
```

## 3. Model Resolution & Create-or-Append Logic

### 3.1 Bentuk Referensi Model di Request

```json
// Referensi model yang sudah ada
{ "model_id": 5 }

// Definisi inline (create-or-append)
{
  "platform": { "name": "aihubmix", "apiType": "chat-completions", "apiKey": "sk-..." },
  "model": { "name": "gpt-5.5-free", "url": "https://aihubmix.com" }
}
```

### 3.2 Urutan Resolusi (per request, per purpose: translation/extraction)

```
1. Field translation_model / extraction_model dikirim di body?
   a. Berisi "model_id" -> pakai model itu langsung (404 kalau tidak ditemukan)
   b. Berisi "platform" + "model" -> jalankan create-or-append logic (lihat 3.3)
2. Tidak dikirim sama sekali ->
   a. Cek series.translation_model_id / series.extraction_model_id (override per series)
   b. Kalau series juga tidak punya -> pakai settings.default_translation_model_id / default_extraction_model_id
   c. Kalau default juga kosong -> 400 error
```

### 3.3 Create-or-Append Logic (Platform + Model)

```python
def resolve_or_create_model(ref: dict, repo: PlatformModelRepo) -> Model:
    if "model_id" in ref:
        model = repo.get_model_by_id(ref["model_id"])
        if not model:
            raise HTTPException(404, f"Model {ref['model_id']} not found")
        return model

    platform_data = ref["platform"]
    model_data = ref["model"]

    platform = repo.get_platform_by_name(platform_data["name"])
    if platform:
        # overwrite HANYA field yang eksplisit dikirim ulang
        updates = {}
        if "apiKey" in platform_data:
            updates["api_key"] = platform_data["apiKey"]
        if "apiType" in platform_data:
            updates["api_type"] = platform_data["apiType"]
        if updates:
            repo.update_platform(platform.id, updates)
    else:
        platform = repo.create_platform(
            name=platform_data["name"],
            api_key=platform_data.get("apiKey"),
            api_type=platform_data.get("apiType", "chat-completions"),
        )

    model = repo.get_model_by_platform_and_name(platform.id, model_data["name"])
    if model:
        updates = {}
        if "url" in model_data:
            updates["url"] = model_data["url"]
        if updates:
            repo.update_model(model.id, updates)
    else:
        model = repo.create_model(
            platform_id=platform.id,
            name=model_data["name"],
            url=model_data.get("url"),
        )

    return model
```

Ringkasan aturan: platform/model yang sudah ada **tidak pernah hilang datanya** hanya karena dipanggil ulang tanpa field tertentu — hanya field yang **eksplisit dikirim** yang menimpa nilai lama.

## 4. API Type Adapter (chat-completions / responses / messages)

Karena satu platform bisa punya `api_type` berbeda, layer pemanggilan LLM perlu adapter:

```text
services/llm_adapters/
├── base.py                  # interface: async def call(system_prompt, user_prompt, model_name, base_url, api_key, max_tokens) -> str
├── chat_completions.py      # OpenAI-compatible /v1/chat/completions (fallback default)
├── responses.py             # OpenAI /v1/responses format
└── messages.py               # Anthropic-style /v1/messages format
```

```python
# services/llm_adapters/__init__.py
ADAPTERS = {
    "chat-completions": ChatCompletionsAdapter(),
    "responses": ResponsesAdapter(),
    "messages": MessagesAdapter(),
}

def get_adapter(api_type: str):
    return ADAPTERS.get(api_type, ADAPTERS["chat-completions"])  # fallback
```

Tiap adapter bertanggung jawab membentuk request sesuai format API-nya masing-masing dan mengembalikan teks output yang sudah dinormalisasi (string biasa) ke pemanggil (`translator.py` / `extractor.py`), sehingga logic di atasnya (sanitasi, parsing JSON extraction, dll dari v1) tidak perlu tahu perbedaan format API.

## 5. Job Queue Design

### 5.1 Konsep

- **In-process semaphore** membatasi jumlah job yang `processing` bersamaan sesuai `settings.max_concurrent_jobs`.
- Job baru selalu **langsung diterima** dan disimpan sebagai row di tabel `jobs` dengan `status='queued'` — request client **tidak pernah menunggu** slot kosong, backend yang mengatur kapan job itu benar-benar dieksekusi.
- **Worker loop** (dijalankan sebagai `asyncio` background task saat FastAPI startup) terus memantau tabel `jobs`: mengambil job `queued` berikutnya begitu ada slot semaphore kosong, mengeksekusinya, lalu update status.
- **Resume saat startup**: saat aplikasi restart, worker loop di `startup` event akan mengambil semua job yang statusnya masih `queued` **atau** `processing` (karena `processing` yang "nyangkut" akibat restart sebelumnya) dan memasukkannya kembali ke antrean eksekusi.

### 5.2 Alur

```
1. POST /chapters/{n}/translate dengan mode="async"
   -> simpan row di `jobs` (status='queued', simpan semua parameter request termasuk
      translation_model_ref/extraction_model_ref sebagai JSON string)
   -> return segera: {"job_id": 42, "status": "queued", "status_url": "/api/v1/jobs/42"}

2. Worker loop (berjalan terus di background sejak startup):
   while True:
       if semaphore_slot_available():
           job = get_next_queued_job()
           if job:
               asyncio.create_task(execute_job(job))  # slot terpakai sampai selesai
       await asyncio.sleep(1)

3. execute_job(job):
   - update status='processing', started_at=now
   - jalankan translate + extract (logic sama persis dengan mode sync, dari v1 §8.7)
   - resolve translation_model_ref / extraction_model_ref via resolve_or_create_model()
   - kalau sukses -> status='completed', result=json.dumps(full_chapter_result), completed_at=now
   - kalau gagal (setelah 3x retry internal) -> status='failed', error=pesan_error
   - lepas slot semaphore

4. Client polling: GET /jobs/{job_id}
   -> selama queued/processing: {"status": "queued", ...}
   -> saat completed: {"status": "completed", "result": {...hasil lengkap chapter...}}
   -> saat failed: {"status": "failed", "error": "..."}
```

### 5.3 Mode Sync vs Async

| | Sync | Async |
|---|---|---|
| Field | `"mode": "sync"` (default) | `"mode": "async"` |
| Ikut kuota `max_concurrent_jobs`? | **Tidak** — selalu langsung dieksekusi saat request diterima | **Ya** — masuk antrean, dieksekusi worker sesuai slot tersedia |
| Response | Hasil lengkap langsung (blocking) | `job_id` + `status_url` segera (non-blocking) |
| Tercatat di tabel `jobs`? | Tidak perlu (opsional, bisa dicatat untuk histori tapi tidak lewat worker) | Ya, wajib |

### 5.4 Startup Resume (kode)

```python
# main.py
@app.on_event("startup")
async def resume_pending_jobs():
    stuck_jobs = job_repo.get_jobs_by_status(["queued", "processing"])
    for job in stuck_jobs:
        if job.status == "processing":
            job_repo.update_status(job.id, "queued")  # reset, karena eksekusi lama pasti terputus
    asyncio.create_task(worker_loop())

async def worker_loop():
    semaphore = asyncio.Semaphore(get_current_max_concurrent_jobs())
    while True:
        settings = settings_repo.get()
        # re-check tiap iterasi supaya perubahan /settings langsung berlaku
        job = job_repo.get_next_queued()
        if job and semaphore.locked() is False:
            asyncio.create_task(run_with_semaphore(semaphore, job))
        await asyncio.sleep(1)
```

## 6. Endpoint Design (Final, Lengkap)

Base path: `/api/v1`

### 6.1 Settings

```http
GET   /settings
PATCH /settings
```
```json
PATCH /settings
{
  "max_concurrent_jobs": 5,
  "default_translation_model_id": 3,
  "default_extraction_model_id": 4
}
```

### 6.2 Platforms & Models

```http
POST   /platforms
GET    /platforms
GET    /platforms/{platform_id}
PATCH  /platforms/{platform_id}
DELETE /platforms/{platform_id}

POST   /platforms/{platform_id}/models
GET    /platforms/{platform_id}/models
PATCH  /platforms/{platform_id}/models/{model_id}
DELETE /platforms/{platform_id}/models/{model_id}

GET    /models              -- flat list semua model lintas platform (untuk pilih model_id di UI/client)
GET    /models/{model_id}
```

```json
POST /platforms
{
  "name": "aihubmix",
  "apiKey": "sk-...",
  "apiType": "chat-completions"
}

POST /platforms/{platform_id}/models
{
  "name": "gpt-5.5-free",
  "url": "https://aihubmix.com"
}
```

### 6.3 Series / Glossary / Characters

Sama seperti v1 §8.2, §8.4, §8.5 — hanya field `translation_model_config_id`/`extraction_model_config_id` diganti nama jadi `translation_model_id`/`extraction_model_id` (merujuk ke `models.id`).

### 6.4 Series Summary (manual + generate opsional)

Sama seperti v1 §8.3, tidak berubah.

### 6.5 Chapters — CRUD

Sama seperti v1 §8.6, tidak berubah.

### 6.6 Translate (Single Chapter — 2 Mode)

```http
POST /series/{series_id}/chapters/{chapter_number}/translate
```

```json
{
  "mode": "async",
  "force_translate": false,
  "force_summary": false,
  "extract": true,
  "translation_model": { "model_id": 5 },
  "extraction_model": {
    "platform": { "name": "aihubmix", "apiType": "chat-completions" },
    "model": { "name": "gpt-5.5-free", "url": "https://aihubmix.com" }
  }
}
```

**Catatan penting soal `force_*` untuk chapter baru:**
Kalau chapter belum pernah diterjemahkan (`status='pending'`), field `force_translate`/`force_summary` **diabaikan sepenuhnya** — translate berjalan seperti proses normal pertama kali, tidak perlu `force=true`. Flag `force_*` hanya relevan/dicek untuk chapter yang **sudah** `status='translated'`.

**Response — mode sync:**
```json
{
  "mode": "sync",
  "chapter_number": 15,
  "status": "translated",
  "translated_text": "...",
  "chapter_summary": "...",
  "extract_status": "done",
  "translated_by_model_name": "gpt-5.5-free",
  "source_language": "ja"
}
```

**Response — mode async:**
```json
{
  "mode": "async",
  "job_id": 42,
  "status": "queued",
  "status_url": "/api/v1/jobs/42"
}
```
Response ini **selalu** langsung kembali secepatnya, termasuk saat semua slot `max_concurrent_jobs` sedang penuh — job tetap tercatat `queued` dan client cukup polling `status_url`.

### 6.7 Jobs

```http
GET /jobs/{job_id}
GET /jobs?series_id=&status=&limit=
```

```json
GET /jobs/42
{
  "id": 42,
  "series_id": 3,
  "chapter_number": 15,
  "status": "completed",
  "result": {
    "chapter_number": 15,
    "translated_text": "...",
    "chapter_summary": "...",
    "extract_status": "done",
    "translated_by_model_name": "gpt-5.5-free",
    "source_language": "ja"
  },
  "created_at": "...",
  "started_at": "...",
  "completed_at": "..."
}
```
Kalau `status="failed"`: field `result` null, field `error` berisi pesan kegagalan.

### 6.8 Context Preview & Monitoring

Sama seperti v1 §8.8, §8.9 — tidak berubah.

## 7. Endpoint Summary Table (v2, Update)

| Method | Endpoint | Keterangan |
|---|---|---|
| GET/PATCH | `/settings` | Konfigurasi global: max_concurrent_jobs, default model translate/extract |
| POST/GET | `/platforms` | Kelola platform (kredensial + apiType) |
| GET/PATCH/DELETE | `/platforms/{id}` | Detail/update/hapus platform |
| POST/GET | `/platforms/{id}/models` | Kelola model di dalam platform |
| PATCH/DELETE | `/platforms/{id}/models/{model_id}` | Update/hapus model |
| GET | `/models`, `/models/{id}` | List/detail model lintas platform |
| POST/GET | `/series` | Sama seperti v1 |
| GET/PATCH/DELETE | `/series/{id}` | Sama seperti v1, field model rename ke `*_model_id` |
| GET/POST | `/series/{id}/summary`, `/summary/generate` | Sama seperti v1 |
| GET | `/series/{id}/status` | Sama seperti v1 |
| CRUD | `/series/{id}/glossary`, `/characters` | Sama seperti v1 |
| CRUD | `/series/{id}/chapters` | Sama seperti v1 |
| POST | `/series/{id}/chapters/{n}/translate` | **Updated**: field `mode` (sync/async), `translation_model`/`extraction_model` (model_id atau inline) |
| GET | `/series/{id}/chapters/{n}/context` | Sama seperti v1 |
| GET | `/jobs/{id}` | **Baru**: status & hasil job async |
| GET | `/jobs` | **Baru**: list job (filter series_id/status) |

## 8. Keputusan Desain Kunci (v2, Tambahan dari v1)

1. **Platform terpisah dari Model** — satu kredensial (`api_key`) dipakai bersama oleh banyak model dalam platform yang sama, menghindari duplikasi API key tiap kali menambah model baru dari provider yang sama.
2. **Create-or-append inline, overwrite parsial** — mengirim ulang platform/model yang sudah ada tidak menghapus data lama; hanya field yang eksplisit dikirim yang di-update (berguna untuk rotate API key tanpa mengganggu daftar model yang sudah terhubung).
3. **Multi apiType dengan fallback aman** — `chat-completions` sebagai default/fallback berarti platform yang tidak eksplisit set `apiType` otomatis kompatibel dengan mayoritas provider OpenAI-compatible.
4. **Job queue tanpa Redis, tapi tahan restart** — kombinasi tabel `jobs` di SQLite + worker loop `asyncio` yang di-resume saat `startup` event memberi daya tahan dasar tanpa menambah dependency infrastruktur, sesuai skala single-user.
5. **Sync tidak ikut kuota concurrency** — mode sync murni tanggung jawab client (kalau mau tunggu lama, silakan), tidak mengganggu antrean job async lain.
6. **Batch endpoint dihapus, diganti pola "fire many async requests"** — client bisa loop kirim banyak `POST .../translate` dengan `mode="async"` secara cepat berurutan; backend menerima semuanya secara instan (return job_id masing-masing) dan mengeksekusinya sendiri sesuai `max_concurrent_jobs`, tanpa client perlu menahan koneksi.
7. **Job result menyimpan hasil lengkap** — karena batch dihapus dan job selalu 1 chapter, tidak ada risiko response job membengkak seperti kasus batch besar; `result` JSON di tabel `jobs` cukup menyimpan data setara response sync.
