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

    # ---- 出站发件 SMTP（一键发送报销单）----
    smtp_host: str = ""  # 如 smtp.example.com；为空则发送功能禁用（端点 503）
    smtp_port: int = 465
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_use_ssl: bool = True  # 465 隐式 TLS；用 587 STARTTLS 时设为 False
    outbound_from_address: str = ""  # 发件地址（如 noreply@invoce.vpanel.cc）；空则回退 smtp_user
    outbound_from_name: str = "发票助手"
    # 导出 ZIP ≤ 此阈值直接当附件；超过则正文改放下载链接（默认 15 MB）
    email_attach_max_bytes: int = 15 * 1024 * 1024
    # 大附件场景的下载链接时效（R2/S3 预签名上限 7 天）
    email_link_expire_seconds: int = 7 * 24 * 3600

    @property
    def outbound_enabled(self) -> bool:
        return bool(self.smtp_host)

    @property
    def from_address(self) -> str:
        return self.outbound_from_address or self.smtp_user

    # ---- Telegram Bot ----
    telegram_bot_token: str = ""  # @BotFather 颁发；为空则功能禁用
    telegram_bot_username: str = ""  # 不含 @，用于生成绑定深链 t.me/<username>?start=<code>
    telegram_webhook_secret: str = ""  # webhook 校验 X-Telegram-Bot-Api-Secret-Token
    telegram_api_base: str = "https://api.telegram.org"  # 可覆盖便于测试

    @property
    def telegram_enabled(self) -> bool:
        return bool(self.telegram_bot_token)

    # ---- 专属收票邮箱(入站) ----
    inbound_email_domain: str = ""  # 如 invoce.vpanel.cc；为空则功能禁用
    inbound_webhook_secret: str = ""  # Cloudflare Email Worker → 后端 webhook 的共享密钥

    @property
    def inbound_enabled(self) -> bool:
        return bool(self.inbound_email_domain)

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
        # 启用收票域却没给够强度的 webhook 密钥 → 端点会静默对所有请求 401，必须拦在启动期
        if self.is_production and self.inbound_enabled and len(self.inbound_webhook_secret) < 32:
            raise ValueError("启用收票邮箱后,生产环境必须设置长度 ≥ 32 的 INBOUND_WEBHOOK_SECRET")
        # 启用出站发件却缺凭证/发件人 → 发送任务必失败，拦在启动期更早暴露配置问题
        if (
            self.is_production
            and self.outbound_enabled
            and not (self.smtp_user and self.smtp_password and self.from_address)
        ):
            raise ValueError("启用发件后,生产环境必须设置 SMTP_USER / SMTP_PASSWORD 与发件地址")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
