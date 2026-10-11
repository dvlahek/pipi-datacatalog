from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.catalog.service import catalog_store
from app.config import get_settings

settings = get_settings()
repository_root = Path(__file__).resolve().parents[1]
data_directory = repository_root / "data"


@asynccontextmanager
async def lifespan(_: FastAPI):
    # When persistence is enabled, initialization is version-aware and idempotent.
    # It creates the target database/role if DATABASE_ADMIN_URL is available and
    # applies only pending SQL migrations before the API begins serving requests.
    if settings.catalog_store_enabled:
        catalog_store(settings)
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description=(
        "Semantic metadata catalog for PiPi with provider-neutral datasets, "
        "persistent metadata, versioning and semantic access."
    ),
    lifespan=lifespan,
)
app.include_router(router)

if data_directory.is_dir():
    app.mount("/files", StaticFiles(directory=data_directory), name="files")
