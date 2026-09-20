from datetime import UTC, datetime

import click
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.clock import SystemClock
from app.core.config import Settings
from app.models import AppSettings
from app.persistence.database import create_database_engine
from app.persistence.models import Base, Finding
from app.pricing.cache import DbPricingCache
from app.pricing.service import PricingService
from app.providers.errors import ProviderCredentialsError, ProviderError
from app.scanner.engine import ScanEngine
from app.services.provider_factory import build_provider
from app.services.settings_service import SettingsService


def _runtime() -> tuple[Settings, sessionmaker[Session], AppSettings, SystemClock]:
    environment = Settings()
    engine = create_database_engine(environment.database_url)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    clock = SystemClock()
    with factory() as session:
        service = SettingsService(session, environment)
        app_settings = service.load()
        if environment.cloudzombie_mode.value == "demo" and app_settings.demo_anchor_at is None:
            app_settings.demo_anchor_at = clock.now()
            service.save(app_settings)
        session.commit()
    return environment, factory, app_settings, clock


def _relative_days(at: datetime, now: datetime) -> int:
    return max((now.astimezone(UTC) - at.astimezone(UTC)).days, 0)


def _print_findings(session: Session, now: datetime) -> None:
    findings = list(session.scalars(select(Finding).order_by(Finding.region, Finding.resource_id)))
    headers = [
        "Resource",
        "Type",
        "Region",
        "Resource age",
        "First observed",
        "Observations",
        "Est. monthly",
        "Confidence",
        "Risk",
        "Status",
    ]
    rows: list[list[str]] = []
    for finding in findings:
        age = (
            f"{_relative_days(finding.resource_created_at, now)} days"
            if finding.resource_created_at
            else "unknown"
        )
        first_days = _relative_days(finding.first_observed_at, now)
        amount = (
            f"${finding.estimated_monthly_cost:.2f}"
            if finding.estimated_monthly_cost is not None
            else "-"
        )
        rows.append(
            [
                finding.resource_id,
                finding.resource_type,
                finding.region,
                age,
                f"{finding.first_observed_at.date().isoformat()} ({first_days} days ago)",
                str(finding.observation_count),
                amount,
                finding.cost_confidence,
                finding.remediation_risk,
                finding.status,
            ]
        )
    widths = [
        max(len(headers[index]), *(len(row[index]) for row in rows))
        if rows
        else len(headers[index])
        for index in range(len(headers))
    ]
    click.echo(" | ".join(value.ljust(widths[i]) for i, value in enumerate(headers)))
    click.echo("-+-".join("-" * width for width in widths))
    for row in rows:
        click.echo(" | ".join(value.ljust(widths[i]) for i, value in enumerate(row)))


@click.group()
def cloudzombie() -> None:
    """CloudZombie cleanup planning commands."""


@cloudzombie.command()
def identity() -> None:
    try:
        environment, _, app_settings, clock = _runtime()
        provider = build_provider(environment, app_settings, clock)
        verified = provider.get_identity()
    except ProviderCredentialsError as exc:
        click.echo(f"Identity check failed: AWS credentials could not be verified ({exc}).")
        click.echo(
            "What you can do: configure a valid AWS profile or the standard AWS credential "
            "environment variables, then retry."
        )
        raise click.exceptions.Exit(1) from None
    except ProviderError as exc:
        click.echo(f"Identity check failed: AWS provider error ({exc}).")
        click.echo("What you can do: verify AWS connectivity, region access, and permissions.")
        raise click.exceptions.Exit(1) from None
    click.echo(f"Mode: {provider.mode.value.upper()}")
    click.echo(f"Account ID: {verified.account_id}")
    click.echo(f"Principal ARN: {verified.principal_arn}")
    click.echo(f"Identity type: {verified.identity_type}")


@cloudzombie.command()
@click.option("regions", "--region", multiple=True)
def scan(regions: tuple[str, ...]) -> None:
    environment, factory, app_settings, clock = _runtime()
    provider = build_provider(environment, app_settings, clock)
    cache = DbPricingCache(factory, clock, app_settings.pricing_cache_ttl_seconds)
    pricing = PricingService(provider, app_settings, clock, cache)
    result = ScanEngine(provider, factory, app_settings, pricing, clock).run_scan(
        list(regions) or None
    )
    click.echo(f"{result.mode.upper()} account {result.account_id or 'unavailable'}")
    for region, entry in result.coverage.items():
        suffix = " - region not enabled" if entry["status"] == "skipped" else ""
        click.echo(f"{region}  {entry['status'].upper()}{suffix}")
    with factory() as session:
        _print_findings(session, clock.now())
    click.echo(
        f"Totals: new {result.new_findings}, persistent {result.persistent_findings}, "
        f"resolved {result.resolved_findings}"
    )
    click.echo(f"Estimated monthly list-price exposure: ${result.estimated_exposure:.2f}")


@cloudzombie.command()
def findings() -> None:
    _, factory, _, clock = _runtime()
    with factory() as session:
        _print_findings(session, clock.now())


if __name__ == "__main__":
    cloudzombie()
