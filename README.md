# Novel Translation API

AI-powered novel translation REST API built with **FastAPI**, **SQLite (`aiosqlite`)**, an async **Job Queue**, and a **Multi-Platform LLM Adapter** system.

Version: **1.0.0**

---

## 🌟 Key Features

- **Multi-Platform LLM Support**: Adaptable architecture for multiple API provider formats:
  - `chat-completions` (OpenAI-compatible)
  - `responses` (OpenAI Responses API)
  - `messages` (Anthropic Messages API format)
- **Flexible Model Resolution**:
  - Request-level inline platform/model definition with create-or-append logic
  - Series-level model override
  - Global default settings override
- **Async Job Queue & Concurrency Management**:
  - `sync` mode (blocking response) or `async` mode (returns job ID for polling)
  - Managed concurrency via `max_concurrent_jobs` setting
  - Automatic startup resume mechanism to recover queued/stuck jobs after server restarts
- **Context & Glossary Retention**:
  - Automatic running plot summary maintenance across consecutive chapters
  - Glossary terms and character dictionaries injected into translation system prompts
  - Post-translation automatic entity extraction (characters & terms)
- **HTML Parsing & Markdown Normalization**: Built-in HTML to Markdown converter and minifier for novel chapter imports.

---

## 📁 Project Architecture

```
novel-trans-app/
├── PRD_Novel_Translation_API_v2.md   # PRD specification
├── pyproject.toml                     # Dependencies and project metadata
├── README.md                          # Project documentation
├── data/                              # SQLite database storage (novel_trans.db)
└── src/
    ├── main.py                        # FastAPI application entry point & lifespan
    ├── database.py                    # SQLite database initialization & connection
    ├── html_parser.py                 # HTML to Markdown parser & minifier
    │
    ├── models/                        # Pydantic schemas (Platform, Model, Series, Chapter, etc.)
    ├── repositories/                  # Async SQLite repository layer
    ├── routers/                       # FastAPI endpoint routers (/api/v1/...)
    │
    └── services/                      # Core business logic
        ├── translator.py              # Translation system prompt & engine
        ├── summarizer.py              # Chapter plot summarizer
        ├── extractor.py               # Character & glossary extraction
        ├── model_resolver.py          # Dynamic model resolution & inline upsert
        ├── job_worker.py              # Background job worker loop & queue manager
        └── llm_adapters/              # LLM API format adapters (chat-completions, responses, messages)
```

---

## 🚀 Getting Started

### Prerequisites

