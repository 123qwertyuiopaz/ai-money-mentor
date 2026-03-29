from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # App
    app_name: str = "AI Money Mentor"
    app_version: str = "1.0.0"
    debug: bool = False
    allowed_origins: list[str] = ["http://localhost:3000", "http://localhost:8080"]

    # NVIDIA NIM
    nvidia_nim_api_key: str = "nvapi-demo"
    nvidia_nim_model: str = "meta/llama-3.1-70b-instruct"
    nvidia_nim_base_url: str = "https://integrate.api.nvidia.com/v1"
    nvidia_nim_max_tokens: int = 2048
    nvidia_nim_temperature: float = 0.3

    # Auth
    secret_key: str = "dev-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440  # 24 hours

    # Database
    database_url: str = "sqlite:///./data/money_mentor.db"


@lru_cache
def get_settings() -> Settings:
    return Settings()
