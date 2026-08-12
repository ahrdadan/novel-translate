"""Unified translate request schemas for the all-in-one endpoint (POST /api/v1/translate-novel)."""

from pydantic import BaseModel, Field

from src.models.system_prompt import SystemPromptReference


class ModelReferenceInput(BaseModel):
    """Flexible model reference: either model_id or inline platform with models array."""
    model_id: int | None = Field(None, alias="modelId")
    platform: dict | None = None
    model: dict | None = None
    models: list[dict] | None = None

    model_config = {"populate_by_name": True}



class InlineSeriesInput(BaseModel):
    """Series reference: either existing series_id or inline series attributes."""
    id: int | None = None
    name: str | None = None
    original_title: str | None = Field(None, alias="originalTitle")
    author: str | None = None
    description: str | None = None

    model_config = {"populate_by_name": True}


class InlineChapterInput(BaseModel):
    """Chapter input: chapter_number and source text or HTML."""
    chapter_number: float = Field(..., alias="chapterNumber")
    title: str | None = None
    source_text: str | None = Field(None, alias="sourceText")
    source_language: str = Field("auto", alias="sourceLanguage")

    model_config = {"populate_by_name": True}


class UnifiedTranslateRequest(BaseModel):
    """Payload for POST /api/v1/translate-novel — all-in-one translation request."""
    series: InlineSeriesInput | int | str
    chapter: InlineChapterInput | int | str
    mode: str = "sync"  # "sync" | "async"
    strategy: str = "pipeline"  # "pipeline" | "single_pass"
    force_translate: bool = Field(False, alias="forceTranslate")
    force_summary: bool = Field(False, alias="forceSummary")
    extract: bool = True
    translation_model: ModelReferenceInput | int | str | dict | list | None = Field(None, alias="translationModel")
    summarize_model: ModelReferenceInput | int | str | dict | list | None = Field(None, alias="summarizeModel")
    extraction_model: ModelReferenceInput | int | str | dict | list | None = Field(None, alias="extractionModel")
    system_prompt: SystemPromptReference | int | str | dict | list | None = Field(None, alias="systemPrompt")
    llm_timeout: int | None = Field(None, alias="llmTimeout")

    model_config = {"populate_by_name": True}


