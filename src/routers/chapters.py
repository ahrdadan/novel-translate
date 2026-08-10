"""Chapters router — CRUD + context preview (PRD §6.5, §6.8)."""

from fastapi import APIRouter, HTTPException

from src.models.chapter import (
    ChapterContextResponse,
    ChapterCreate,
    ChapterListItem,
    ChapterResponse,
    ChapterUpdate,
)
from src.repositories import chapter_repo, character_repo, glossary_repo, series_repo

router = APIRouter(prefix="/series/{series_id}/chapters", tags=["chapters"])


@router.post("", response_model=ChapterResponse, status_code=201)
async def create_chapter(series_id: int, body: ChapterCreate):
    series = await series_repo.get_series_by_id(series_id)
    if not series:
        raise HTTPException(404, "Series not found")
    existing = await chapter_repo.get_chapter(series_id, body.chapter_number)
    if existing:
        raise HTTPException(409, f"Chapter {body.chapter_number} already exists in this series")
    data = body.model_dump()
    data["series_id"] = series_id
    return await chapter_repo.create_chapter(data)


@router.get("", response_model=list[ChapterListItem])
async def list_chapters(series_id: int):
    series = await series_repo.get_series_by_id(series_id)
    if not series:
        raise HTTPException(404, "Series not found")
    return await chapter_repo.get_chapters_by_series(series_id)


@router.get("/{chapter_number}", response_model=ChapterResponse)
async def get_chapter(series_id: int, chapter_number: int):
    chapter = await chapter_repo.get_chapter(series_id, chapter_number)
    if not chapter:
        raise HTTPException(404, "Chapter not found")
    return chapter


@router.patch("/{chapter_number}", response_model=ChapterResponse)
async def update_chapter(series_id: int, chapter_number: int, body: ChapterUpdate):
    chapter = await chapter_repo.get_chapter(series_id, chapter_number)
    if not chapter:
        raise HTTPException(404, "Chapter not found")
    updates = body.model_dump(exclude_unset=True)
    return await chapter_repo.update_chapter(chapter["id"], updates)


@router.delete("/{chapter_number}", status_code=204)
async def delete_chapter(series_id: int, chapter_number: int):
    chapter = await chapter_repo.get_chapter(series_id, chapter_number)
    if not chapter:
        raise HTTPException(404, "Chapter not found")
    await chapter_repo.delete_chapter(chapter["id"])


# --- Context preview (PRD §6.8) ---

@router.get("/{chapter_number}/context", response_model=ChapterContextResponse)
async def get_chapter_context(series_id: int, chapter_number: int):
    """Return context preview: previous chapter summary + glossary + characters."""
    series = await series_repo.get_series_by_id(series_id)
    if not series:
        raise HTTPException(404, "Series not found")

    prev_summary = await chapter_repo.get_previous_chapter_summary(series_id, chapter_number)
    glossary = await glossary_repo.get_terms_by_series(series_id)
    characters = await character_repo.get_characters_by_series(series_id)

    return {
        "chapter_number": chapter_number,
        "previous_summary": prev_summary,
        "glossary": glossary,
        "characters": characters,
    }
