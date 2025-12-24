"""Application configuration using pydantic-settings."""

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and config files."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App Info
    app_name: str = "Edge Backend API"
    app_version: str = "0.1.0"
    debug: bool = False

    # Server
    host: str = "0.0.0.0"
    port: int = 8400
    workers: int = 1

    # Database
    data_save_folder: str = "/opt/autocare/dx/volume/DxApi"
    db_file: str = "DxApi.db"

    @property
    def database_url(self) -> str:
        """SQLite database URL."""
        db_path = Path(self.data_save_folder) / self.db_file
        return f"sqlite+aiosqlite:///{db_path}"

    # JWT Authentication
    jwt_secret_key: str = Field(
        default="DhftOS5uphK3vmCJQrexST1RsyjZBjXWRgJMFPU4",
        alias="JWT_SECRET_KEY",
    )
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60 * 24  # 24 hours
    jwt_issuer: str = "https://localhost:8000/"
    jwt_audience: str = "https://localhost:8000/"

    # NATS
    nats_uri: str = Field(default="nats://localhost:4222", alias="NATS_URI")

    # gRPC (Core/Detector)
    core_grpc_server: str = Field(
        default="127.0.0.1:50051",
        alias="CORE_GRPC_SERVER",
    )

    # ViveEX (Mx) Backend
    backend_base: str = Field(
        default="https://localhost:7001",
        alias="BACKEND_BASE",
    )
    bearer_token: str | None = Field(default=None, alias="BEARER_TOKEN")
    basic_user: str = Field(default="admin", alias="BASIC_USER")
    basic_pass: str = Field(default="autocare1!", alias="BASIC_PASS")

    # Static Files
    static_file_path: str = "/opt/autocare/dx/hls"

    # DX Config File
    dx_cfg_path: str = "/opt/autocare/dx/volume/config/dx.cfg"

    # Aggregation
    aggregation_primary_url: str = "http://localhost:8400"
    aggregation_secondary_url: str = "http://localhost:8401"

    # CORS
    cors_origins: list[str] = ["*"]
    cors_allow_methods: list[str] = ["*"]
    cors_allow_headers: list[str] = ["*"]

    # Retention Settings
    event_retention_days: int = 30
    image_retention_days: int = 7

    # Core Services (gRPC, NATS, Workers)
    # Set to False to disable connections to Core for frontend/backend only testing
    enable_core_services: bool = Field(
        default=False,
        alias="ENABLE_CORE_SERVICES",
    )

    # MediaMTX (RTSP to HLS/WebRTC streaming server)
    mediamtx_api_url: str = Field(
        default="http://localhost:9997/v3",
        alias="MEDIAMTX_API_URL",
        description="MediaMTX REST API URL",
    )
    mediamtx_hls_url: str = Field(
        default="http://localhost:8888",
        alias="MEDIAMTX_HLS_URL",
        description="MediaMTX HLS streaming URL",
    )
    mediamtx_webrtc_url: str = Field(
        default="http://localhost:8889",
        alias="MEDIAMTX_WEBRTC_URL",
        description="MediaMTX WebRTC streaming URL",
    )
    mediamtx_enabled: bool = Field(
        default=True,
        alias="MEDIAMTX_ENABLED",
        description="Enable MediaMTX integration for camera streaming",
    )

    @field_validator("core_grpc_server", mode="before")
    @classmethod
    def strip_http_prefix(cls, v: str) -> str:
        """Remove http:// prefix if present for gRPC address."""
        if v.startswith("http://"):
            return v[7:]
        if v.startswith("https://"):
            return v[8:]
        return v


class DxConfig:
    """DX configuration loaded from YAML file (dx.cfg)."""

    def __init__(self, config_path: str | None = None):
        self._config: dict[str, Any] = {}
        if config_path:
            self.load(config_path)

    def load(self, config_path: str) -> None:
        """Load configuration from YAML file."""
        path = Path(config_path)
        if path.exists():
            with open(path) as f:
                self._config = yaml.safe_load(f) or {}

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by key."""
        return self._config.get(key, default)

    @property
    def api_port(self) -> int:
        """Get API port from dx.cfg."""
        return self._config.get("port_api", 8400)

    @property
    def nats_port(self) -> int:
        """Get NATS port from dx.cfg."""
        return self._config.get("port_nats", 4422)

    @property
    def launcher_port(self) -> int:
        """Get launcher port from dx.cfg."""
        return self._config.get("port_launcher", 8500)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


@lru_cache
def get_dx_config() -> DxConfig:
    """Get cached DX config instance."""
    settings = get_settings()
    return DxConfig(settings.dx_cfg_path)
