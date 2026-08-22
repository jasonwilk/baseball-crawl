<!-- NO REAL NAMES OR IDENTIFIERS — placeholder taxonomy per .claude/rules/api-docs.md. -->

# `bb report reconcile-scoreboard` opens the live DB read-write while promising read-only

**Date**: 2026-08-22 · **Status**: `STUB` — verified, one-line fix + test; FOLD into the
runs-instrument chunk (which owns this command's surfaces) unless ruled standalone.

The command's docstring says "Read-only on the database." (`src/cli/report.py:262`) and
`.claude/rules/canonical-seams.md` prescribes the `mode=ro` URI for must-not-modify readers
— but the connection is `sqlite3.connect(str(db_path))` (`src/cli/report.py:297`), a bare
read-write open that then executes `PRAGMA foreign_keys=ON`. Pre-existing; the command is a
pure reader today, so this is a seam divergence, not a live hazard — but it is also the
north-star instrument CLAUDE.md tells every ingestion chunk to run, so it holds a write
handle on the live DB exactly when writers are most likely active. Known adjacent trap: the
bare CLI form silently returned EMPTY results under concurrent WAL writers (2026-08-10).

Fix shape: `sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)`; drop or justify the
PRAGMA (FK enforcement is meaningless read-only); one test proving a write attempt through
the command's connection raises `sqlite3.OperationalError`.

First recorded on the board 2026-08-17 (STANDING RESIDUALS, "Two live-data findings", item
2); routed to a stub at audit 6.
