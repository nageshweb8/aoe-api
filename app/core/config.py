from __future__ import annotations

from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration loaded from environment variables / .env file."""

    app_name: str = "AOE API"
    app_env: str = "development"
    app_port: int = 8000
    frontend_url: str = "http://localhost:3000"
    max_upload_size_mb: int = 10

    # OpenAI
    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4.1-mini", alias="OPENAI_MODEL")
    openai_max_tokens: int = Field(default=2000, alias="OPENAI_MAX_TOKENS")
    openai_timeout: int = Field(default=60, alias="OPENAI_TIMEOUT")

    # Database (Azure SQL via ODBC or SQLite for local dev)
    database_url: str = Field(
        default="sqlite+aiosqlite:///./aoe_dev.db",
        alias="DATABASE_URL",
    )

    # Multi-tenancy default
    default_client_id: str = Field(default="default", alias="DEFAULT_CLIENT_ID")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "populate_by_name": True,
    }

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def ai_enabled(self) -> bool:
        """AI features are available only when an OpenAI key is configured."""
        return bool(self.openai_api_key)


settings = Settings()
