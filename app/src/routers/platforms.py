"""Platforms router — CRUD for platforms (PRD §6.2)."""

from fastapi import APIRouter, HTTPException

from src.models.platform import PlatformCreate, PlatformResponse, PlatformUpdate
from src.repositories import model_repo, platform_repo

router = APIRouter(prefix="/platforms", tags=["platforms"])


@router.post("", response_model=PlatformResponse, status_code=201)
async def create_platform(body: PlatformCreate):
    existing = await platform_repo.get_platform_by_name(body.name)
    if existing:
        raise HTTPException(409, f"Platform '{body.name}' already exists")
    platform = await platform_repo.create_platform(
        name=body.name,
        api_key=body.api_key,
        api_type=body.api_type,
    )
    if body.models:
        for m in body.models:
            await model_repo.create_model(
                platform_id=platform["id"],
                name=m.name,
                url=m.url,
            )
    platform["models"] = await model_repo.get_models_by_platform(platform["id"])
    return platform


@router.get("", response_model=list[PlatformResponse])
async def list_platforms():
    platforms = await platform_repo.get_all_platforms()
    for p in platforms:
        p["models"] = await model_repo.get_models_by_platform(p["id"])
    return platforms


@router.get("/{platform_id}", response_model=PlatformResponse)
async def get_platform(platform_id: int):
    p = await platform_repo.get_platform_by_id(platform_id)
    if not p:
        raise HTTPException(404, "Platform not found")
    p["models"] = await model_repo.get_models_by_platform(p["id"])
    return p


@router.patch("/{platform_id}", response_model=PlatformResponse)
async def update_platform(platform_id: int, body: PlatformUpdate):
    existing = await platform_repo.get_platform_by_id(platform_id)
    if not existing:
        raise HTTPException(404, "Platform not found")
    updates = body.model_dump(exclude_unset=True)
    p = await platform_repo.update_platform(platform_id, updates)
    p["models"] = await model_repo.get_models_by_platform(p["id"])
    return p


@router.delete("/{platform_id}", status_code=204)
async def delete_platform(platform_id: int):
    deleted = await platform_repo.delete_platform(platform_id)
    if not deleted:
        raise HTTPException(404, "Platform not found")

