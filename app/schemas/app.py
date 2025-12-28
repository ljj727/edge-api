"""App schemas for API request/response."""

from typing import Any

from pydantic import BaseModel, Field


class OutputClassifier(BaseModel):
    """App output classifier schema."""

    class_type: str = Field(..., alias="classType")
    result_labels: list[str] = Field(default_factory=list, alias="resultLabels")

    model_config = {"populate_by_name": True}


class Output(BaseModel):
    """App output schema."""

    label: str
    classifiers: list[OutputClassifier] = []


class AppModel(BaseModel):
    """App model schema."""

    id: str
    name: str
    version: str | None = None
    capacity: int | None = None
    precision: str | None = None
    desc: str | None = None
    path: str | None = None
    model_memory_usage: int | None = Field(None, alias="model_memory_usage")
    model_performance: float | None = Field(None, alias="model_performance")

    model_config = {"populate_by_name": True}


class AppPropertyPipeline(BaseModel):
    """App property pipeline schema."""

    name: str
    type: str | None = None
    properties: dict[str, Any] = {}
    attributes: dict[str, Any] = {}


class AppProperty(BaseModel):
    """App property schema."""

    pipeline: list[AppPropertyPipeline] = []


class AppDTO(BaseModel):
    """App response schema."""

    id: str
    desc: str | None = None
    name: str
    version: str | None = None
    framework: str | None = None
    compute_capability: str | None = Field(None, alias="compute_capability")
    platform: str | None = None
    evgen_path: str | None = Field(None, alias="evgen_path")
    models: list[AppModel] = []
    outputs: list[Output] = []
    properties: AppProperty | None = None
    app_memory_usage: int | None = Field(None, alias="app_memory_usage")
    app_max_fps: float | None = Field(None, alias="app_max_fps")

    model_config = {"populate_by_name": True}


class AppSyncResponse(BaseModel):
    """Schema for app sync response."""

    success: bool
    message: str
    added: int = 0
    updated: int = 0
    deleted: int = 0
