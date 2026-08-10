"""Model resolution — resolve_or_create_model() and full chain resolution.

Implements PRD v2 §3.2 and §3.3.
"""

from fastapi import HTTPException

from src.repositories import model_repo, platform_repo, series_repo, settings_repo


async def resolve_or_create_model(ref: int | str | dict) -> dict:
    """Resolve a model reference to a model dict.

    Supports ultra-flexible references:
      - Direct integer/string model ID: 5 or "5" or {"model_id": 5}
      - Existing platform ID + model ID: {"platform": {"id": 1}, "model": {"id": 5}}
      - Existing platform ID + model Name: {"platform": {"id": 1}, "model": {"name": "gpt-4o"}}
      - Platform Name + Single Model: {"platform": {"name": "aihubmix", "model": {"name": "gpt-4o", "url": "..."}}}
      - Platform Name + Models Array: {"platform": {"name": "aihubmix", "models": [{"name": "gpt-4o"}]}}

    Uses create-or-append logic: existing platform/models are updated only
    for fields explicitly sent; missing fields keep their old values.
    """
    if isinstance(ref, (int, str)) and str(ref).isdigit():
        model = await model_repo.get_model_by_id(int(ref))
        if not model:
            raise HTTPException(404, f"Model {ref} not found")
        return model

    if not isinstance(ref, dict):
        raise HTTPException(400, "Invalid model reference format")

    # Direct model_id / modelId / id in root ref
    root_model_id = ref.get("model_id") or ref.get("modelId")
    if root_model_id:
        model = await model_repo.get_model_by_id(root_model_id)
        if not model:
            raise HTTPException(404, f"Model {root_model_id} not found")
        return model

    platform_data = ref.get("platform", {})
    if not isinstance(platform_data, dict):
        platform_data = {}

    # Extract platform (by ID or Name)
    platform = None
    plat_id = platform_data.get("id") or ref.get("platform_id") or ref.get("platformId")
    plat_name = platform_data.get("name") or ref.get("platform_name")

    if plat_id:
        platform = await platform_repo.get_platform_by_id(plat_id)
        if not platform:
            raise HTTPException(404, f"Platform ID {plat_id} not found")
        updates = {}
        if "apiKey" in platform_data or "api_key" in platform_data:
            updates["api_key"] = platform_data.get("apiKey") or platform_data.get("api_key")
        if "apiType" in platform_data or "api_type" in platform_data:
            updates["api_type"] = platform_data.get("apiType") or platform_data.get("api_type")
        if updates:
            platform = await platform_repo.update_platform(platform["id"], updates)
    elif plat_name:
        platform = await platform_repo.get_platform_by_name(plat_name)
        if platform:
            updates = {}
            if "apiKey" in platform_data or "api_key" in platform_data:
                updates["api_key"] = platform_data.get("apiKey") or platform_data.get("api_key")
            if "apiType" in platform_data or "api_type" in platform_data:
                updates["api_type"] = platform_data.get("apiType") or platform_data.get("api_type")
            if updates:
                platform = await platform_repo.update_platform(platform["id"], updates)
        else:
            platform = await platform_repo.create_platform(
                name=plat_name,
                api_key=platform_data.get("apiKey") or platform_data.get("api_key"),
                api_type=platform_data.get("apiType") or platform_data.get("api_type") or "chat-completions",
            )
    else:
        # Check if direct model payload was sent without platform wrapper
        direct_model_id = ref.get("id")
        if direct_model_id:
            model = await model_repo.get_model_by_id(direct_model_id)
            if model:
                return model

        raise HTTPException(
            400, "Inline model reference requires platform.id or platform.name"
        )

    # Extract model(s) from platform.models, platform.model, ref.models, or ref.model
    models_list = []
    if isinstance(platform_data.get("models"), list):
        models_list = platform_data["models"]
    elif platform_data.get("model"):
        m_val = platform_data["model"]
        models_list = [m_val] if isinstance(m_val, (dict, str, int)) else []
    elif isinstance(ref.get("models"), list):
        models_list = ref["models"]
    elif ref.get("model"):
        m_val = ref["model"]
        models_list = [m_val] if isinstance(m_val, (dict, str, int)) else []

    if not models_list:
        raise HTTPException(
            400, "Inline model reference requires at least one model specification"
        )

    # Resolve or create models under platform
    target_model = None
    for m_item in models_list:
        if isinstance(m_item, (int, str)) and str(m_item).isdigit():
            model = await model_repo.get_model_by_id(int(m_item))
            if model:
                if target_model is None:
                    target_model = model
                continue

        m_data = {"name": m_item} if isinstance(m_item, str) else m_item
        if not isinstance(m_data, dict):
            continue

        m_id = m_data.get("id")
        m_name = m_data.get("name")

        if m_id:
            model = await model_repo.get_model_by_id(m_id)
            if model:
                if "url" in m_data:
                    model = await model_repo.update_model(m_id, {"url": m_data["url"]})
                if target_model is None:
                    target_model = model
                continue

        if not m_name:
            continue

        model = await model_repo.get_model_by_platform_and_name(platform["id"], m_name)
        if model:
            updates = {}
            if "url" in m_data:
                updates["url"] = m_data["url"]
            if updates:
                model = await model_repo.update_model(model["id"], updates)
        else:
            model = await model_repo.create_model(
                platform_id=platform["id"],
                name=m_name,
                url=m_data.get("url"),
            )

        if target_model is None:
            target_model = model

    if not target_model:
        raise HTTPException(400, "Invalid model specification inside inline platform reference")

    return target_model




async def resolve_model_for_purpose(
    purpose: str,
    request_model_ref: dict | None,
    series_id: int,
) -> dict:
    """Full resolution chain per PRD §3.2:

    1. request body model ref → resolve_or_create_model
    2. series override (translation_model_id / extraction_model_id)
    3. settings default (default_translation_model_id / default_extraction_model_id)
    4. 400 error
    """
    # 1. Request body
    if request_model_ref:
        return await resolve_or_create_model(request_model_ref)

    # 2. Series override
    series = await series_repo.get_series_by_id(series_id)
    if not series:
        raise HTTPException(404, f"Series {series_id} not found")

    series_model_id = series.get(f"{purpose}_model_id")
    if series_model_id:
        model = await model_repo.get_model_by_id(series_model_id)
        if model:
            return model

    # 3. Settings default
    settings = await settings_repo.get_settings()
    default_model_id = settings.get(f"default_{purpose}_model_id")
    if default_model_id:
        model = await model_repo.get_model_by_id(default_model_id)
        if model:
            return model

    # 4. Error
    raise HTTPException(
        400,
        f"No {purpose} model configured. Set a default in /settings, "
        f"assign one to the series, or pass model reference in the request.",
    )
