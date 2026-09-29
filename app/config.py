from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    openai_api_key: str = ""
    openai_base_url: str | None = None
    mongodb_uri: str = ""
    database_name: str = "Student_feedback"
    secret_key: str = "change-me-in-production"
    admin_username: str = "admin"
    admin_password: str = ""
    academic_current_week: int = 2
    academic_week_3_start_date: str = "2026-10-05"
    academic_total_weeks: int = 11
    frontend_url: str = "http://localhost:5173"
    environment: str = "development"
    access_token_expire_minutes: int = 60 * 8
    openai_model: str = "gpt-5.4-mini"
    rate_limit_feedback: str = "10/minute"


@lru_cache
def get_settings() -> Settings:
    return Settings()
