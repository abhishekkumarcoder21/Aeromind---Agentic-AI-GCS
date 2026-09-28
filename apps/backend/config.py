"""Application configuration loaded from environment variables.

Uses pydantic-settings for typed, validated config with sensible defaults.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings — loaded from environment variables or .env file."""

    # ── Database ──
    database_url: str = "postgresql+asyncpg://aeromind:aeromind@localhost:5432/aeromind"
    database_url_sync: str = "postgresql://aeromind:aeromind@localhost:5432/aeromind"

    # ── Redis ──
    redis_url: str = "redis://localhost:6379/0"

    # ── LLM ──
    llm_api_key: str = ""
    llm_model: str = "gpt-4o"
    llm_base_url: str = "https://api.openai.com/v1"

    # ── Simulator ──
    telemetry_interval_ms: int = 1000
    heartbeat_interval_ms: int = 2000
    heartbeat_timeout_seconds: int = 10
    initial_uav_count: int = 8

    # ── Safety ──
    min_battery_percent: float = 25.0
    min_separation_meters: float = 50.0
    min_gps_satellites: int = 6
    min_signal_strength: float = -80.0
    geofence_enabled: bool = True

    # ── Server ──
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:3000,http://frontend:3000"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance."""
    return Settings()
