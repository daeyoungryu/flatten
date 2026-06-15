import re
import subprocess
import sys
from pathlib import Path

import tomllib


def test_distribution_name_is_normalized_and_unique():
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert project["name"] == "flatten-polymorph"


def test_wheel_filename_pattern_after_build(tmp_path):
    result = subprocess.run(
        [sys.executable, "-m", "build", "--wheel", "--outdir", str(tmp_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    wheels = list(tmp_path.glob("*.whl"))
    assert len(wheels) == 1
    assert re.fullmatch(r"flatten_polymorph-0\.1\.1-py3-none-any\.whl", wheels[0].name)
