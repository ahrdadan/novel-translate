"""Characters router — CRUD for characters (PRD §6.3)."""

from fastapi import APIRouter, HTTPException
from src.models.character import CharacterCreate, CharacterResponse, CharacterUpdate
from src.repositories import character_repo, series_repo

router = APIRouter(prefix="/series/{series_id}/characters", tags=["characters"])


@router.post("", response_model=CharacterResponse, status_code=201)
async def create_character(series_id: int, body: CharacterCreate):
    series = await series_repo.get_series_by_id(series_id)
    if not series:
        raise HTTPException(404, "Series not found")
    data = body.model_dump()
    return await character_repo.create_character(series_id, data)


@router.get("", response_model=list[CharacterResponse])
async def list_characters(series_id: int):
    series = await series_repo.get_series_by_id(series_id)
    if not series:
        raise HTTPException(404, "Series not found")
    return await character_repo.get_characters_by_series(series_id)


@router.patch("/{character_id}", response_model=CharacterResponse)
async def update_character(series_id: int, character_id: int, body: CharacterUpdate):
    char = await character_repo.get_character_by_id(character_id)
    if not char or char["series_id"] != series_id:
        raise HTTPException(404, "Character not found")
    updates = body.model_dump(exclude_unset=True)
    return await character_repo.update_character(character_id, updates)


@router.delete("/{character_id}", status_code=204)
async def delete_character(series_id: int, character_id: int):
    char = await character_repo.get_character_by_id(character_id)
    if not char or char["series_id"] != series_id:
        raise HTTPException(404, "Character not found")
    await character_repo.delete_character(character_id)
