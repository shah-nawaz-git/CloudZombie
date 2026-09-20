from click.testing import CliRunner

import app.cli as cli_module
from app.cli import cloudzombie
from app.providers.errors import ProviderCredentialsError


def test_demo_identity_command(tmp_path) -> None:
    result = CliRunner().invoke(
        cloudzombie,
        ["identity"],
        env={
            "CLOUDZOMBIE_MODE": "demo",
            "DATABASE_URL": f"sqlite:///{(tmp_path / 'identity.db').as_posix()}",
        },
    )
    assert result.exit_code == 0, result.output
    assert "Mode: DEMO" in result.output
    assert "Account ID: 123456789012" in result.output
    assert "Identity type: assumed-role" in result.output


def test_identity_credentials_error_is_clean(tmp_path, monkeypatch) -> None:
    class MissingCredentialsProvider:
        def get_identity(self):
            raise ProviderCredentialsError("credentials unavailable")

    monkeypatch.setattr(
        cli_module,
        "build_provider",
        lambda environment, app_settings, clock: MissingCredentialsProvider(),
    )
    result = CliRunner().invoke(
        cloudzombie,
        ["identity"],
        env={
            "CLOUDZOMBIE_MODE": "live",
            "DATABASE_URL": f"sqlite:///{(tmp_path / 'live-identity.db').as_posix()}",
        },
    )
    assert result.exit_code == 1
    assert "Identity check failed" in result.output
    assert "What you can do" in result.output
    assert "Traceback" not in result.output


def test_scan_twice_preserves_first_observed_and_increments_count(tmp_path) -> None:
    database = tmp_path / "cli.db"
    runner = CliRunner()
    environment = {
        "CLOUDZOMBIE_MODE": "demo",
        "DATABASE_URL": f"sqlite:///{database.as_posix()}",
    }
    first = runner.invoke(cloudzombie, ["scan", "--region", "eu-central-1"], env=environment)
    assert first.exit_code == 0, first.output
    second = runner.invoke(cloudzombie, ["scan", "--region", "eu-central-1"], env=environment)
    assert second.exit_code == 0, second.output
    assert "DEMO" in first.output and "DEMO" in second.output
    assert first.output.isascii() and second.output.isascii()
    assert "unattached for" not in first.output.lower() + second.output.lower()
    first_date = (
        next(line for line in first.output.splitlines() if "vol-0a1b2c3d4e5f60001" in line)
        .split("|")[4]
        .strip()
        .split()[0]
    )
    second_line = next(
        line for line in second.output.splitlines() if "vol-0a1b2c3d4e5f60001" in line
    )
    assert second_line.split("|")[4].strip().split()[0] == first_date
    assert second_line.split("|")[5].strip() == "2"
