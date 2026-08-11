"""Models router — nested under platform + flat listing (PRD §6.2)."""

from fastapi import APIRouter, HTTPException
from src.models.model import (
    ModelCreate,
    ModelDetailResponse,
    ModelResponse,
    ModelUpdate,
)
from src.repositories import model_repo, platform_repo

router = APIRouter(tags=["models"])


# --- Nested under platform ---

@router.post("/platforms/{platform_id}/models", response_model=ModelResponse, status_code=201)
async def create_model(platform_id: int, body: ModelCreate):
    platform = await platform_repo.get_platform_by_id(platform_id)
    if not platform:
        raise HTTPException(404, "Platform not found")
    existing = await model_repo.get_model_by_platform_and_name(platform_id, body.name)
    if existing:
        raise HTTPException(409, f"Model '{body.name}' already exists on this platform")
    return await model_repo.create_model(
        platform_id=platform_id,
        name=body.name,
        url=body.url,
    )


@router.get("/platforms/{platform_id}/models", response_model=list[ModelResponse])
async def list_platform_models(platform_id: int):
    platform = await platform_repo.get_platform_by_id(platform_id)
    if not platform:
        raise HTTPException(404, "Platform not found")
    return await model_repo.get_models_by_platform(platform_id)


@router.patch("/platforms/{platform_id}/models/{model_id}", response_model=ModelResponse)
async def update_model(platform_id: int, model_id: int, body: ModelUpdate):
    model = await model_repo.get_model_by_id(model_id)
    if not model or model["platform_id"] != platform_id:
        raise HTTPException(404, "Model not found on this platform")
    updates = body.model_dump(exclude_unset=True)
    return await model_repo.update_model(model_id, updates)


@router.delete("/platforms/{platform_id}/models/{model_id}", status_code=204)
async def delete_model(platform_id: int, model_id: int):
    model = await model_repo.get_model_by_id(model_id)
    if not model or model["platform_id"] != platform_id:
        raise HTTPException(404, "Model not found on this platform")
    await model_repo.delete_model(model_id)


# --- Flat listing across all platforms ---

@router.get("/models", response_model=list[ModelDetailResponse])
async def list_all_models():
    return await model_repo.get_all_models()


@router.get("/models/{model_id}", response_model=ModelDetailResponse)
async def get_model(model_id: int):
    model = await model_repo.get_model_detail(model_id)
    if not model:
        raise HTTPException(404, "Model not found")
    return model


@router.post("/models/{model_id}/ping")
async def ping_model(model_id: int):
    from src.services.llm_adapters import get_adapter
    model = await model_repo.get_model_detail(model_id)
    if not model:
        raise HTTPException(404, "Model not found")
    
    platform = await platform_repo.get_platform_by_id(model["platform_id"])
    if not platform:
        raise HTTPException(404, "Platform not found")

    adapter = get_adapter(platform.get("api_type", "chat-completions"))
    try:
        res = await adapter.call(
            system_prompt="ping",
            user_prompt="ping",
            model_name=model["name"],
            base_url=model.get("url") or "",
            api_key=platform.get("api_key") or "",
            max_tokens=1
        )
        return {"status": "success", "message": "Model ping successful", "response": res}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, f"Ping failed: {e!s}")


@router.post("/models/{model_id}/check-streaming")
async def check_streaming(model_id: int):
    from src.services.llm_adapters import get_adapter
    model = await model_repo.get_model_detail(model_id)
    if not model:
        raise HTTPException(404, "Model not found")
    
    platform = await platform_repo.get_platform_by_id(model["platform_id"])
    if not platform:
        raise HTTPException(404, "Platform not found")

    adapter = get_adapter(platform.get("api_type", "chat-completions"))
    try:
        chunks = []
        async for chunk in adapter.call_stream(
            system_prompt="Return exactly 'streaming_test'",
            user_prompt="start",
            model_name=model["name"],
            base_url=model.get("url") or "",
            api_key=platform.get("api_key") or "",
            max_tokens=5
        ):
            chunks.append(chunk)
        
        return {
            "status": "success",
            "message": "Streaming works",
            "chunks_received": len(chunks),
            "final_text": "".join(chunks)
        }
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, f"Streaming check failed: {e!s}")
