from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AgentOps RAG"
    app_version: str = "0.1.0"
    environment: str = "development"
    log_level: str = "INFO"

    database_url: str = Field(
        default="postgresql+psycopg://agentops:agentops@localhost:5432/agentops_rag"
    )
    redis_url: str = "redis://localhost:6379/0"
    opensearch_url: str = "http://localhost:9200"

    jwt_secret_key: str = "dev-only-change-me"
    jwt_algorithm: str = "HS256"
    demo_token_ttl_minutes: int = 60

    model_provider: str = "fake"
    embedding_provider: str = "fake"

    tracing_enabled: bool = True
    tracing_console_exporter: bool = True

    rate_limit_ask_limit: int = 60
    rate_limit_documents_limit: int = 20
    rate_limit_evals_limit: int = 5
    rate_limit_window_seconds: int = 60

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
