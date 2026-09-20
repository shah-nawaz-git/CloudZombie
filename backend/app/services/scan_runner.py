import logging
from threading import Lock, Thread
from uuid import UUID

from sqlalchemy import select

from app.api.errors import ScanConflictError
from app.core.enums import Mode, ScanStatus
from app.persistence.models import Scan
from app.pricing.cache import DbPricingCache
from app.pricing.service import PricingService
from app.scanner.engine import ScanEngine
from app.services.app_context import AppContext
from app.services.provider_factory import build_provider
from app.services.settings_service import SettingsService

logger = logging.getLogger(__name__)


class ScanRunner:
    def __init__(self, context: AppContext) -> None:
        self._context = context
        self._lock = Lock()
        self.current_scan_id: UUID | None = None

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self.current_scan_id is not None

    def start(self, regions: list[str] | None, wait: bool) -> Scan:
        with self._lock:
            if self.current_scan_id is not None:
                raise ScanConflictError("A scan is already running.")
            with self._context.session_factory() as session:
                existing = session.scalar(
                    select(Scan).where(Scan.status == ScanStatus.RUNNING.value).limit(1)
                )
                if existing is not None:
                    raise ScanConflictError("A scan is already running.")
                now = self._context.clock.now()
                scan = Scan(
                    mode=self._context.env.cloudzombie_mode.value,
                    started_at=now,
                    status=ScanStatus.RUNNING.value,
                    requested_regions=regions or [],
                    completed_regions=[],
                    partial_regions=[],
                    failed_regions=[],
                    skipped_regions=[],
                    coverage={},
                    errors=[],
                    created_at=now,
                )
                session.add(scan)
                session.commit()
                scan_id = scan.id
            self.current_scan_id = scan_id
        if wait:
            self._execute(scan_id, regions)
        else:
            Thread(target=self._execute, args=(scan_id, regions), daemon=True).start()
        with self._context.session_factory() as session:
            stored = session.get(Scan, scan_id)
            if stored is None:
                raise RuntimeError(f"Scan {scan_id} disappeared after creation")
            return stored

    def _execute(self, scan_id: UUID, regions: list[str] | None) -> None:
        try:
            with self._context.session_factory() as session:
                app_settings = SettingsService(session, self._context.env).load()
                session.commit()
            provider = build_provider(self._context.env, app_settings, self._context.clock)
            cache = DbPricingCache(
                self._context.session_factory,
                self._context.clock,
                app_settings.pricing_cache_ttl_seconds,
            )
            pricing = PricingService(provider, app_settings, self._context.clock, cache)
            scan = ScanEngine(
                provider,
                self._context.session_factory,
                app_settings,
                pricing,
                self._context.clock,
            ).run_scan(regions, scan_id=scan_id)
            if self._context.env.cloudzombie_mode == Mode.LIVE and scan.account_id:
                self._context.identity_status.refresh(provider, self._context.clock)
        except Exception as exc:
            logger.exception("Scan %s failed unexpectedly", scan_id)
            with self._context.session_factory() as session:
                failed_scan = session.get(Scan, scan_id)
                if failed_scan is not None:
                    failed_scan.status = ScanStatus.FAILED.value
                    failed_scan.finished_at = self._context.clock.now()
                    failed_scan.errors = [
                        {
                            "scope": "scan",
                            "code": "internal_error",
                            "message": f"{type(exc).__name__}: {exc}",
                        }
                    ]
                    session.commit()
        finally:
            with self._lock:
                if self.current_scan_id == scan_id:
                    self.current_scan_id = None
