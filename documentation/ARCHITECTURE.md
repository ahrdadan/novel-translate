# System Architecture & Technical Specification

This document provides a comprehensive technical overview of the **Novel Translation API** backend system, data flow, database schemas, and service layer integration.

> 📖 **Per-Endpoint Data Flow & Flowcharts**: For detailed step-by-step Mermaid diagrams of each API endpoint process (ingress, parsing, model resolution, agent pipeline, database CRUD, and response formatting), see [ENDPOINT_FLOWCHARTS.md](file:///d:/Project_/2026/python/novel-trans-app/documentation/ENDPOINT_FLOWCHARTS.md).
> 🗄️ **Database Schema Specification**: For full column definitions, foreign keys, data types, and indexes, see [DATABASE_DESIGN.md](file:///d:/Project_/2026/python/novel-trans-app/documentation/DATABASE_DESIGN.md).

---

## 🏛️ High-Level System Architecture

The application is structured into decoupled layers following clean architecture principles: **API Routers**, **Service Orchestrators**, **Repositories**, and **Database Drivers**.

```mermaid
graph TD
    Client[Client Applications / Web UI / Mobile / Scripts]

    subgraph FastAPI Application Engine
        Router[FastAPI Routers /api/v1]
        HTMLP[HTML Parser & Markdown Minifier]
        MRes[Model Resolver Service]
        Worker[Background Job Worker Loop]
    end

    subgraph Service Layer
        Translator[Translation Engine]
        Summarizer[Plot Summarizer]
        Extractor[Entity & Glossary Extractor]
        AdapterFactory[LLM Adapter Factory]
    end

    subgraph Adapters & LLM API Integration
        ChatAdapter[ChatCompletions Adapter]
        RespAdapter[Responses API Adapter]
        MsgAdapter[Messages API Adapter]
    end

    subgraph Data Store
        SQLite[(SQLite WAL Mode Database)]
    end

    Client -->|HTTP REST / JSON| Router
    Router --> HTMLP
    Router --> MRes
    Router --> Worker
    Worker --> Translator
    Worker --> Summarizer
    Worker --> Extractor
    Translator --> AdapterFactory
    Summarizer --> AdapterFactory
    Extractor --> AdapterFactory
    AdapterFactory --> ChatAdapter
    AdapterFactory --> RespAdapter
    AdapterFactory --> MsgAdapter
    MRes --> SQLite
    Worker --> SQLite
```

---

## 💻 Tech Stack & Specifications

| Layer | Technology | Specification / Details |
|---|---|---|
| **Runtime** | Python 3.14+ | Utilizing modern async/await syntax and optimized performance |
| **Package Manager** | `uv` | Ultra-fast Python package & virtualenv manager |
| **Web Framework** | FastAPI | High-performance ASGI framework with Pydantic v2 validation |
| **Database** | SQLite + `aiosqlite` | Asynchronous SQLite driver running with `PRAGMA journal_mode = WAL` |
| **Concurrency** | `asyncio.Semaphore` | Dynamic concurrency control with runtime setting adjustments |
| **Parsing** | BeautifulSoup4 / Selectolax | HTML cleanup, selector extraction, and markdown transformation |

---

## 📊 Relational Database Schema (SQLite)

The SQLite database (`data/novel_trans.db`) relies on foreign key enforcement (`PRAGMA foreign_keys = ON`) and WAL mode for efficient multi-process read/write operations.

```mermaid
erDiagram
    PLATFORMS ||--o{ MODELS : "has many"
    MODELS ||--o{ SERIES : "default translation/extraction model"
    MODELS ||--o{ CHAPTERS : "used for translation/extraction"
    SETTINGS }o--|| MODELS : "global default models"
    SERIES ||--o{ CHAPTERS : "contains"
    SERIES ||--o{ GLOSSARY_TERMS : "owns"
    SERIES ||--o{ CHARACTERS : "owns"
    SERIES ||--o{ JOBS : "executes"

    PLATFORMS {
        int id PK
        string name UK
        string api_key
        string api_type
        timestamp created_at
    }

    MODELS {
        int id PK
        int platform_id FK
        string name
        string url
        timestamp created_at
    }

    SETTINGS {
        int id PK
        int max_concurrent_jobs
        int default_translation_model_id FK
        int default_extraction_model_id FK
    }

    SERIES {
        int id PK
        string name UK
        string original_title
        string author
        string status
        string summary
        int translation_model_id FK
        int extraction_model_id FK
        int last_translated_chapter
    }

    CHAPTERS {
        int id PK
        int series_id FK
        int chapter_number
        string title
        string source_text
        string translated_text
        string chapter_summary
        string status
        string extract_status
    }

    JOBS {
        int id PK
        int series_id FK
        int chapter_number
        string status
        int force_translate
        int extract
        string translation_model_ref
        string result
        string error
    }
```

---

## 🎯 Model Resolution Hierarchy

Model resolution dynamically determines which LLM configuration to execute for translation or extraction tasks based on a prioritized 3-tier hierarchy:

```mermaid
flowchart TD
    Start([Translation / Extraction Triggered]) --> Step1{Request Body contains model ref?}
    Step1 -- Yes: explicit model_id --> CheckID[Fetch model from DB by ID]
    Step1 -- Yes: inline platform + model --> CreateAppend[Execute Create-or-Append Logic]
    
    Step1 -- No --> Step2{Series has override model_id?}
    Step2 -- Yes --> FetchSeriesModel[Fetch Series Model Configuration]
    
    Step2 -- No --> Step3{Settings has global default model_id?}
    Step3 -- Yes --> FetchGlobalModel[Fetch Global Default Model Configuration]
    Step3 -- No --> Error[Throw 400 Bad Request Error]

    CheckID --> Execute[Execute LLM API Call via Adapter]
    CreateAppend --> Execute
    FetchSeriesModel --> Execute
    FetchGlobalModel --> Execute
```

### Create-or-Append Rule Matrix
- **Existing Platform / Model**: If a platform or model with the matching name exists, only the non-null fields explicitly provided in the payload will be updated. Other existing fields (such as `api_key` or `url`) remain intact.
- **New Platform / Model**: Automatically inserts a new platform or model record into the database.

---

## ⏳ Async Job Queue & Worker System

1. **Job Lifecycle**:
   - `queued`: Added to database, waiting for execution slot.
   - `processing`: Worker acquired concurrency slot and actively translating/extracting.
   - `completed`: Successfully processed; results written to `chapters`, `series`, and `jobs.result`.
   - `failed`: Exception captured; error message recorded in `jobs.error`.

2. **Server Startup Recovery**:
   When the FastAPI lifespan starts, `JobWorkerService` automatically queries jobs with `status IN ('queued', 'processing')` and re-enqueues them into the asyncio worker loop. This ensures zero data loss during server restarts or deployment cycles.

3. **Concurrency Control**:
   `max_concurrent_jobs` can be dynamically altered via `PATCH /api/v1/settings`. The worker automatically adjusts its `asyncio.Semaphore` bound without requiring a server reboot.
