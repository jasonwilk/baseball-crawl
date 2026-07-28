"""Integration tests for the doc-PII byte-gate wrapper in .githooks/pre-commit.

The gate runs `scripts/check_doc_pii.sh` against the staged `epics/` and
`.project/` trees. Exit disposition: 0 pass, 1 block, 2 block (fail closed),
3 announce but do not block.

Every identifier used here is fabricated. The real denylist
(secrets/pii-denylist.txt) is never read: each test either points
PII_DENYLIST_FILE at a temp denylist of fake tokens, or asserts the
denylist-absent path, which needs no identifier at all.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Fabricated sentinel. Not a real name, UUID, or public_id.
FAKE_TOKEN = "ZZ__FABRICATED_DENYLIST_SENTINEL"


def _base_env() -> dict[str, str]:
    env = {**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null"}
    env.pop("PII_DENYLIST_FILE", None)
    return env


def _init_repo(tmp_path: Path, *, with_scripts: bool = True) -> Path:
    """Temp git repo wired to the project's pre-commit hook, scanner, and scripts."""
    env = _base_env()
    repo = tmp_path / "repo"
    repo.mkdir()

    subprocess.run(["git", "init"], cwd=repo, capture_output=True, check=True, env=env)
    for key, value in [
        ("user.email", "test@localhost"),
        ("user.name", "Test User"),
        ("core.hooksPath", str(PROJECT_ROOT / ".githooks")),
    ]:
        subprocess.run(
            ["git", "config", key, value], cwd=repo, capture_output=True, check=True, env=env
        )

    src_dir = repo / "src"
    src_dir.mkdir()
    (src_dir / "__init__.py").touch()
    (src_dir / "safety").symlink_to(PROJECT_ROOT / "src" / "safety")
    if with_scripts:
        (repo / "scripts").symlink_to(PROJECT_ROOT / "scripts")

    return repo


def _git(repo: Path, *args: str) -> None:
    subprocess.run(list(args), cwd=repo, capture_output=True, check=True, env=_base_env())


