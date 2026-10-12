from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api.auth import router as auth_router
from app.api.rag import router as rag_router
from app.api.resources import router as resources_router
from app.api.routes import router
from app.catalog.service import catalog_store
from app.config import get_settings
from app.security.auth import (
    BearerAuthMiddleware,
    SecurityHeadersMiddleware,
    validate_auth_configuration,
)

settings = get_settings()
repository_root = Path(__file__).resolve().parents[1]
data_directory = repository_root / "data"
web_directory = repository_root / "web"


@asynccontextmanager
async def lifespan(_: FastAPI):
    validate_auth_configuration(settings)

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

# Add bearer protection first, then security headers so headers also wrap auth errors.
app.add_middleware(BearerAuthMiddleware, settings=settings)
app.add_middleware(SecurityHeadersMiddleware, settings=settings)

app.include_router(auth_router)
app.include_router(resources_router)
app.include_router(rag_router)
app.include_router(router)


@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    return RedirectResponse(url="/portal/")


if web_directory.is_dir():
    # The HTML/JS shell is public, but all catalog/resource API calls are protected
    # by bearer authentication when AUTH_ENABLED=true. No catalog data is embedded
    # in the static portal itself.
    app.mount("/portal", StaticFiles(directory=web_directory, html=True), name="portal")

if data_directory.is_dir():
    # Current repository-hosted files are synthetic demo assets. User-registered
    # resources remain at their source and are fetched through the safe resource
    # ingestion path instead of becoming an unrestricted local file server.
    app.mount("/files", StaticFiles(directory=data_directory), name="files")
