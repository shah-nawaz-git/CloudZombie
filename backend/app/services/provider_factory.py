from app.core.clock import Clock
from app.core.config import Settings
from app.core.enums import Mode
from app.models import AppSettings
from app.providers.base import CloudProvider
from app.providers.demo import DemoProvider, load_demo_dataset


def build_provider(settings: Settings, app_settings: AppSettings, clock: Clock) -> CloudProvider:
    if settings.cloudzombie_mode == Mode.DEMO:
        app_settings.pricing_mode = "fallback_only"
        anchor = app_settings.demo_anchor_at or clock.now()
        return DemoProvider(load_demo_dataset(), step=5, anchor=anchor)
    raise NotImplementedError("live provider arrives in Phase 13")
