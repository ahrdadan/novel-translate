"""Glossary router — CRUD for glossary_terms (PRD §6.3)."""

from fastapi import APIRouter, HTTPException
from src.models.glossary import (
    GlossaryTermCreate,
    GlossaryTermResponse,
    GlossaryTermUpdate,
)
from src.repositories import glossary_repo, series_repo

router = APIRouter(prefix="/series/{series_id}/glossary", tags=["glossary"])


@router.post("", response_model=GlossaryTermResponse, status_code=201)
async def create_term(series_id: int, body: GlossaryTermCreate):
    series = await series_repo.get_series_by_id(series_id)
    if not series:
        raise HTTPException(404, "Series not found")
    data = body.model_dump()
    return await glossary_repo.create_term(series_id, data)


@router.get("", response_model=list[GlossaryTermResponse])
async def list_terms(series_id: int):
    series = await series_repo.get_series_by_id(series_id)
    if not series:
        raise HTTPException(404, "Series not found")
    return await glossary_repo.get_terms_by_series(series_id)


@router.patch("/{term_id}", response_model=GlossaryTermResponse)
async def update_term(series_id: int, term_id: int, body: GlossaryTermUpdate):
    term = await glossary_repo.get_term_by_id(term_id)
    if not term or term["series_id"] != series_id:
        raise HTTPException(404, "Term not found")
    updates = body.model_dump(exclude_unset=True)
    return await glossary_repo.update_term(term_id, updates)


@router.delete("/{term_id}", status_code=204)
async def delete_term(series_id: int, term_id: int):
    term = await glossary_repo.get_term_by_id(term_id)
    if not term or term["series_id"] != series_id:
        raise HTTPException(404, "Term not found")
    await glossary_repo.delete_term(term_id)
