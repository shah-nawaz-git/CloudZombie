from collections.abc import Callable
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.clock import Clock, FixedClock
from app.core.config import Settings
from app.persistence.models import Scan
from app.pricing.service import PricingService
from app.providers.demo import DemoProvider, load_demo_dataset
from app.scanner.engine import ScanEngine
from app.services.settings_service import SettingsService


class DemoSeeder:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        env_settings: Settings,
        clock: Clock,
    ) -> None:
        self._session_factory = session_factory
        self._env = env_settings
        self._clock = clock

    def seed_if_empty(self) -> bool:
        with self._session_factory() as session:
            if session.scalar(select(func.count()).select_from(Scan)):
                return False
            service = SettingsService(session, self._env)
            app_settings = service.load()
            anchor = self._clock.now()
            app_settings.demo_anchor_at = anchor
            app_settings.pricing_mode = "fallback_only"
            service.save(app_settings)
            session.commit()
        dataset = load_demo_dataset()
        for step, days_before in ((1, 21), (2, 14), (3, 7), (4, 2)):
            fixed = FixedClock(anchor - timedelta(days=days_before))
            provider = DemoProvider(dataset, step, anchor)
            pricing = PricingService(provider, app_settings, fixed)
            scan = ScanEngine(
                provider, self._session_factory, app_settings, pricing, fixed
            ).run_scan()
            with self._session_factory() as session:
                stored = session.get(Scan, scan.id)
                if stored is None:
                    raise RuntimeError(f"Seeded scan {scan.id} disappeared")
                stored.seeded = True
                session.commit()
        return True
