from collections.abc import Mapping
from dataclasses import dataclass

from app.models import AppSettings


@dataclass(frozen=True)
class IgnoreDecision:
    ignored: bool
    reason: str | None = None


def evaluate_ignore(tags: Mapping[str, str], settings: AppSettings) -> IgnoreDecision:
    value = tags.get(settings.ignore_tag_key)
    ignored = value is not None and value.casefold() == settings.ignore_tag_value.casefold()
    if not ignored:
        return IgnoreDecision(False)
    return IgnoreDecision(True, tags.get(settings.ignore_reason_tag_key))
