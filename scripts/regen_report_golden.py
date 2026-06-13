"""Regenerate the committed report-stats golden file (E-234-01).

This is the explicit, separate regeneration path for
``tests/fixtures/golden/report_stats.json``. The golden test
(``tests/test_report_golden.py``) NEVER writes the golden -- it only loads and
deep-equals -- so any regenerated golden surfaces in ``git diff`` and is gated
by code review (the anti-silent-overwrite mechanism, TN-1).

The collector / normalizer live in ``tests.test_report_golden`` so there is a
single source of truth for the query surface; this script just drives them and
writes the file with a refreshed ``_meta`` provenance block.

Usage::

    python scripts/regen_report_golden.py

This is a dev-only tool (not an operator ``bb`` command) and is intentionally
exempt from the ``tests/test_script_entry_points.py`` ``--help`` subprocess
convention.

IMPORTANT: After regenerating, hand-review the diff against the ``seed.sql``
header math before committing -- do NOT encode a current bug as the golden.
"""

from __future__ import annotations

import datetime
import getpass
import json
import sys
from pathlib import Path

# Add project root to sys.path so ``src`` / ``tests`` are importable directly.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tests.test_report_golden import (  # noqa: E402
    GOLDEN_PATH,
    PRIMARY_SEASON_ID,
    TEAM_GC_UUID,
    WORKLOAD_REFERENCE_DATE,
    build_golden_payload,
    resolve_team_id,
    seed_connection,
)

_BASIS = "seed.sql header math"


def regenerate() -> Path:
    """Rebuild the golden file and return its path."""
    conn = seed_connection()
    try:
        team_id = resolve_team_id(conn, TEAM_GC_UUID)
        meta = {
            "reviewed_by": getpass.getuser(),
            "reviewed_date": datetime.date.today().isoformat(),
            "basis": _BASIS,
            "note": (
                "Hand-reviewed against the seed.sql header math at creation. "
                "Regeneration is observable in git diff; re-review before commit."
            ),
        }
        payload = build_golden_payload(
            conn,
            team_id,
            PRIMARY_SEASON_ID,
            WORKLOAD_REFERENCE_DATE,
            meta=meta,
        )
    finally:
        conn.close()

    GOLDEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    GOLDEN_PATH.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return GOLDEN_PATH


def main() -> None:
    path = regenerate()
    rel = path.relative_to(_PROJECT_ROOT)
    print(f"Wrote golden: {rel}")
    print("Review the diff against seed.sql header math before committing.")


if __name__ == "__main__":
    main()
