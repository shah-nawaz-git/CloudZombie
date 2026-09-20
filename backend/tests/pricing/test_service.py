from app.core.enums import CostConfidence
from app.models import AppSettings, EbsVolumePricingRequest
from app.pricing.service import PricingService
from app.providers.errors import ProviderTransientError


class EmptyProvider:
    def get_prices(self, service_code, filters):
        return []


class TransientProvider:
    def get_prices(self, service_code, filters):
        raise ProviderTransientError("pricing unavailable")


def request():
    return EbsVolumePricingRequest(region="us-east-1", volume_type="gp2", size_gib=100)


def test_missing_api_product_falls_back_with_warning(fixed_clock) -> None:
    result = PricingService(
        EmptyProvider(), AppSettings(pricing_mode="auto"), fixed_clock
    ).estimate(request())
    assert result.source == "fallback_table"
    assert result.warnings and "PricingLookupError" in result.warnings[0]


def test_provider_error_falls_back_with_warning(fixed_clock) -> None:
    result = PricingService(
        TransientProvider(), AppSettings(pricing_mode="auto"), fixed_clock
    ).estimate(request())
    assert result.source == "fallback_table"
    assert result.warnings and "ProviderTransientError" in result.warnings[0]


def test_disabled_is_unavailable(fixed_clock) -> None:
    result = PricingService(None, AppSettings(pricing_mode="disabled"), fixed_clock).estimate(
        request()
    )
    assert result.cost_confidence == CostConfidence.UNAVAILABLE
    assert result.source == "unavailable"


def test_estimate_never_raises_when_all_backends_fail(fixed_clock) -> None:
    service = PricingService(EmptyProvider(), AppSettings(pricing_mode="auto"), fixed_clock)

    def explode(selected):
        raise RuntimeError("boom")

    service._api.estimate = explode
    service._fallback.estimate = explode
    result = service.estimate(request())
    assert result.cost_confidence == CostConfidence.UNAVAILABLE
    assert len(result.warnings) == 2
