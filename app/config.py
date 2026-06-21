from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application configuration loaded from environment variables or a .env file.
    Defaults are suitable for local SQLite development.
    For Cloud Run production, override via environment variables or Secret Manager.
    """

    # --- Database ---
    # Local default: SQLite file. Production: set to a postgres:// URL.
    DATABASE_URL: str = "sqlite:///./app.db"

    # --- JWT Authentication ---
    # IMPORTANT: Override this with a long random string in production.
    # Generate one with: python -c "import secrets; print(secrets.token_hex(32))"
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours

    # --- LLM ---
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3-flash-preview"

    # --- Environment ---
    ENVIRONMENT: str = "local"  # "local" | "production"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
