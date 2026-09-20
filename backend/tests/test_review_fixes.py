import importlib

from app.core.config import Settings
from app.models import AppSettings
from app.services.provider_factory import build_provider


def test_database_module_has_no_eager_engine() -> None:
    database = importlib.import_module("app.persistence.database")
    assert not hasattr(database, "engine")
    assert not hasattr(database, "SessionLocal")


def test_demo_provider_factory_forces_fallback_pricing(fixed_clock) -> None:
    environment = Settings(CLOUDZOMBIE_MODE="demo")
    app_settings = AppSettings(pricing_mode="auto")
    build_provider(environment, app_settings, fixed_clock)
    assert app_settings.pricing_mode == "fallback_only"
