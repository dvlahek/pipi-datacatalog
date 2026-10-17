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
    provider_open_data_catalogs_enabled: bool = False
    csv_datasets_config: str = "config/csv_datasets.json"
    open_data_catalogs_config: str = "config/open_data_catalogs.json"
    open_data_catalogs_timeout_seconds: float = 30.0
    catalog_public_base_url: str = "http://127.0.0.1:8000"
    foi_documents_base_url: str = "https://dokumenti.foi.hr/document/"
    foi_documents_timeout_seconds: float = 20.0

    # GitHub repository resources. Public repositories work without a token, but
    # GitHub's unauthenticated API limit is low. Configure a server-side token in
    # production; it is never stored in catalog metadata.
    github_api_token: str | None = None
    github_timeout_seconds: float = 20.0
    github_index_max_files: int = 100
    github_index_max_file_bytes: int = 256 * 1024
    github_index_max_total_bytes: int = 3 * 1024 * 1024

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

    # Vector retrieval. `feature-hash` remains a dependency-free plumbing baseline.
    # `multilingual-e5` enables neural semantic retrieval through Sentence Transformers.
    # A model revision can be pinned for reproducibility; changing model/revision
    # produces a different embedding identity and therefore triggers a new backfill.
    # `metadata-v1` enriches passage input with dataset title and, when available,
    # GitHub file_path. The non-default profile becomes part of the vector identity.
    rag_embedding_provider: str = "feature-hash"
    rag_embedding_model: str = "feature-hash-384-v1"
    rag_embedding_revision: str | None = None
    rag_embedding_dimensions: int = 384
    rag_embedding_device: str = "auto"
    rag_embedding_batch_size: int = 128
    rag_embedding_backfill_limit: int = 10000
    rag_embedding_input_profile: str = "content-v1"
    rag_hybrid_rrf_k: int = 60
    # GitHub repositories are one catalog Dataset containing many source files.
    # Prefer at most this many results per file before backfilling from duplicates.
    rag_source_diversity_max_per_file: int = 2

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
