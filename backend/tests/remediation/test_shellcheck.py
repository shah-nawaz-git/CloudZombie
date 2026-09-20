import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tests.remediation.script_examples import generated_examples

GOLDEN_DIR = Path(__file__).parents[1] / "golden"


def shellcheck_path() -> str:
    executable = shutil.which("shellcheck")
    if executable:
        return executable
    try:
        import shellcheck_py
    except ImportError:
        shellcheck_py = None
    fallback = getattr(shellcheck_py, "SHELLCHECK_PATH", None)
    if fallback:
        return str(fallback)
    sibling = Path(sys.executable).with_name("shellcheck.exe")
    if sibling.exists():
        return str(sibling)
    pytest.skip("shellcheck not found in PATH and shellcheck-py exposes no binary")


def check(executable: str, path: Path) -> None:
    result = subprocess.run(
        [executable, "-s", "bash", "-S", "style", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_golden_and_fresh_scripts_pass_shellcheck(tmp_path) -> None:
    executable = shellcheck_path()
    examples = generated_examples()
    for filename, script in examples.items():
        check(executable, GOLDEN_DIR / filename)
        fresh = tmp_path / filename
        fresh.write_text(script.content, encoding="ascii", newline="\n")
        check(executable, fresh)
