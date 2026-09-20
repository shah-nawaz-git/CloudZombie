from datetime import UTC, datetime

from app.persistence.models import Finding


def _days_since(at: datetime, now: datetime) -> int:
    return max((now.astimezone(UTC) - at.astimezone(UTC)).days, 0)


def observation_sentence(finding: Finding, now: datetime) -> str:
    first_days = _days_since(finding.first_observed_at, now)
    sentence = (
        f"CloudZombie first observed this condition on "
        f"{finding.first_observed_at.date().isoformat()} ({first_days} days ago) and has "
        f"seen it in {finding.observation_count} scan(s)"
    )
    if (
        finding.consecutive_observations > 0
        and finding.consecutive_observations != finding.observation_count
    ):
        sentence += f", {finding.consecutive_observations} consecutive"
    sentence += "."
    if finding.streak_started_at != finding.first_observed_at:
        sentence += (
            " The condition was previously resolved and re-observed; the current streak "
            f"began on {finding.streak_started_at.date().isoformat()}."
        )
    if finding.resource_created_at is not None:
        resource_days = _days_since(finding.resource_created_at, now)
        sentence += (
            f" The resource itself was created on "
            f"{finding.resource_created_at.date().isoformat()} ({resource_days} days ago); "
            "resource age is not evidence of how long the condition has existed."
        )
    return sentence
