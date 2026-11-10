import os
from pathlib import Path

try:
    from pydantic_settings import BaseSettings
except ImportError:
    from pydantic import BaseSettings

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DEFAULT_DB_PATH = REPO_ROOT / "continuity.db"
DEFAULT_STORAGE_DIR = REPO_ROOT / "storage"


class Settings(BaseSettings):
    CONTRACT_VERSION: str = "1.0.0"
    APP_VERSION: str = "1.0.0"

    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH}")
    JWT_SECRET: str = os.getenv("JWT_SECRET", "demo-super-secret-key-for-continuity-ai-2026")
    JWT_EXPIRES_HOURS: int = int(os.getenv("JWT_EXPIRES_HOURS", "8"))
    STORAGE_DIR: str = os.getenv("STORAGE_DIR", str(DEFAULT_STORAGE_DIR))
    MAX_UPLOAD_BYTES: int = int(os.getenv("MAX_UPLOAD_BYTES", "10485760"))  # 10 MB

    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "fake")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "fake-model-v1")
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    LLM_TIMEOUT_SECONDS: int = int(os.getenv("LLM_TIMEOUT_SECONDS", "60"))
    LLM_MAX_RETRIES: int = int(os.getenv("LLM_MAX_RETRIES", "2"))

    GITHUB_MODE: str = os.getenv("GITHUB_MODE", "fixture")  # fixture or live
    GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")

    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "*")
    EXTRACT_RESTRICTED: bool = os.getenv("EXTRACT_RESTRICTED", "false").lower() == "true"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
