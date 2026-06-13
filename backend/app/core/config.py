"""应用配置：从环境变量 / .env 读取。所有密钥默认值仅供本地开发，生产必须覆盖。"""

from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_JWT_SECRET = "dev-change-me-please-use-a-32char-min-secret"
_DEFAULT_FERNET_KEY = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---- App ----
    app_name: str = "Invoce API"
    environment: str = "development"

    # ---- Database ----
    database_url: str = "postgresql+asyncpg://invoce:invoce@postgres:5432/invoce"

    # ---- Redis ----
    redis_url: str = "redis://redis:6379/0"

    # ---- Auth ----
    jwt_secret: str = "dev-change-me-please-use-a-32char-min-secret"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440
    # 用于加密 IMAP 授权码的 Fernet 密钥（dev 默认全零，生产必须替换）
    fernet_key: str = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="

    # ---- S3 / R2 ----
    s3_endpoint_url: str | None = None
    s3_region: str = "auto"
    s3_bucket: str = "invoce-invoices"
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    presigned_expire_seconds: int = 60

    # ---- AIGC 网关 ----
    aigc_base_url: str = ""
    aigc_api_key: str = ""
    aigc_model: str = "qwen3.5-plus"

    # ---- IMAP ----
    imap_poll_interval_seconds: int = 1800

    # ---- CORS ----
    cors_origins: list[str] = ["http://localhost:3000"]

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in {"production", "prod"}

    @model_validator(mode="after")
    def _forbid_default_secrets_in_prod(self) -> "Settings":
        if self.is_production and (
            self.jwt_secret == _DEFAULT_JWT_SECRET or self.fernet_key == _DEFAULT_FERNET_KEY
        ):
            raise ValueError("生产环境必须设置非默认的 JWT_SECRET 与 FERNET_KEY")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
