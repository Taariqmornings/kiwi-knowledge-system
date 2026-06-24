from fastapi import APIRouter
from app.models.schemas import AppSettings
from app.core import settings_store

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=AppSettings)
def get_settings():
    """Return current application settings."""
    return settings_store.load()


@router.post("", response_model=AppSettings)
def update_settings(data: AppSettings):
    """Persist application settings."""
    return settings_store.save(data.model_dump())
