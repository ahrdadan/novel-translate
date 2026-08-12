"""Settings router — GET /settings, PATCH /settings."""

from fastapi import APIRouter

from src.models.settings import SettingsResponse, SettingsUpdate
from src.repositories import settings_repo

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=SettingsResponse)
async def get_settings():
    return await settings_repo.get_settings()


@router.patch("", response_model=SettingsResponse)
async def update_settings(body: SettingsUpdate):
    updates = body.model_dump(exclude_unset=True)
    return await settings_repo.update_settings(updates)
