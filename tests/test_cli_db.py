"""Tests for the ``bb db`` CLI sub-app (src/cli/db.py).

Tests use CliRunner to exercise argument mapping only -- database operations
(backup, migrations, seeding) are mocked.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from src.cli import app

runner = CliRunner()


# ---------------------------------------------------------------------------
# bb db backup
# ---------------------------------------------------------------------------


class TestDbBackup:
    """Argument mapping tests for ``bb db backup``."""

    _BACKUP_PATH = Path("/data/backups/app-2026-01-01T000000.db")

    def test_backup_success_exit_0(self) -> None:
        """Successful backup exits 0."""
        with patch("src.cli.db.backup_database", return_value=self._BACKUP_PATH) as mock_fn:
            result = runner.invoke(app, ["db", "backup"])
        assert result.exit_code == 0
        mock_fn.assert_called_once_with(db_path=None)

    def test_backup_prints_backup_path(self) -> None:
        """Output contains the path to the backup file."""
        with patch("src.cli.db.backup_database", return_value=self._BACKUP_PATH):
            result = runner.invoke(app, ["db", "backup"])
        assert str(self._BACKUP_PATH) in result.output

    def test_backup_db_path_flag_passed_through(self, tmp_path: Path) -> None:
        """--db-path flag is forwarded to backup_database."""
        db_file = tmp_path / "custom.db"
        with patch("src.cli.db.backup_database", return_value=self._BACKUP_PATH) as mock_fn:
            result = runner.invoke(app, ["db", "backup", "--db-path", str(db_file)])
        assert result.exit_code == 0
        mock_fn.assert_called_once_with(db_path=db_file)

    def test_backup_file_not_found_exits_1(self) -> None:
        """FileNotFoundError from backup_database exits 1 with actionable message."""
        with patch(
            "src.cli.db.backup_database",
            side_effect=FileNotFoundError("Database not found: /data/app.db"),
        ):
            result = runner.invoke(app, ["db", "backup"])
        assert result.exit_code == 1

    def test_backup_file_not_found_message_hints_init(self) -> None:
        """Error output mentions the actual path and how to initialize the DB."""
        with patch(
            "src.cli.db.backup_database",
            side_effect=FileNotFoundError("Database not found: /data/app.db"),
        ):
            result = runner.invoke(app, ["db", "backup"])
        assert "Initialize the database first" in result.output
        assert "Database not found: /data/app.db" in result.output


# ---------------------------------------------------------------------------
# bb db reset
# ---------------------------------------------------------------------------


class TestDbReset:
    """Argument mapping tests for ``bb db reset``."""

    def test_reset_with_force_skips_confirmation(self) -> None:
        """--force bypasses the confirmation prompt and exits 0."""
        with patch("src.cli.db.reset_database", return_value=(5, 42)) as mock_fn:
            result = runner.invoke(app, ["db", "reset", "--force"])
        assert result.exit_code == 0
        mock_fn.assert_called_once_with(db_path=None, force=True, _skip_guard=True)

    def test_reset_prints_summary_on_success(self) -> None:
        """Output reports the table count and an empty-schema message."""
        with patch("src.cli.db.reset_database", return_value=(5, 0)):
            result = runner.invoke(app, ["db", "reset", "--force"])
        assert "5" in result.output
        assert "empty schema" in result.output.lower()

    def test_reset_db_path_flag_passed_through(self, tmp_path: Path) -> None:
        """--db-path flag is forwarded to reset_database."""
        db_file = tmp_path / "custom.db"
        with patch("src.cli.db.reset_database", return_value=(3, 0)) as mock_fn:
            result = runner.invoke(app, ["db", "reset", "--force", "--db-path", str(db_file)])
        assert result.exit_code == 0
        mock_fn.assert_called_once_with(db_path=db_file, force=True, _skip_guard=True)

    def test_reset_without_force_triggers_confirmation_prompt(self) -> None:
        """Without --force, the confirmation prompt appears."""
        with patch("src.cli.db.reset_database", return_value=(5, 42)):
            # Provide "y" to confirm.
            result = runner.invoke(app, ["db", "reset"], input="y\n")
        assert "Confirm?" in result.output

    def test_reset_without_force_confirm_yes_proceeds(self) -> None:
        """Answering 'y' to the prompt proceeds to reset."""
        with patch("src.cli.db.reset_database", return_value=(5, 42)) as mock_fn:
            result = runner.invoke(app, ["db", "reset"], input="y\n")
        assert result.exit_code == 0
        mock_fn.assert_called_once()

    def test_reset_without_force_confirm_no_aborts(self) -> None:
        """Answering 'n' (default) aborts without calling reset_database."""
        with patch("src.cli.db.reset_database", return_value=(5, 42)) as mock_fn:
            result = runner.invoke(app, ["db", "reset"], input="n\n")
        assert result.exit_code != 0
        mock_fn.assert_not_called()

    def test_reset_production_guard_without_force_exits_1(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """APP_ENV=production without --force exits 1 before the confirmation prompt."""
        monkeypatch.setenv("APP_ENV", "production")
        with patch("src.cli.db.reset_database", return_value=(5, 42)) as mock_fn:
            result = runner.invoke(app, ["db", "reset"])
        assert result.exit_code == 1
        mock_fn.assert_not_called()

    def test_reset_production_guard_fires_before_prompt(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Production guard logs an error; confirmation prompt does NOT appear."""
        import logging

        monkeypatch.setenv("APP_ENV", "production")
        with patch("src.cli.db.reset_database", return_value=(5, 42)):
            with caplog.at_level(logging.ERROR, logger="src.db.reset"):
                result = runner.invoke(app, ["db", "reset"])
        assert any("production" in r.message.lower() for r in caplog.records)
        assert "Confirm?" not in result.output

    def test_reset_production_with_force_succeeds(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """APP_ENV=production with --force bypasses guard and confirmation."""
        monkeypatch.setenv("APP_ENV", "production")
        with patch("src.cli.db.reset_database", return_value=(5, 42)) as mock_fn:
            result = runner.invoke(app, ["db", "reset", "--force"])
        assert result.exit_code == 0
        mock_fn.assert_called_once_with(db_path=None, force=True, _skip_guard=True)

    def test_reset_system_exit_propagated(self) -> None:
        """SystemExit raised by reset_database is converted to a non-zero Typer exit."""
        with patch("src.cli.db.reset_database", side_effect=SystemExit(1)):
            result = runner.invoke(app, ["db", "reset", "--force"])
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# bb db --help
# ---------------------------------------------------------------------------


class TestDbHelp:
    def test_help_lists_backup_and_reset(self) -> None:
        """``bb db --help`` lists both backup and reset sub-commands."""
        result = runner.invoke(app, ["db", "--help"])
        assert result.exit_code == 0
        assert "backup" in result.output
        assert "reset" in result.output
        assert "purge-scouting" in result.output


# ---------------------------------------------------------------------------
# bb db purge-scouting (E-267-06)
# ---------------------------------------------------------------------------


class TestDbPurgeScouting:
    """Argument mapping and guard sequencing for ``bb db purge-scouting``.

    The purge itself is mocked here -- its behavior is covered end-to-end in
    ``tests/test_purge_scouting.py``. What this class pins is the CLI contract:
    the guard runs BEFORE anything else, a refusal exits non-zero WITHOUT calling
    the purge, the preview is shown before the prompt, the backup is fail-closed,
    and failures surface as a formatted non-zero exit rather than a traceback.

    ``backup_database`` is patched in EVERY test that reaches it, and that is not
    incidental: its destination is hardwired to ``<repo_root>/data/backups`` via
    ``parents[2]`` regardless of ``db_path``, so an unpatched CliRunner run would
    write a real snapshot into the repository.
    """

    _DB_NAME = "custom.db"

    def _result(self, rows=None, files_removed=0, file_errors=0):
        from src.db.purge_scouting import PurgeResult

        return PurgeResult(
            rows_deleted=rows if rows is not None else {"games": 3},
            files_removed=files_removed,
            file_errors=file_errors,
        )

    def _preview(self, counts=None, name: str | None = None):
        from src.db.purge_scouting import PurgePreview

        return PurgePreview(
            resolved_path=Path("/data") / (name or self._DB_NAME),
            row_counts=counts if counts is not None else {"games": 3, "plays": 0},
        )

    @contextmanager
    def _patched(self, *, purge=None, preview=None, backup=None, guard=None):
        """Patch the four seams the command orchestrates.

        Defaults are the all-clear path, so each test overrides only the seam it
        is about and no test silently reaches the real backup or the real DB.
        """
        purge_kw = {"side_effect": purge} if isinstance(purge, Exception) else {
            "return_value": purge if purge is not None else self._result()
        }
        backup_kw = {"side_effect": backup} if isinstance(backup, Exception) else {
            "return_value": backup if backup is not None else Path("/data/backups/b.db")
        }
        preview_kw = {"side_effect": preview} if isinstance(preview, Exception) else {
            "return_value": preview if preview is not None else self._preview()
        }
        guard_kw = {"side_effect": guard} if guard is not None else {}
        with patch("src.cli.db.check_purge_production_guard", **guard_kw) as g, patch(
            "src.cli.db.preview_purge", **preview_kw
        ) as p, patch("src.cli.db.backup_database", **backup_kw) as b, patch(
            "src.cli.db.purge_scouting_data", **purge_kw
        ) as fn:
            yield SimpleNamespace(guard=g, preview=p, backup=b, purge=fn)

    # -- flag split (AC-4) ------------------------------------------------

    def test_force_and_yes_exits_0_and_forwards_args(self, tmp_path: Path) -> None:
        """--force --yes is the scripted path; --db-path is forwarded."""
        db_file = tmp_path / "custom.db"
        with self._patched() as m:
            result = runner.invoke(
                app,
                ["db", "purge-scouting", "--db-path", str(db_file), "--force", "--yes"],
            )
        assert result.exit_code == 0
        m.purge.assert_called_once_with(db_path=db_file, force=True)

    def test_force_alone_still_prompts(self) -> None:
        """AC-4: --force overrides the production refusal, it does NOT skip the prompt.

        The whole point of the split. Pre-E-270 a single --force did both, so an
        operator reaching for the production override silently lost the
        confirmation as well. Declining here must purge nothing.
        """
        with self._patched() as m:
            result = runner.invoke(app, ["db", "purge-scouting", "--force"], input="n\n")
        assert result.exit_code != 0
        m.purge.assert_not_called()

    def test_yes_alone_still_refuses_on_production(self) -> None:
        """AC-4: --yes skips the prompt only; the production refusal still fires.

        ``--yes`` must never reach the library, so the guard is invoked with
        ``force=False`` and its refusal stands.
        """
        with self._patched(guard=SystemExit(1)) as m:
            result = runner.invoke(app, ["db", "purge-scouting", "--yes"])
        assert result.exit_code == 1
        m.guard.assert_called_once_with(force=False)
        m.purge.assert_not_called()

    def test_yes_is_never_forwarded_to_the_library(self) -> None:
        """AC-4: ``--yes`` is pure CLI -- the library takes only ``force``."""
        with self._patched() as m:
            result = runner.invoke(app, ["db", "purge-scouting", "--yes"])
        assert result.exit_code == 0
        _, kwargs = m.purge.call_args
        assert set(kwargs) == {"db_path", "force"}
        assert kwargs["force"] is False

    # -- guard (AC-1 / AC-8) ----------------------------------------------

    def test_production_refusal_exits_nonzero_without_purging(self) -> None:
        """The guard's SystemExit becomes a clean non-zero exit, purge NOT called.

        The error path that matters on a destructive command: a refused purge
        must not reach ``purge_scouting_data`` at all.
        """
        with self._patched(guard=SystemExit(1)) as m:
            result = runner.invoke(app, ["db", "purge-scouting", "--force"])
        assert result.exit_code == 1
        m.purge.assert_not_called()

    def test_typo_app_env_runtimeerror_is_a_clean_nonzero_exit(self) -> None:
        """AC-1: the typo guard raises RuntimeError, not SystemExit.

        The pre-E-270 CLI caught only ``SystemExit``, so this would have surfaced
        as a raw traceback. Nothing may be purged and nothing may be backed up.
        """
        with self._patched(
            guard=RuntimeError("Unrecognized APP_ENV='prod'; expected one of ...")
        ) as m:
            result = runner.invoke(app, ["db", "purge-scouting"])
        assert result.exit_code == 1
        assert "Traceback" not in result.output
        assert "Unrecognized APP_ENV" in result.output
        m.purge.assert_not_called()
        m.backup.assert_not_called()
        m.preview.assert_not_called()

    def test_typo_guard_is_not_overridable_by_force_and_yes(self) -> None:
        """AC-8: --force --yes must NOT get past the typo guard.

        The epic's own fail-open lesson applied to its own spec: an unrecognized
        APP_ENV means the posture is ambiguous, and an override cannot resolve an
        ambiguity. This test fails if ``--force`` is ever wired to skip
        ``validate_app_env`` -- note the guard is asserted CALLED, so a
        short-circuit that never consults it fails here too.
        """
        with self._patched(guard=RuntimeError("Unrecognized APP_ENV='prod'")) as m:
            result = runner.invoke(app, ["db", "purge-scouting", "--force", "--yes"])
        assert result.exit_code == 1
        m.guard.assert_called_once()
        m.purge.assert_not_called()
        m.backup.assert_not_called()

    # -- preview (AC-2) ---------------------------------------------------

    def test_preview_shows_resolved_path_and_counts_before_the_prompt(self) -> None:
        """AC-2: the operator sees WHICH database and HOW MUCH before answering.

        The audit's finding was that the guard keys on APP_ENV while destruction
        keys on ``resolve_db_path()``, and the resolved path was only logged
        AFTER the confirmation -- so the prompt could not tell the operator what
        was in the firing line.
        """
        preview = self._preview(counts={"games": 12, "plays": 400, "reports": 0})
        with self._patched(preview=preview):
            result = runner.invoke(app, ["db", "purge-scouting"], input="n\n")
        assert str(preview.resolved_path) in result.output
        assert "games" in result.output
        assert "12" in result.output
        assert "400" in result.output
        assert "412" in result.output, "the total must be shown"

    def test_unreadable_database_aborts_before_any_prompt_or_purge(self) -> None:
        """AC-2: a preview failure is fail-closed, not a warning."""
        with self._patched(preview=FileNotFoundError("Database not found: /x.db")) as m:
            result = runner.invoke(app, ["db", "purge-scouting", "--yes"])
        assert result.exit_code == 1
        assert "Traceback" not in result.output
        assert "Cannot read the database" in result.output
        m.purge.assert_not_called()
        m.backup.assert_not_called()

    def test_empty_database_preview_says_so(self) -> None:
        """AC-2: zero rows is stated plainly rather than shown as an empty table."""
        with self._patched(preview=self._preview(counts={"games": 0})):
            result = runner.invoke(app, ["db", "purge-scouting"], input="n\n")
        assert "no-op" in result.output.lower()

    # -- confirmation (AC-3) ----------------------------------------------

    def test_declining_the_prompt_aborts_without_purging(self) -> None:
        """Answering 'n' at the confirmation aborts and purges nothing."""
        with self._patched() as m:
            result = runner.invoke(app, ["db", "purge-scouting"], input="n\n")
        assert result.exit_code != 0
        m.purge.assert_not_called()
        m.backup.assert_not_called()

    def test_confirming_the_prompt_purges(self) -> None:
        """Answering 'y' proceeds."""
        with self._patched() as m:
            result = runner.invoke(app, ["db", "purge-scouting"], input="y\n")
        assert result.exit_code == 0
        m.purge.assert_called_once()

    def test_production_requires_a_typed_confirmation(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AC-3: on production a bare 'y' is NOT enough."""
        monkeypatch.setenv("APP_ENV", "production")
        with self._patched() as m:
            result = runner.invoke(app, ["db", "purge-scouting", "--force"], input="y\n")
        assert result.exit_code == 1
        assert "did not match" in result.output
        m.purge.assert_not_called()
        m.backup.assert_not_called()

    @pytest.mark.parametrize("typed", ["custom.db", "purge"])
    def test_production_typed_confirmation_accepts_filename_or_literal(
        self, monkeypatch: pytest.MonkeyPatch, typed: str
    ) -> None:
        """AC-3: the resolved DB filename or the literal 'purge' both confirm."""
        monkeypatch.setenv("APP_ENV", "production")
        with self._patched() as m:
            result = runner.invoke(
                app, ["db", "purge-scouting", "--force"], input=f"{typed}\n"
            )
        assert result.exit_code == 0, result.output
        m.purge.assert_called_once()

    def test_production_typed_confirmation_names_the_resolved_db(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AC-3: the PROMPT names the file to type, so it cannot be guessed blind.

        The assertion is on the QUOTED form, and that is the whole point. The
        ``Database: {resolved_path}`` line printed above the table already emits
        the bare filename, so ``"prod-app.db" in result.output`` passes even with
        ``{expected!r}`` dropped from the prompt -- it would be testing the path
        display, not the prompt. Only the prompt renders the name quoted.
        """
        monkeypatch.setenv("APP_ENV", "production")
        with self._patched(preview=self._preview(name="prod-app.db")):
            result = runner.invoke(
                app, ["db", "purge-scouting", "--force"], input="wrong\n"
            )
        assert "'prod-app.db'" in result.output
        assert result.exit_code == 1

    def test_yes_skips_the_typed_confirmation_on_production(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AC-4: --force --yes is the sanctioned scripted production purge."""
        monkeypatch.setenv("APP_ENV", "production")
        with self._patched() as m:
            result = runner.invoke(app, ["db", "purge-scouting", "--force", "--yes"])
        assert result.exit_code == 0
        m.purge.assert_called_once()

    # -- backup (AC-5) ----------------------------------------------------

    def test_backup_runs_before_the_purge_on_the_resolved_path(self) -> None:
        """AC-5: the snapshot is taken first, of the file actually being purged.

        Passing the PREVIEW's resolved path (not the raw ``--db-path``) is what
        makes "the backup and the purge targeted the same database" true rather
        than coincidental.
        """
        preview = self._preview()
        calls: list[str] = []
        with self._patched(preview=preview) as m:
            m.backup.side_effect = lambda **_kw: (
                calls.append("backup"), Path("/data/backups/b.db")
            )[1]
            m.purge.side_effect = lambda **_kw: (
                calls.append("purge"), self._result()
            )[1]
            result = runner.invoke(app, ["db", "purge-scouting", "--yes"])
        assert result.exit_code == 0
        assert calls == ["backup", "purge"], "the backup must precede the purge"
        m.backup.assert_called_once_with(db_path=preview.resolved_path)

    def test_backup_failure_aborts_the_purge_fail_closed(self) -> None:
        """AC-5: ANY backup failure stops the purge before a row is touched.

        A purge with no recovery point is exactly the gap this closes, so a
        broken backup is a reason to abort -- not a warning to print and carry on.
        """
        with self._patched(backup=OSError("disk full")) as m:
            result = runner.invoke(app, ["db", "purge-scouting", "--yes"])
        assert result.exit_code == 1
        assert "Traceback" not in result.output
        assert "backup failed" in result.output
        assert "Nothing was deleted" in result.output
        m.purge.assert_not_called()

    def test_backup_failure_on_a_missing_database_also_aborts(self) -> None:
        """AC-5: the FileNotFoundError path is fail-closed too, not special-cased."""
        with self._patched(backup=FileNotFoundError("Database not found")) as m:
            result = runner.invoke(app, ["db", "purge-scouting", "--yes"])
        assert result.exit_code == 1
        m.purge.assert_not_called()

    # -- purge failure (AC-6) ---------------------------------------------

    def test_purge_failure_surfaces_as_a_formatted_nonzero_exit(self) -> None:
        """AC-6: a DB failure is a formatted message, not a raw traceback."""
        import sqlite3

        with self._patched(purge=sqlite3.OperationalError("disk I/O error")):
            result = runner.invoke(app, ["db", "purge-scouting", "--force", "--yes"])
        assert result.exit_code == 1
        assert "Traceback" not in result.output
        assert "Purge FAILED" in result.output
        assert "disk I/O error" in result.output

    def test_purge_failure_message_states_the_db_was_rolled_back(self) -> None:
        """AC-6: the operator is told the database is UNCHANGED, not half-purged.

        The actionable part of the failure. Note this deliberately does NOT
        assert the backup path appears in ``result.output`` -- the path is
        already printed by the "Pre-purge backup saved to ..." line above, so
        such an assertion passes even with the error handling deleted. Verified
        by mutation: only the rollback sentence discriminates.
        """
        import sqlite3

        with self._patched(
            purge=sqlite3.OperationalError("boom"), backup=Path("/data/backups/x.db")
        ):
            result = runner.invoke(app, ["db", "purge-scouting", "--force", "--yes"])
        assert result.exit_code == 1
        assert "rolled back" in result.output

    def test_file_errors_are_reported_but_do_not_fail_the_command(self) -> None:
        """Unremovable report files warn; the DB purge still succeeded."""
        with self._patched(
            purge=self._result(files_removed=2, file_errors=1)
        ):
            result = runner.invoke(app, ["db", "purge-scouting", "--force", "--yes"])
        assert result.exit_code == 0
        assert "could not be removed" in result.output
