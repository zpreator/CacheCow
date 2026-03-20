from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    download_path: str = "/app/downloads"
    port: int = 8501
    # Auth - reads APP_USER/APP_PASS_HASH from .env
    # Default hash is sha256("admin") — change via Settings page or APP_PASS_HASH env var
    app_user: str = "admin"
    app_pass_hash: str = "8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918"
    secret_key: str = "change-me-in-production"
    redis_url: str = "redis://localhost:6379/0"
    database_url: str = "sqlite:///data/cachecow.db"


settings = AppSettings()