- Python `>=3.14`
- [uv](https://github.com/astral-sh/uv) package manager

### 1. Installation

Install all project dependencies:

```bash
uv sync
```

### 2. Running the Server

Start the FastAPI development server with Uvicorn:

```bash
uv run uvicorn src.main:app --reload --port 8000
```

The server will automatically initialize the SQLite database (`data/novel_trans.db`) and start the background job worker loop.

### 3. API Documentation & System Specifications

- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

#### 📚 System Documentation Files:
- [API Endpoints Flowcharts & Process Lifecycle](file:///d:/Project_/2026/python/novel-trans-app/documentation/ENDPOINT_FLOWCHARTS.md) — Step-by-step Mermaid & ASCII diagrams for every endpoint process.
- [SQLite Database Design & Schemas](file:///d:/Project_/2026/python/novel-trans-app/documentation/DATABASE_DESIGN.md) — Tables, foreign keys, constraints, data types, and indexes.
- [System Architecture](file:///d:/Project_/2026/python/novel-trans-app/documentation/ARCHITECTURE.md) — Technical architecture, database schemas, and model resolution hierarchy.
- [API Requests Samples](file:///d:/Project_/2026/python/novel-trans-app/documentation/API_REQUESTS_SAMPLES.md) — cURL requests & JSON response examples for all endpoints.
- [API & UI Design System](file:///d:/Project_/2026/python/novel-trans-app/documentation/DESIGN_SYSTEM.md) — Data contracts, status codes, and frontend visual tokens.
- [PRD Specification v2](file:///d:/Project_/2026/python/novel-trans-app/documentation/PRD_Novel_Translation_API_v2.md) — Full product requirement document.

---

## 📡 Core API Endpoints Overview

All API endpoints are prefixed with `/api/v1`.

### 1. Unified All-In-One API (Recommended)
- `POST /api/v1/translate-novel` - Create/resolve Series, Chapter (HTML or raw text), Platform, Model, and execute translation in a single request.

> [!NOTE]
> See [API_REQUESTS_SAMPLES.md: 📋 6.1 Complete Endpoint Parameter Specification Table](file:///d:/Project_/2026/python/novel-trans-app/documentation/API_REQUESTS_SAMPLES.md#61-complete-endpoint-parameter-specification-table) for full parameter documentation and cURL examples.

#### 📋 Complete Endpoint Parameter Specification Table

| Parameter / Field | Type | Status | Default | Description & Resolution Rule |
|---|---|---|---|---|
| **`series`** | `Object` \| `Integer` \| `String` | **Required** | — | **Series Reference**: Object `{"name": "..."}`, ID integer `1`, or string `"Shadow Slave"`. Resolved by ID or Name if existing; created automatically if Name is not found. |
| `series.id` | `Integer` | *Optional* | `null` | Existing Series ID in database. |
| `series.name` | `String` | *Optional* | `null` | Series title. If series already exists, resolved by Name. If missing, creates a new series. |
| `series.author` | `String` | *Optional* | `null` | Author name (used only when creating a new series). |
| `series.description` | `String` | *Optional* | `null` | Series synopsis (used only when creating a new series). |
| **`chapter`** | `Object` \| `Integer` | **Required** | — | **Chapter Input**: Object or integer chapter number `1`. |
| `chapter.chapterNumber` | `Integer` | **Required** | — | Chapter sequence number (e.g., `1`, `2`). |
| `chapter.title` | `String` | *Optional* | `null` | Chapter title. |
| `chapter.sourceText` | `String` | **Required*** | `null` | Raw text or HTML string. **Required for new chapters**. *Optional if chapter already exists in DB*. |
| `chapter.sourceLanguage` | `String` | *Optional* | `"auto"` | Source language code (`"auto"`, `"zh"`, `"ja"`, `"ko"`). |
| **`translationModel`** | `Object` \| `Integer` | *Optional* | `null` | **Translation Model Reference**: Integer ID `2`, or platform object. |
| `translationModel.modelId` | `Integer` | *Optional* | `null` | Direct model ID from database. |
| `translationModel.platform` | `Object` | *Optional* | `null` | Platform object containing `name` or `id`, and single `model` or `models` array. |
| `translationModel.platform.id` | `Integer` | *Optional* | `null` | Existing Platform ID. |
| `translationModel.platform.name` | `String` | *Optional* | `null` | Platform provider name (e.g., `"aihubmix"`). Resolves existing or creates new. |
| `translationModel.platform.apiKey` | `String` | *Optional* | `null` | API key credential for provider. |
| `translationModel.platform.apiType` | `String` | *Optional* | `"chat-completions"` | API protocol format (`"chat-completions"`, `"responses"`, `"messages"`). |
| `translationModel.platform.model` | `Object` | *Optional* | `null` | **Single Model Object (1 Chapter 1 Model)**: `{"name": "gpt-4o", "url": "..."}`. |
| `translationModel.platform.models` | `Array` | *Optional* | `null` | **Multiple Models Array**: `[{"name": "gpt-4o"}, {"name": "claude-3-5-sonnet"}]`. |
| **`summarizeModel`** | `Object` \| `Integer` | *Optional* | `null` | **Summarize Model Reference** (Pipeline mode): Dedicated model for chapter summarization. Defaults to `translationModel` if omitted. |
| **`extractionModel`** | `Object` \| `Integer` | *Optional* | `null` | Extraction Model Reference (same structure as `translationModel`). |
| **`systemPrompt`** | `Object` \| `Integer` \| `String` | *Optional* | `null` | **System Prompt Reference**: Select existing prompt by ID `2`, by Name `"default"`, or create on-the-fly `{"name": "wuxia_tone", "promptText": "..."}`. |
| `systemPrompt.id` | `Integer` | *Optional* | `null` | Existing System Prompt ID in database. |
| `systemPrompt.name` | `String` | *Optional* | `null` | System Prompt name (e.g., `"default"`, `"formal"`, `"wuxia_tone"`). |
| `systemPrompt.promptText` | `String` | *Optional* | `null` | Prompt text content. If `name` is new, creates a new prompt in DB; if `name` exists, updates prompt text. |
| **`mode`** | `String` | *Optional* | `"sync"` | Execution mode: `"sync"` (blocking response) or `"async"` (job queue polling). |
| **`strategy`** | `String` | *Optional* | `"pipeline"` | Execution strategy: `"pipeline"` (decoupled 2-3 LLM calls for Translate/Summarize/Extract) or `"single_pass"` (all-in-one single LLM call). |
| **`forceTranslate`** | `Boolean` | *Optional* | `false` | Set `true` to force re-translating an already translated chapter. |
| **`forceSummary`** | `Boolean` | *Optional* | `false` | Set `true` to force re-generating chapter plot summary. |
| **`extract`** | `Boolean` | *Optional* | `true` | Set `true` to auto-extract newly introduced characters and glossary terms (Pipeline mode). |

#### Example Quickstart Request (New Series + HTML Chapter + New Platform/Model):
```bash
curl -X POST "http://localhost:8000/api/v1/translate-novel" \
     -H "Content-Type: application/json" \
     -d '{
           "series": {
             "name": "Lord of the Mysteries",
             "author": "Cuttlefish That Loves Diving",
             "description": "With the rising tide of steam and machinery..."
           },
           "chapter": {
             "chapterNumber": 1,
             "title": "Chapter 1: Crimson",
             "sourceText": "<div><h1>Chapter 1</h1><p>Pain. Painful. Painful in the head.</p></div>"
           },
           "translationModel": {
             "platform": {
               "name": "aihubmix",
               "apiKey": "sk-aihubmix-secret-key-12345",
               "apiType": "chat-completions",
               "model": {
                 "name": "gpt-4o",
                 "url": "https://aihubmix.com/v1"
               }
             }
           },
           "mode": "sync",
           "strategy": "pipeline"
         }'
```

#### Example JSON Response:
```json
{
  "mode": "sync",
  "series_id": 1,
  "series_name": "Lord of the Mysteries",
  "chapter_number": 1,
  "title": "Chapter 1: Crimson",
  "status": "translated",
  "translated_text": "# Chapter 1: Crimson\n\nPain. Painful. Painful in the head...",
  "plot_summary": "The protagonist wakes up in a dark room with severe head trauma.",
  "extracted_characters_count": 1,
  "extracted_terms_count": 0
}
```



### 2. Global Settings
- `GET /api/v1/settings` - Retrieve global configuration.
- `PATCH /api/v1/settings` - Update `max_concurrent_jobs`, default translation/extraction models.

### 3. Platforms & Model Management
- `POST /api/v1/platforms` - Add an API platform (credentials & API type, optional nested models).
- `GET /api/v1/platforms` - List platforms with their models.
- `POST /api/v1/platforms/{platform_id}/models` - Add model under a platform.
- `GET /api/v1/models` - List all registered models across platforms.

> 💡 **Smart Base URL Normalization**: All LLM Adapters (`chat-completions`, `responses`, `messages`) feature automatic URL normalization. Model URLs can be specified as base domain (`https://aihubmix.com`), versioned path (`https://aihubmix.com/v1`), or full endpoint (`https://aihubmix.com/v1/chat/completions`). The backend automatically normalizes the URL to prevent double `/v1/v1` or duplicate endpoint path suffixes.

### 4. Series & Chapters
- `POST /api/v1/series` - Create a novel series.
- `GET /api/v1/series/{id}/status` - Get series translation statistics.
- `POST /api/v1/series/{id}/chapters` - Create chapter (accepts source text/HTML).
- `GET /api/v1/series/{id}/chapters/{n}/context` - Preview chapter context (glossary + summary).

### 5. Translation & Jobs
- `POST /api/v1/series/{id}/chapters/{n}/translate` - Trigger chapter translation (sync/async).
- `GET /api/v1/jobs/{job_id}` - Check async job status & result.
- `GET /api/v1/jobs` - List jobs with optional status/series filters.

### 6. System Prompts Management
- `GET /api/v1/system-prompts` - List all system prompts in database.
- `POST /api/v1/system-prompts` - Create a new system prompt.
- `GET /api/v1/system-prompts/{id}` - Get system prompt details by ID.
- `PATCH /api/v1/system-prompts/{id}` - Update a system prompt text or name.
- `POST /api/v1/system-prompts/{id}/set-default` - Set a system prompt as global default.
- `DELETE /api/v1/system-prompts/{id}` - Delete a system prompt.



---

## 📄 License

This project is licensed under the MIT License.
