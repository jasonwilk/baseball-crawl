"""Import-isolation guard for the FastAPI app (E-239-01, AC-2).

E-239-01 extracted the surviving admin surface into
``src/api/routes/reports_admin.py`` and deleted ``src/api/routes/admin.py``,
which had pulled the member-sync orchestration package into the app's import
graph.  Severing that coupling chain is what made the package deletable; it
**was** deleted later in E-239 and no longer exists.

This test is therefore a standing guard against the chain being re-formed, not
a check on live code: it asserts that importing the app pulls in no module named
``src.pipeline``.  The name survives here only as the thing being excluded.

The check runs in a fresh subprocess so a clean ``sys.modules`` is guaranteed --
an in-process assertion could pass or fail depending on what an earlier test had
already imported.

Run with:
    pytest tests/test_app_import_isolation.py -v
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_app_import_does_not_pull_in_pipeline() -> None:
    """A fresh ``import src.api.main`` must not load a ``src.pipeline`` module.

    The package was removed in E-239; this guards against its return.
    """
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
