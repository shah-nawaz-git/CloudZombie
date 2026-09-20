from click.testing import CliRunner

from app.cli import cloudzombie


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
