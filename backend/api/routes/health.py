from fastapi import APIRouter
from backend.core.personality import get_active_personality_config, PersonalityConfig
from backend.core.system_metrics import get_system_metrics

router = APIRouter()

@router.get("/health")
def health_check():
    return {"status": "ok"}

@router.get("/personality")
def get_personality():
    """Returns the currently active personality configuration."""
    config = get_active_personality_config()
    return {
        "name": config.name,
        "display_name": config.display_name,
        "tagline": config.tagline,
        "ui_config": config.ui,
        "loaded_at": config.loaded_at
    }

@router.get("/system/metrics")
def system_metrics():
    """Returns live system metrics: CPU, RAM, GPU usage, and GPU temperature."""
    return get_system_metrics()
