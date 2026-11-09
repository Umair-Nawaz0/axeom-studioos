import os
from datetime import date
from urllib.parse import urlparse, unquote

# Simple zero-dependency .env file loader
def _load_env_files():
    candidates = [
        os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"),
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"),
    ]
    for p in candidates:
        if os.path.isfile(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            k = k.strip()
                            v = v.strip().strip("'\"")
                            if k not in os.environ:
                                os.environ[k] = v
            except Exception:
                pass

_load_env_files()


class Settings:
    # Challenge reference date (Oct 6, 2026) - deterministic, configurable via env for QA tests
    REFERENCE_DATE: date = date.fromisoformat(os.getenv("REFERENCE_DATE", "2026-10-06"))

    # Database configuration
    DATABASE_URL: str = os.getenv("DATABASE_URL", "").strip()

    if DATABASE_URL:
        _u = urlparse(DATABASE_URL)
        DB_NAME: str = _u.path.lstrip("/") or os.getenv("DB_NAME", "axeom_db")
        DB_USER: str = unquote(_u.username) if _u.username else os.getenv("DB_USER", "umair")
        DB_PASSWORD: str = unquote(_u.password) if _u.password else os.getenv("DB_PASSWORD", "")
        DB_HOST: str = _u.hostname or os.getenv("DB_HOST", "")
        DB_PORT: int = _u.port or int(os.getenv("DB_PORT", "5432"))
        DB_SSLMODE: str = os.getenv("DB_SSLMODE", "require")
    else:
        DB_NAME: str = os.getenv("DB_NAME", "axeom_db")
        DB_USER: str = os.getenv("DB_USER", "umair")
        DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")
        DB_HOST: str = os.getenv("DB_HOST", "")  # empty string defaults to Unix domain socket
        DB_PORT: int = int(os.getenv("DB_PORT", "5432"))
        DB_SSLMODE: str = os.getenv("DB_SSLMODE", "")
    DB_SCHEMA: str = os.getenv("DB_SCHEMA", "public")

    # Google Gemini API configuration (Gemini is the ONLY AI provider for message classification)
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
    GEMINI_BATCH_SIZE: int = int(os.getenv("GEMINI_BATCH_SIZE", "15"))
    GEMINI_AUTO_CLASSIFY: bool = os.getenv("GEMINI_AUTO_CLASSIFY", "false").lower() in ("true", "1", "yes")
    GEMINI_MAX_RETRIES: int = int(os.getenv("GEMINI_MAX_RETRIES", "3"))

    # Legacy TypeSafe Jev references removed per prompt (Gemini is the ONLY AI provider)
    TYPESAFE_API_KEY: str = ""
    TYPESAFE_BASE_URL: str = ""
    TYPESAFE_MODEL: str = ""
    JEV_API_KEY: str = ""
    JEV_BASE_URL: str = ""

    # App config
    PROJECT_NAME: str = "Axeom StudioOS Backend"
    VERSION: str = "2.0.0"


settings = Settings()
