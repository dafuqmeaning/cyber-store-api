from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Cyber Store API"
    database_path: str = "data/store.sqlite3"
    telegram_bot_token: str = "change-me"
    session_secret: str = "change-me-too"
    session_ttl_seconds: int = 60 * 60 * 24 * 7
    allow_demo_auth: bool = True
    cors_origins: str = "http://localhost:5173,http://localhost:8080,http://127.0.0.1:8080"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
