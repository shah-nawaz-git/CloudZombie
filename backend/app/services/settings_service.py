from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import AppSettings
from app.persistence.models import SettingsRecord


class SettingsService:
    def __init__(self, session: Session, environment: Settings | None = None) -> None:
        self._session = session
        self._environment = environment or Settings()

    def load(self) -> AppSettings:
        record = self._session.get(SettingsRecord, 1)
        if record is None:
            settings = AppSettings(
                regions=self._environment.region_selection,
                pricing_cache_ttl_seconds=self._environment.pricing_cache_ttl,
                pricing_mode=(
                    "fallback_only"
                    if self._environment.cloudzombie_mode.value == "demo"
                    else "auto"
                ),
            )
            self.save(settings)
            return settings
        return AppSettings.model_validate(record.data)

    def save(self, settings: AppSettings) -> None:
        record = self._session.get(SettingsRecord, 1)
        data = settings.model_dump(mode="json")
        if record is None:
            self._session.add(SettingsRecord(id=1, data=data))
        else:
            record.data = data
        self._session.flush()
