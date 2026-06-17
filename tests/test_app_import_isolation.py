"""Import-isolation guard for the FastAPI app (E-239-01, AC-2).

After E-239-01 extracted the surviving admin surface into
``src/api/routes/reports_admin.py`` and deleted ``src/api/routes/admin.py``,
importing the app must no longer transitively import ``src.pipeline`` (the
member-sync orchestration that admin.py pulled in via
``from src.pipeline import trigger``).  This severs coupling chain 1 so the
pipeline package becomes deletable in later E-239 stories without breaking app
startup.

The check runs in a fresh subprocess so a clean ``sys.modules`` is guaranteed --
an in-process assertion could pass or fail depending on whether an earlier test
already imported ``src.pipeline``.

Run with:
    pytest tests/test_app_import_isolation.py -v
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_app_import_does_not_pull_in_pipeline() -> None:
    """A fresh ``import src.api.main`` must not load any ``src.pipeline`` module."""
    code = (
        "import sys\n"
        "import src.api.main  # noqa: F401\n"
        "leaked = sorted(\n"
        "    m for m in sys.modules\n"
        "    if m == 'src.pipeline' or m.startswith('src.pipeline.')\n"
        ")\n"
        "assert not leaked, f'app import leaked pipeline modules: {leaked}'\n"
        "print('OK')\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(_PROJECT_ROOT),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"import-isolation check failed.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert "OK" in result.stdout
