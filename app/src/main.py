"""Novel Translation API — FastAPI application entry point.

Startup:
- Initialize SQLite database
- Resume any stuck jobs from previous run
- Start the background job worker loop
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.database import close_db, init_db
from src.routers.chapters import router as chapters_router
from src.routers.characters import router as characters_router
from src.routers.glossary import router as glossary_router
from src.routers.jobs import router as jobs_router
from src.routers.models import router as models_router
from src.routers.platforms import router as platforms_router
from src.routers.series import router as series_router
from src.routers.settings import router as settings_router
from src.routers.snapshots import router as snapshots_router
from src.routers.system_prompts import router as system_prompts_router
from src.routers.translate import router as translate_router
from src.routers.unified_translate import router as unified_translate_router
from src.routers.websocket import router as websocket_router
from src.services.job_worker import resume_pending_jobs

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    # Startup
    logger.info("Initializing database...")
    await init_db()
    logger.info("Database initialized.")

    logger.info("Resuming pending jobs and starting worker loop...")
    await resume_pending_jobs()
    logger.info("Worker loop started.")

    yield

    # Shutdown
    logger.info("Shutting down...")
    await close_db()
    logger.info("Database connection closed.")


openapi_tags = [
    {
        "name": "⚡ Quickstart Translate",
        "description": "All-in-One endpoint (POST /api/v1/translate-novel) to submit Series, Chapter, Platform, Model, and System Prompt in a single request.",
    },
    {
        "name": "translate",
        "description": "Chapter translation endpoints.",
    },
    {
        "name": "series",
        "description": "Series management.",
    },
    {
        "name": "chapters",
        "description": "Chapter management.",
    },
    {
        "name": "glossary",
        "description": "Glossary terms management.",
    },
    {
        "name": "characters",
        "description": "Character entities management.",
    },
    {
        "name": "models",
        "description": "Model management.",
    },
    {
        "name": "platforms",
        "description": "Platform management.",
    },
    {
        "name": "system-prompts",
        "description": "System prompt templates.",
    },
    {
        "name": "jobs",
        "description": "Async background job tracking.",
    },
    {
        "name": "settings",
        "description": "Global application settings.",
    },
    {
        "name": "snapshots",
        "description": "System backup and restore snapshots.",
    },
]

app = FastAPI(
    title="Novel Translation API",
    description="AI-powered novel translation API with multi-platform LLM support, job queue, and glossary management.",
    version="1.0.0",
    lifespan=lifespan,
    openapi_tags=openapi_tags,
)

# CORS — allow all origins for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register all routers under /api/v1 (Quickstart All-in-One endpoint FIRST)
API_PREFIX = "/api/v1"

app.include_router(unified_translate_router, prefix=API_PREFIX)
app.include_router(translate_router, prefix=API_PREFIX)
app.include_router(series_router, prefix=API_PREFIX)
app.include_router(chapters_router, prefix=API_PREFIX)
app.include_router(glossary_router, prefix=API_PREFIX)
app.include_router(characters_router, prefix=API_PREFIX)
app.include_router(models_router, prefix=API_PREFIX)
app.include_router(platforms_router, prefix=API_PREFIX)
app.include_router(system_prompts_router, prefix=API_PREFIX)
app.include_router(jobs_router, prefix=API_PREFIX)
app.include_router(settings_router, prefix=API_PREFIX)
app.include_router(snapshots_router, prefix=API_PREFIX)
app.include_router(websocket_router, prefix=API_PREFIX)
app.include_router(websocket_router)



@app.get("/")
async def root():
    return {
        "name": "Novel Translation API",
        "version": "1.0.0",
        "docs": "/docs",
    }
