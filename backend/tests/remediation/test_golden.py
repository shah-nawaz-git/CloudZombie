import os
from pathlib import Path

from tests.remediation.script_examples import generated_examples

GOLDEN_DIR = Path(__file__).parents[1] / "golden"


def test_generated_scripts_match_golden_files(request) -> None:
    update = request.config.getoption("--update-golden") or os.getenv("UPDATE_GOLDEN") == "1"
    for filename, script in generated_examples().items():
        path = GOLDEN_DIR / filename
        if update:
            path.write_text(script.content, encoding="ascii", newline="\n")
        assert path.read_bytes() == script.content.encode("ascii")
