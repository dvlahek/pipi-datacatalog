from fastapi import FastAPI

from app.api.routes import router
from app.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description=(
        "Semantic metadata catalog for PiPi. The first integration harvests "
        "metadata from the PiPi Sensor Hub API."
    ),
)
app.include_router(router)
