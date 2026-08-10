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

### 2. Global Settings
- `GET /api/v1/settings` - Retrieve global configuration.
- `PATCH /api/v1/settings` - Update `max_concurrent_jobs`, default translation/extraction models.

### 3. Platforms & Model Management
- `POST /api/v1/platforms` - Add an API platform (credentials & API type, optional nested models).
- `GET /api/v1/platforms` - List platforms with their models.
- `POST /api/v1/platforms/{platform_id}/models` - Add model under a platform.
- `GET /api/v1/models` - List all registered models across platforms.

### 4. Series & Chapters
- `POST /api/v1/series` - Create a novel series.
- `GET /api/v1/series/{id}/status` - Get series translation statistics.
- `POST /api/v1/series/{id}/chapters` - Create chapter (accepts source text/HTML).
- `GET /api/v1/series/{id}/chapters/{n}/context` - Preview chapter context (glossary + summary).

### 5. Translation & Jobs
- `POST /api/v1/series/{id}/chapters/{n}/translate` - Trigger chapter translation (sync/async).
- `GET /api/v1/jobs/{job_id}` - Check async job status & result.
- `GET /api/v1/jobs` - List jobs with optional status/series filters.


---

## 📄 License

This project is licensed under the MIT License.
