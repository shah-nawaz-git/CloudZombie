from dataclasses import dataclass
from datetime import datetime
from threading import Lock
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from app.core.clock import Clock
from app.core.config import Settings
from app.providers.base import CloudProvider, Identity
from app.providers.errors import ProviderError


@dataclass
class IdentityStatus:
    mode: str
    account_id: str | None = None
    principal_arn: str | None = None
    identity_type: str | None = None
    verified_at: datetime | None = None
    error: str | None = None

    def __post_init__(self) -> None:
        self._lock = Lock()

    def refresh(self, provider: CloudProvider, clock: Clock) -> None:
        try:
            identity = provider.get_identity()
        except ProviderError as exc:
            with self._lock:
                self.error = str(exc)
                self.verified_at = clock.now()
            return
        self.update(identity, clock.now())

    def update(self, identity: Identity, verified_at: datetime) -> None:
        with self._lock:
            self.account_id = identity.account_id
            self.principal_arn = identity.principal_arn
            self.identity_type = identity.identity_type
            self.verified_at = verified_at
            self.error = None


@dataclass
class AppContext:
    env: Settings
    clock: Clock
    session_factory: sessionmaker[Session]
    provider: CloudProvider
    identity_status: IdentityStatus
    version: str
    scan_runner: Any | None = None