def _write_denylist(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "denylist.txt"
    path.write_text(body)
    return path


def _stage_file(repo: Path, name: str, content: str) -> Path:
    path = repo / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    subprocess.run(
        ["git", "add", name], cwd=repo, capture_output=True, check=True, env=_base_env()
    )
    return path


def _commit(
    repo: Path, denylist: Path | None = None, bash_env: Path | None = None
) -> subprocess.CompletedProcess[str]:
    env = _base_env()
    if denylist is not None:
        env["PII_DENYLIST_FILE"] = str(denylist)
    if bash_env is not None:
        env["BASH_ENV"] = str(bash_env)
    return subprocess.run(
        ["git", "commit", "-m", "test commit"],
        cwd=repo,
        capture_output=True,
        text=True,
        env=env,
    )


def _output(result: subprocess.CompletedProcess[str]) -> str:
    return result.stdout + result.stderr


@pytest.mark.integration
class TestExitCodeDisposition:
    """AC-2: 0 passes, 1 blocks, 2 blocks, 3 announces without blocking."""

    def test_denylist_absent_announces_and_does_not_block(self, tmp_path: Path) -> None:
        # AC-5: a fresh clone (denylist gitignored, hence absent) stays committable.
        repo = _init_repo(tmp_path)
        _stage_file(repo, "epics/E-999-demo/epic.md", "# Demo epic\n")
        result = _commit(repo)
        assert result.returncode == 0, _output(result)
        assert "[doc-pii: INCONCLUSIVE" in _output(result)

    def test_clean_tree_with_real_denylist_passes(self, tmp_path: Path) -> None:
        repo = _init_repo(tmp_path)
        denylist = _write_denylist(tmp_path, f"plain {FAKE_TOKEN}\n")
        _stage_file(repo, "epics/E-999-demo/epic.md", "# Demo epic\n")
        result = _commit(repo, denylist)
        assert result.returncode == 0, _output(result)
        assert "[doc-pii: REAL, 0 matches]" in _output(result)

    def test_denylisted_identifier_blocks_commit(self, tmp_path: Path) -> None:
        # AC-6, with a fabricated identifier in both the denylist and the artifact.
        repo = _init_repo(tmp_path)
        denylist = _write_denylist(tmp_path, f"plain {FAKE_TOKEN}\n")
        _stage_file(repo, "epics/E-999-demo/epic.md", f"Opponent: {FAKE_TOKEN}\n")
        result = _commit(repo, denylist)
        assert result.returncode != 0
        assert "[doc-pii: BLOCKED]" in _output(result)

    def test_malformed_denylist_blocks_commit(self, tmp_path: Path) -> None:
        repo = _init_repo(tmp_path)
        denylist = _write_denylist(tmp_path, "bogustype something\n")
        _stage_file(repo, "epics/E-999-demo/epic.md", "# Demo epic\n")
        result = _commit(repo, denylist)
        assert result.returncode != 0
        assert "[doc-pii: BLOCKED]" in _output(result)


@pytest.mark.integration
class TestGatedTrees:
    """AC-1: both planning trees are gated; other paths are not."""

    def test_dot_project_tree_is_gated(self, tmp_path: Path) -> None:
        repo = _init_repo(tmp_path)
        denylist = _write_denylist(tmp_path, f"plain {FAKE_TOKEN}\n")
        _stage_file(repo, ".project/ideas/IDEA-999.md", f"Ref: {FAKE_TOKEN}\n")
        result = _commit(repo, denylist)
        assert result.returncode != 0
        assert "[doc-pii: BLOCKED]" in _output(result)

    def test_non_planning_paths_do_not_invoke_the_gate(self, tmp_path: Path) -> None:
        repo = _init_repo(tmp_path)
        denylist = _write_denylist(tmp_path, f"plain {FAKE_TOKEN}\n")
        _stage_file(repo, "notes.md", "# notes\n")
        result = _commit(repo, denylist)
        assert result.returncode == 0, _output(result)
        assert "[doc-pii:" not in _output(result)


@pytest.mark.integration
class TestIndexNotWorkingTree:
    """The gate judges the index snapshot, not the working tree."""

    def test_staged_identifier_blocks_even_when_working_tree_is_clean(
        self, tmp_path: Path
    ) -> None:
        repo = _init_repo(tmp_path)
        denylist = _write_denylist(tmp_path, f"plain {FAKE_TOKEN}\n")
        path = _stage_file(repo, "epics/E-999-demo/epic.md", f"Opponent: {FAKE_TOKEN}\n")
        path.write_text("# scrubbed in the working tree only\n")
        result = _commit(repo, denylist)
        assert result.returncode != 0
        assert "[doc-pii: BLOCKED]" in _output(result)

    def test_working_tree_identifier_does_not_block_a_clean_index(self, tmp_path: Path) -> None:
        repo = _init_repo(tmp_path)
        denylist = _write_denylist(tmp_path, f"plain {FAKE_TOKEN}\n")
        path = _stage_file(repo, "epics/E-999-demo/epic.md", "# Demo epic\n")
        path.write_text(f"Unstaged edit: {FAKE_TOKEN}\n")
        result = _commit(repo, denylist)
        assert result.returncode == 0, _output(result)
        assert "[doc-pii: REAL, 0 matches]" in _output(result)

    def test_skip_worktree_entry_still_blocks(self, tmp_path: Path) -> None:
        """`git checkout-index` omits skip-worktree entries unless told otherwise.

        Without --ignore-skip-worktree-bits the snapshot lacks epics/ entirely,
        the gate certifies a snapshot the index disagrees with, and the
        identifier rides into the commit.
        """
        repo = _init_repo(tmp_path)
        denylist = _write_denylist(tmp_path, f"plain {FAKE_TOKEN}\n")
        _stage_file(repo, "epics/E-999-demo/epic.md", f"Opponent: {FAKE_TOKEN}\n")
        _git(repo, "git", "update-index", "--skip-worktree", "epics/E-999-demo/epic.md")
        result = _commit(repo, denylist)
        assert result.returncode != 0, _output(result)
        assert "[doc-pii: BLOCKED]" in _output(result)


@pytest.mark.integration
class TestGateNeverSilentlySkips:
    """A gate that did not run must not report a pass (fail closed, TN §7)."""

    def test_lookalike_prefix_does_not_select_a_planning_tree(self, tmp_path: Path) -> None:
        # `.project` used as a regex matches `aproject/`. The gate would then be
        # selected for a tree absent from the snapshot, skip, and print a pass.
        repo = _init_repo(tmp_path)
        _stage_file(repo, "aproject/notes.md", "# notes\n")
        result = _commit(repo)
        assert result.returncode == 0, _output(result)
        assert "[doc-pii:" not in _output(result)

    def test_missing_gate_script_blocks_planning_commit(self, tmp_path: Path) -> None:
        repo = _init_repo(tmp_path, with_scripts=False)
        _stage_file(repo, "epics/E-999-demo/epic.md", "# Demo epic\n")
        result = _commit(repo)
        assert result.returncode != 0, _output(result)
        assert "[doc-pii: BLOCKED]" in _output(result)

    def test_enumeration_does_not_depend_on_mapfile_d(self, tmp_path: Path) -> None:
        """`mapfile -d` needs bash 4.4+; the Mac host ships bash 3.2.

        A `mapfile -d` enumeration would error there, leave STAGED_ARR empty,
        pass the empty-check, and commit with both gates inert (fail-open). A
        BASH_ENV shim overrides the mapfile builtin to reject -d, emulating the
        old bash; the portable `read -d ''` loop never calls it and still blocks.
        """
        shim = tmp_path / "shim.sh"
        shim.write_text(
            "mapfile() {\n"
            '  case "$1" in -d) echo "bash: mapfile: -d: invalid option" >&2; return 2 ;; esac\n'
            '  builtin mapfile "$@"\n'
            "}\n"
        )
        repo = _init_repo(tmp_path)
        denylist = _write_denylist(tmp_path, f"plain {FAKE_TOKEN}\n")
        _stage_file(repo, "epics/E-999-demo/epic.md", f"Opponent: {FAKE_TOKEN}\n")
        result = _commit(repo, denylist, bash_env=shim)
        assert result.returncode != 0, _output(result)
        assert "[doc-pii: BLOCKED]" in _output(result)

    @pytest.mark.parametrize("name", ['rép.md', 'a"b.md', "a\\b.md"])
    def test_hostile_filename_still_blocks(self, tmp_path: Path, name: str) -> None:
        """`git diff --cached --name-only` C-quotes hostile paths.

        A non-ASCII byte, a double-quote, or a backslash each yield a quoted
        C-string that matches no path prefix and names no readable file, so the
        tree is never enumerated, the gate never runs, and the identifier is
        committed. `core.quotePath=false` suppresses only the non-ASCII case;
        `-z` is the enumeration that has no quoting layer at all. The GATED
        counter cannot catch this -- it validates the loop, not the enumeration.
        """
        repo = _init_repo(tmp_path)
        denylist = _write_denylist(tmp_path, f"plain {FAKE_TOKEN}\n")
        _stage_file(repo, f"epics/E-999-demo/{name}", f"Opponent: {FAKE_TOKEN}\n")
        result = _commit(repo, denylist)
        assert result.returncode != 0, _output(result)
        assert "[doc-pii: BLOCKED]" in _output(result)


@pytest.mark.integration
class TestRenameEnumeration:
    """The staged-file enumeration must include renames.

    `--diff-filter=ACM` excludes `R`, so a renamed path never reached the
    enumeration and was never scanned. When the rename is the only staged
    change the list is EMPTY, and the hook returns 0 at the empty-list early
    exit before any gate runs at all -- so a rename carrying a content edit
    committed unscanned. Both tests stage only the rename, which is the
    reachable shape: `git mv` a file and edit it in the same commit.
    """

    def test_rename_with_edit_introducing_credential_blocks(self, tmp_path: Path) -> None:
        # Built at runtime: a literal credential-shaped assignment written into
        # this source file would trip the scanner on this file itself.
        credential = "GC_REFRESH_TOKEN=" + "z" * 40
        body = "".join(f"line {n}\n" for n in range(10))

        repo = _init_repo(tmp_path)
        _stage_file(repo, "docs/notes.md", body)
        _git(repo, "git", "commit", "-m", "seed")

        _git(repo, "git", "mv", "docs/notes.md", "docs/renamed.md")
        (repo / "docs" / "renamed.md").write_text(body + credential + "\n")
        _git(repo, "git", "add", "-A", "docs")

        # Precondition: git must classify this as R, not delete+add. If it ever
        # scores below the rename threshold the staged set contains an `A`,
        # which `ACM` already caught -- the test would pass without exercising
        # the enumeration it exists to pin.
        status = subprocess.run(
            ["git", "diff", "--cached", "--name-status"],
            cwd=repo,
            capture_output=True,
            text=True,
            env=_base_env(),
        ).stdout
        assert status.startswith("R"), f"precondition: expected a rename, got: {status!r}"

        result = _commit(repo)
        assert result.returncode != 0, _output(result)
        assert "[PII BLOCKED]" in _output(result)

    def test_content_neutral_rename_still_passes(self, tmp_path: Path) -> None:
        """No false positive: a rename that changes nothing must still commit."""
        repo = _init_repo(tmp_path)
        _stage_file(repo, "docs/notes.md", "line one\nline two\n")
        _git(repo, "git", "commit", "-m", "seed")

        _git(repo, "git", "mv", "docs/notes.md", "docs/renamed.md")
        _git(repo, "git", "add", "-A", "docs")

        result = _commit(repo)
        assert result.returncode == 0, _output(result)
