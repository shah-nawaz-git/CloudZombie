import re
from pathlib import Path

_MUTATING_CALL = re.compile(
    r"\b(delete|terminate|release|modify|create|attach|detach|deregister|associate|disassociate)_[a-z_]+\("
)
_MUTATING_CLI = re.compile(
    r"aws ec2 (delete|terminate|release|modify|create|attach|detach|deregister|associate|"
    r"disassociate)-[a-z-]+"
)
_ALLOWED_HELPERS = {
    "create_engine(",
    "create_database_engine(",
    "create_client(",
    "create_all(",
    "create_app(",
    "create_scan(",
}


def test_application_has_no_mutating_aws_calls_outside_templates() -> None:
    app = Path(__file__).parents[1] / "app"
    template = app / "remediation" / "scripts" / "templates.py"
    violations: list[str] = []
    for path in app.rglob("*.py"):
        if path == template:
            continue
        source = path.read_text(encoding="utf-8")
        for match in _MUTATING_CALL.finditer(source):
            token = source[match.start() : source.find("(", match.start()) + 1]
            if token not in _ALLOWED_HELPERS:
                violations.append(f"{path.relative_to(app)}: {token}")
        if _MUTATING_CLI.search(source):
            violations.append(f"{path.relative_to(app)}: mutating AWS CLI command")
    assert violations == []


def test_templates_contain_only_intended_destructive_commands() -> None:
    template = Path(__file__).parents[1] / "app" / "remediation" / "scripts" / "templates.py"
    source = template.read_text(encoding="utf-8")
    commands = {
        match.group(0).removeprefix("aws ec2 ")
        for match in re.finditer(r"aws ec2 (?:delete|release|create)-[a-z-]+", source)
    }
    assert commands == {
        "delete-volume",
        "release-address",
        "create-snapshot",
        "delete-snapshot",
    }
    for line in source.splitlines():
        if "aws ec2 delete-snapshot" in line:
            stripped = line.strip()
            assert stripped.startswith("#") or 'echo "#' in stripped
