"""The JavaScript engine used by the Explorer must reproduce the Python reference exactly."""
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is not installed")
def test_js_engine_reproduces_python(tmp_path):
    fx = tmp_path / "fixtures.json"
    subprocess.run([sys.executable, str(ROOT / "tools" / "dump_conformance.py"), str(fx)], check=True, capture_output=True)
    r = subprocess.run(["node", str(ROOT / "tests" / "js_conformance.mjs"), str(fx)], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
