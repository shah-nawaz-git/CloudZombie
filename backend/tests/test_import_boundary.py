import ast
from pathlib import Path


def test_boto_imports_are_confined_to_aws_provider() -> None:
    app = Path(__file__).parents[1] / "app"
    violations: list[str] = []
    for path in app.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            if any(name == "boto3" or name.startswith("botocore") for name in names):
                relative = path.relative_to(app).as_posix()
                if not relative.startswith("providers/aws/"):
                    violations.append(relative)
    assert violations == []
