from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Adrobot"
    database_url: str = "sqlite:///./adrobot.db"

    keitaro_base_url: str = "https://keitaro-for-tests.etolegko.com"
    keitaro_api_key: str = ""
    keitaro_default_domain_id: int | None = 1813
    keitaro_default_group_id: int | None = 10332
    keitaro_default_traffic_source_id: int | None = 836

    # These values follow the supplied Adrobot test-stand examples.
    google_redirect_url: str = "https://google.com"
    auto_create_tables: bool = False

    request_timeout_seconds: float = Field(default=20.0, gt=0, le=120)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
