from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    download_path: str = "/app/downloads"
    port: int = 8501
    # Auth - reads APP_USER/APP_PASS_HASH from .env
    app_user: str = "admin"
    app_pass_hash: str = ""
    secret_key: str = "change-me-in-production"
    redis_url: str = "redis://localhost:6379/0"
    database_url: str = "sqlite:///data/cachecow.db"


settings = AppSettings()
