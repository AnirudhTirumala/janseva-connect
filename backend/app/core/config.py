```python
import os
import secrets
from pathlib import Path
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    PROJECT_NAME: str = "Smart Community Management Platform"
    API_V1_PREFIX: str = "/api"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    TESTING: bool = os.getenv("TESTING", "false").lower() == "true"

    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./panchayat.db")

    SECRET_KEY: str = os.getenv("SECRET_KEY", secrets.token_hex(32))
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))

    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

    SMTP_HOST: str = os.getenv("SMTP_HOST", "")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM_NAME: str = os.getenv("SMTP_FROM_NAME", "JanSeva Connect")

    EMAIL_API_URL: str = os.getenv("EMAIL_API_URL", "")
    EMAIL_API_SECRET: str = os.getenv("EMAIL_API_SECRET", "")

    OTP_EXPIRY_MINUTES: int = int(os.getenv("OTP_EXPIRY_MINUTES", "10"))

    RESEND_API_KEY: str = os.getenv("RESEND_API_KEY", "")
    RESEND_FROM_EMAIL: str = os.getenv("RESEND_FROM_EMAIL", "")

    # Supabase Storage
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_SERVICE_ROLE_KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    SUPABASE_DOCUMENTS_BUCKET: str = os.getenv("SUPABASE_DOCUMENTS_BUCKET", "documents")
    SUPABASE_CERTIFICATES_BUCKET: str = os.getenv("SUPABASE_CERTIFICATES_BUCKET", "certificates")

    # Kept for local development/backward compatibility.
    # Render production storage uses Supabase Storage instead.
    STORAGE_PATH: str = os.getenv("STORAGE_PATH", "")

    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "http://localhost:5173")
    ALLOWED_HOSTS: str = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")

    @property
    def cors_origins_list(self) -> List[str]:
        return [
            origin.strip()
            for origin in self.CORS_ORIGINS.split(",")
            if origin.strip()
        ]

    @property
    def allowed_hosts_list(self) -> List[str]:
        return [
            host.strip()
            for host in self.ALLOWED_HOSTS.split(",")
            if host.strip()
        ]

    @property
    def secret_key_is_configured(self) -> bool:
        return bool(os.getenv("SECRET_KEY"))

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"

    @property
    def supabase_storage_is_configured(self) -> bool:
        return bool(
            self.SUPABASE_URL.strip()
            and self.SUPABASE_SERVICE_ROLE_KEY.strip()
            and self.SUPABASE_DOCUMENTS_BUCKET.strip()
            and self.SUPABASE_CERTIFICATES_BUCKET.strip()
        )

    @property
    def storage_path(self) -> Path:
        if self.STORAGE_PATH.strip():
            return Path(self.STORAGE_PATH).expanduser().resolve()
        return (Path(__file__).resolve().parents[1] / "storage").resolve()

    class Config:
        env_file = ".env"


settings = Settings()
```
