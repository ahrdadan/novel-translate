"""System Prompts router — CRUD endpoints for system_prompts table."""

from fastapi import APIRouter, HTTPException, status
from src.models.system_prompt import (
    SystemPromptCreate,
    SystemPromptResponse,
    SystemPromptUpdate,
)
from src.repositories import system_prompt_repo

router = APIRouter(prefix="/system-prompts", tags=["system-prompts"])


@router.get("", response_model=list[SystemPromptResponse])
async def list_system_prompts():
    """List all system prompts stored in the database."""
    return await system_prompt_repo.get_all_prompts()


@router.get("/{prompt_id}", response_model=SystemPromptResponse)
async def get_system_prompt(prompt_id: int):
    """Get a specific system prompt by ID."""
    prompt = await system_prompt_repo.get_prompt_by_id(prompt_id)
    if not prompt:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"System prompt {prompt_id} not found")
    return prompt


@router.post("", response_model=SystemPromptResponse, status_code=status.HTTP_201_CREATED)
async def create_system_prompt(body: SystemPromptCreate):
    """Create a new system prompt."""
    existing = await system_prompt_repo.get_prompt_by_name(body.name)
    if existing:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"System prompt with name '{body.name}' already exists",
        )
    return await system_prompt_repo.create_prompt(
        name=body.name,
        prompt_text=body.prompt_text,
        is_default=body.is_default,
    )


@router.patch("/{prompt_id}", response_model=SystemPromptResponse)
async def update_system_prompt(prompt_id: int, body: SystemPromptUpdate):
    """Update a system prompt by ID."""
    existing = await system_prompt_repo.get_prompt_by_id(prompt_id)
    if not existing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"System prompt {prompt_id} not found")

    if body.name and body.name != existing["name"]:
        duplicate = await system_prompt_repo.get_prompt_by_name(body.name)
        if duplicate:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"System prompt with name '{body.name}' already exists",
            )

    updates = body.model_dump(exclude_unset=True)
    return await system_prompt_repo.update_prompt(prompt_id, updates)


@router.post("/{prompt_id}/set-default", response_model=SystemPromptResponse)
async def set_default_system_prompt(prompt_id: int):
    """Set a specific system prompt as the default."""
    prompt = await system_prompt_repo.get_prompt_by_id(prompt_id)
    if not prompt:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"System prompt {prompt_id} not found")
    return await system_prompt_repo.set_default_prompt(prompt_id)


@router.delete("/{prompt_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_system_prompt(prompt_id: int):
    """Delete a system prompt by ID."""
    existing = await system_prompt_repo.get_prompt_by_id(prompt_id)
    if not existing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"System prompt {prompt_id} not found")

    if existing.get("is_default"):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Cannot delete the default system prompt. Set another prompt as default first.",
        )

    deleted = await system_prompt_repo.delete_prompt(prompt_id)
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"System prompt {prompt_id} not found")
