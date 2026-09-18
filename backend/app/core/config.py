import os
import secrets
from pathlib import Path
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """
    Central application configuration.
    Values are read from environment variables (see .env.example).
    Falls back to sane local-dev defaults so the app runs out of the box.
    """

    PROJECT_NAME: str = "Smart Community Management Platform"
    API_V1_PREFIX: str = "/api"

    # "development" (default) or "production". In production, insecure
    # fallback defaults (like the SECRET_KEY below) are refused rather
    # than silently used - see the check in main.py at startup.
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    TESTING: bool = os.getenv("TESTING", "false").lower() == "true"

    # Database: defaults to local sqlite file if not provided (easy local dev),
    # use Postgres in production via DATABASE_URL env var.
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./panchayat.db")

    # Auth. The fallback here is intentionally random-per-process (not a
    # fixed string) so that even if someone forgets to set SECRET_KEY in
    # a quick local test, they don't end up on a publicly-known key - but
    # production deployments must still set a real one explicitly (enforced
    # at startup) since a random-per-process key invalidates all sessions
    # on every restart.
    SECRET_KEY: str = os.getenv("SECRET_KEY", secrets.token_hex(32))
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))

    # AI Assistant
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    # Groq periodically retires older models (see https://console.groq.com/docs/deprecations).
    # llama-3.3-70b-versatile was shut down 08/16/26; openai/gpt-oss-120b is Groq's
    # recommended replacement. Override via .env if Groq deprecates this one too.
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

    # Email OTP (for citizen passwordless login)
    SMTP_HOST: str = os.getenv("SMTP_HOST", "")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM_NAME: str = os.getenv("SMTP_FROM_NAME", "JanSeva Connect")
    OTP_EXPIRY_MINUTES: int = int(os.getenv("OTP_EXPIRY_MINUTES", "10"))

    # Files containing citizen identity documents and generated certificates
    # must live on durable storage in production.  The empty default is
    # intentional: main.py refuses a production boot until the deployer has
    # explicitly mounted/configured persistent storage.
    STORAGE_PATH: str = os.getenv("STORAGE_PATH", "")

    # CORS - kept as a plain comma-separated string field on purpose.
    # pydantic-settings tries to JSON-parse any field typed as List[...]
    # when it's loaded from .env, which breaks on a plain comma-separated
    # value like "http://a.com,http://b.com" (not valid JSON). Splitting
    # it ourselves via the property below avoids that entirely.
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "http://localhost:5173")
    # Comma-separated hostnames accepted by Starlette's Host-header guard.
    # In production this must contain the API domain(s), never "*".
    ALLOWED_HOSTS: str = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def allowed_hosts_list(self) -> List[str]:
        return [host.strip() for host in self.ALLOWED_HOSTS.split(",") if host.strip()]

    @property
    def secret_key_is_configured(self) -> bool:
        return bool(os.getenv("SECRET_KEY"))

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"

    @property
    def storage_path(self) -> Path:
        """Configured persistent storage, with a harmless local-dev fallback."""
        if self.STORAGE_PATH.strip():
            return Path(self.STORAGE_PATH).expanduser().resolve()
        return (Path(__file__).resolve().parents[1] / "storage").resolve()

    class Config:
        env_file = ".env"


settings = Settings()
