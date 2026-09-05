from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BIZCHAT_", env_file=".env")

    app_name: str = "BizChat"
    env: str = "local"

    # LLM
    anthropic_api_key: str = ""
    model: str = "claude-sonnet-5"
    max_tokens: int = 2048
    temperature: float = 0.0

    # Persistence for LangGraph checkpoints. Use sqlite locally, Postgres in EKS.
    checkpoint_db: str = "./data/checkpoints.sqlite"

    # Business data source the agent queries. Swap for the real warehouse.
    warehouse_dsn: str = ""

    # CORS origins for the SPA
    cors_origins: list[str] = ["*"]

    # Auth: when running behind API Gateway the JWT is already validated,
    # so the app only needs to trust the forwarded principal header.
    behind_api_gateway: bool = False
    principal_header: str = "x-principal-id"


@lru_cache
def settings() -> Settings:
    return Settings()
