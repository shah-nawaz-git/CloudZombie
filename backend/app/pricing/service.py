from typing import Protocol

from app.core.clock import Clock
from app.core.enums import CostConfidence
from app.models import AppSettings, PricingRequest, PricingResult
from app.pricing.aws_api import AwsPricingApiBackend
from app.pricing.cache import InMemoryPricingCache, PricingCache
from app.pricing.fallback import FallbackTableBackend
from app.providers.base import CloudProvider


class PricingBackend(Protocol):
    def estimate(self, request: PricingRequest) -> PricingResult: ...


class PricingService:
    def __init__(
        self,
        provider: CloudProvider | None,
        settings: AppSettings,
        clock: Clock,
        cache: PricingCache | None = None,
    ) -> None:
        self._settings = settings
        selected_cache = cache or InMemoryPricingCache(clock, settings.pricing_cache_ttl_seconds)
        self._api = (
            AwsPricingApiBackend(provider, clock, selected_cache) if provider is not None else None
        )
        self._fallback: PricingBackend = FallbackTableBackend()

    def estimate(self, request: PricingRequest) -> PricingResult:
        if self._settings.pricing_mode == "disabled":
            return PricingResult(
                estimated_monthly_cost=None,
                cost_confidence=CostConfidence.UNAVAILABLE,
                explanation="Pricing is disabled.",
                source="unavailable",
                pricing_timestamp=None,
                line_items=[],
            )
        warnings: list[str] = []
        backends: list[PricingBackend] = []
        if self._settings.pricing_mode == "auto" and self._api is not None:
            backends.append(self._api)
        backends.append(self._fallback)
        for backend in backends:
            try:
                result = backend.estimate(request)
                return result.model_copy(update={"warnings": [*warnings, *result.warnings]})
            except Exception as exc:
                warnings.append(f"{type(exc).__name__}: {exc}")
        return PricingResult(
            estimated_monthly_cost=None,
            cost_confidence=CostConfidence.UNAVAILABLE,
            explanation="Pricing is unavailable.",
            source="unavailable",
            pricing_timestamp=None,
            line_items=[],
            warnings=warnings,
        )


__all__ = ["FallbackTableBackend", "PricingBackend", "PricingService"]
