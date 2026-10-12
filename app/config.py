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
    provider_foi_documents_enabled: bool = True
    csv_datasets_config: str = "config/csv_datasets.json"
    catalog_public_base_url: str = "http://127.0.0.1:8000"
    foi_documents_base_url: str = "https://dokumenti.foi.hr/document/"
    foi_documents_timeout_seconds: float = 20.0

    # Authentication is secure-by-default. Disable only for isolated local tests.
    auth_enabled: bool = True
    auth_username: str | None = None
    auth_password_hash: str | None = None
    auth_jwt_secret: str | None = None
    auth_token_ttl_minutes: int = 480
    auth_rate_limit_attempts: int = 5
    auth_rate_limit_window_seconds: int = 900

    # Web/API hardening.
    security_hsts_enabled: bool = False
    resource_fetch_max_bytes: int = 25 * 1024 * 1024
    resource_fetch_timeout_seconds: float = 20.0
    resource_fetch_allowed_ports: str = "80,443"

    # RAG ingestion and maintenance. Automatic re-indexing touches only datasets
    # that were indexed previously and became stale after a new catalog version.
    rag_chunk_size_chars: int = 1200
    rag_chunk_overlap_chars: int = 200
    rag_auto_reindex_enabled: bool = True
    rag_auto_reindex_limit: int = 10

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

    @property
    def allowed_resource_ports(self) -> set[int]:
        ports: set[int] = set()
        for value in self.resource_fetch_allowed_ports.split(","):
            value = value.strip()
            if value:
                ports.add(int(value))
        return ports


@lru_cache
def get_settings() -> Settings:
    return Settings()
