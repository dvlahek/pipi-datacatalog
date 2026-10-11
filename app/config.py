from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "PiPi Data Catalog"
    app_environment: str = "development"

    sensor_hub_base_url: str = "http://webtesting.foi.unizg.hr:3000/api/v1"
    sensor_hub_username: str | None = None
    sensor_hub_password: str | None = None
    sensor_hub_timeout_seconds: float = 15.0

    # Provider registration. Providers can be disabled independently.
    provider_sensor_hub_enabled: bool = True
    provider_static_web_enabled: bool = True
    provider_csv_enabled: bool = True
    csv_datasets_config: str = "config/csv_datasets.json"
    catalog_public_base_url: str = "http://127.0.0.1:8000"

    # Persistent catalog metadata store. Source payloads/readings are not copied.
    catalog_store_enabled: bool = False
    database_url: str | None = None
    database_admin_url: str | None = None
    catalog_bootstrap_if_empty: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def sensor_hub_configured(self) -> bool:
        return bool(self.sensor_hub_username and self.sensor_hub_password)

    @property
    def catalog_store_configured(self) -> bool:
        return bool(self.catalog_store_enabled and self.database_url)


@lru_cache
def get_settings() -> Settings:
    return Settings()
