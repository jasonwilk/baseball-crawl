"""Coverage for the archive-reference sweep (AC-1, AC-2) and its pre-commit
gate (AC-5).

Every case builds a THROWAWAY git repo under pytest's ``tmp_path`` and installs
the real ``.githooks/pre-commit`` and ``scripts/check_archive_refs.sh`` into it.
Nothing is planted under ``/tmp/.worktrees/`` -- a directory matching
``baseball-crawl-E-*`` under the real worktree root puts every agent on the
machine into the write-guard's dispatch mode for as long as it exists, and an
earlier story in this epic did exactly that by accident.

A property of these scratch repos is load-bearing rather than incidental:
``src/safety/pii_scanner.py`` does not exist in them, so the hook's
missing-scanner skip fires and exits 0. Every assertion that the gate FIRED is
therefore also a demonstration that it ran ABOVE that skip -- which is the whole
of AC-5's PLACEMENT requirement. ``test_placement_below_scanner_skip_is_inert``
makes that implicit coverage explicit by mutating the placement and showing the
verdict flips.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK = REPO_ROOT / ".githooks" / "pre-commit"
SCRIPT = REPO_ROOT / "scripts" / "check_archive_refs.sh"

# Exit-code contract, mirroring scripts/check_doc_pii.sh.
PASS, BLOCKED, INVALID = 0, 1, 2

GATE_START = "# --- archive-reference gate ---"
GATE_END = "# --- end archive-reference gate"
SCANNER_SKIP = (
    'if [ ! -f "$REPO_ROOT/src/safety/pii_scanner.py" ]; then\n'
    '  echo "[pii-hook] Scanner not installed yet. Skipping PII check."\n'
    "  exit 0\n"
    "fi\n"
)


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True
    )


def _sweep(epic_id: str, tree: Path | str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(SCRIPT), epic_id, str(tree)], capture_output=True, text=True
    )


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    """A plain directory tree (no git) for the script-level cases."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "src").mkdir()
    (tmp_path / ".project" / "archive" / "E-500-old").mkdir(parents=True)
    (tmp_path / "docs" / "clean.md").write_text("nothing to see\n")
    return tmp_path


def _make_repo(root: Path, hook_text: str | None = None) -> Path:
    """A repo mid-epic: one live epic, one already-archived epic, and a
    reference to each. The dead reference to the ALREADY-archived epic is
    deliberate -- it is what makes the AC-5 RED states meaningful, since a
    gate keyed on presence rather than on archiving would fire on it."""
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-q", ".")
    _git(root, "config", "user.email", "t@example.invalid")
    _git(root, "config", "user.name", "t")
    _git(root, "config", "commit.gpgsign", "false")

    (root / ".hooks").mkdir()
    (root / "scripts").mkdir()
    (root / "epics" / "E-500-old").mkdir(parents=True)
    (root / ".project" / "archive" / "E-400-done").mkdir(parents=True)
    (root / "docs").mkdir()

    (root / ".hooks" / "pre-commit").write_text(
        HOOK.read_text() if hook_text is None else hook_text
    )
    shutil.copy(SCRIPT, root / "scripts" / "check_archive_refs.sh")
    (root / ".hooks" / "pre-commit").chmod(0o755)
    (root / "scripts" / "check_archive_refs.sh").chmod(0o755)
    _git(root, "config", "core.hooksPath", ".hooks")

    (root / "epics" / "E-500-old" / "epic.md").write_text("epic body\n")
    (root / "epics" / "E-500-old" / "E-500-01.md").write_text("story body\n")
    (root / ".project" / "archive" / "E-400-done" / "epic.md").write_text("old\n")
    (root / "docs" / "ref.md").write_text("see epics/E-500-old/epic.md\n")
    (root / "docs" / "old.md").write_text("see epics/E-400-done/epic.md\n")

    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "base")
    return root


def _commit_allowed(repo: Path) -> bool:
    return _git(repo, "commit", "-qm", "t").returncode == 0


def _archive_by_rename(repo: Path) -> None:
    _git(repo, "mv", "epics/E-500-old", ".project/archive/E-500-old")


def _archive_by_delete_add(repo: Path) -> None:
    """The same move with similarity destroyed, so git cannot detect a rename.

    ``git apply --3way`` produces this shape when the epic file has been
    rewritten during its own epic, which is the ordinary case.
    """
    _git(repo, "rm", "-rq", "epics/E-500-old")
    dest = repo / ".project" / "archive" / "E-500-old"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "epic.md").write_text("wholly different bytes; similarity gone\n")
    _git(repo, "add", "-A")


# --------------------------------------------------------------------------
# AC-1 -- the script exists and discriminates, in BOTH directions
# --------------------------------------------------------------------------


def test_clean_tree_passes(tree: Path) -> None:
    assert _sweep("E-500", tree).returncode == PASS


def test_planted_reference_blocks(tree: Path) -> None:
    """The clean exit above certifies nothing without this case."""
    (tree / "src" / "x.py").write_text("truth: epics/E-500-old/story.md\n")
    result = _sweep("E-500", tree)
    assert result.returncode == BLOCKED
    assert "src/x.py" in result.stderr


def test_reference_inside_archive_tree_is_not_a_hit(tree: Path) -> None:
    """History is not a defect. An archived epic quoting its own former path
    is the normal state of every closed epic in the repo."""
    (tree / ".project" / "archive" / "E-500-old" / "epic.md").write_text(
        "see epics/E-500-old/epic.md\n"
    )
    assert _sweep("E-500", tree).returncode == PASS


def test_sweep_is_scoped_to_the_id_it_was_given(tree: Path) -> None:
    (tree / "docs" / "other.md").write_text("see epics/E-501-different/x.md\n")
    assert _sweep("E-500", tree).returncode == PASS
    assert _sweep("E-501", tree).returncode == BLOCKED


def test_needle_is_a_literal_not_a_pattern(tree: Path) -> None:
    """-F matters: an epic slug is DATA and must not become a regex."""
    (tree / "docs" / "meta.md").write_text("epics/E-502-a.b-c\n")
    assert _sweep("E-502", tree).returncode == BLOCKED


def test_routing_table_is_reported_with_the_hits(tree: Path) -> None:
    """A hit is adjudicated by its owner, so the owner must be on screen."""
    (tree / "src" / "x.py").write_text("epics/E-500-old/story.md\n")
    err = _sweep("E-500", tree).stderr
    for owner in (
        "product-manager",
        "claude-architect",
        "software-engineer",
        "docs-writer",
    ):
        assert owner in err


# --------------------------------------------------------------------------
# AC-2 -- one epic per invocation; wildcards refused
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "arg",
    ["", "E-*", "*", "E-27", "E-2799", "epics", "E-abc", "E-500-old", "../E-500"],
)
def test_malformed_id_is_invalid_and_sweeps_nothing(tree: Path, arg: str) -> None:
    result = _sweep(arg, tree)
    assert result.returncode == INVALID, f"{arg!r} was not refused"
    assert "INVALID" in result.stderr


def test_invalid_is_distinct_from_blocked(tree: Path) -> None:
    """A gate that never ran is INVALID, not a pass -- and not a finding
    either. Collapsing 2 into 1 would make an unusable argument look like a
    real hit; collapsing it into 0 would make it look clean."""
    (tree / "src" / "x.py").write_text("epics/E-500-old/story.md\n")
    assert _sweep("E-500", tree).returncode == BLOCKED
    assert _sweep("E-*", tree).returncode == INVALID


def test_wrong_argument_count_is_invalid(tree: Path) -> None:
    assert subprocess.run([str(SCRIPT)], capture_output=True).returncode == INVALID
    assert (
        subprocess.run(
            [str(SCRIPT), "E-500", str(tree), "extra"], capture_output=True
        ).returncode
        == INVALID
    )


# --------------------------------------------------------------------------
# AC-5 -- the pre-commit backstop fires on ARCHIVING, in either staged shape
# --------------------------------------------------------------------------


def test_gate_fires_on_rename_shaped_archiving(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path / "r")
    _archive_by_rename(repo)
    assert not _commit_allowed(repo)


def test_gate_fires_on_delete_add_shaped_archiving(tmp_path: Path) -> None:
    """Rename-shape independence. A gate conditioned on ``rename from``
    passes the case above and fails this one."""
    repo = _make_repo(tmp_path / "r")
    _archive_by_delete_add(repo)
    status = _git(repo, "diff", "--cached", "--name-status", "--no-renames").stdout
    assert "\nD\tepics/E-500-old" in "\n" + status  # precondition, not the assertion
    assert not _commit_allowed(repo)


def test_clean_archiving_is_allowed(tmp_path: Path) -> None:
    """The positive control for the two cases above: the SAME archiving, with
    the surviving reference removed, must commit."""
    repo = _make_repo(tmp_path / "r")
    _archive_by_rename(repo)
    (repo / "docs" / "ref.md").write_text("see the archived epic\n")
    _git(repo, "add", "-A")
    assert not (repo / "epics" / "E-500-old").exists()  # precondition
    assert _commit_allowed(repo)


def test_red_state_modify_only_under_archived_epic(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path / "r")
    (repo / ".project" / "archive" / "E-400-done" / "epic.md").write_text("edited\n")
    _git(repo, "add", "-A")
    assert _commit_allowed(repo)


def test_red_state_add_only_under_archived_epic(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path / "r")
    (repo / ".project" / "archive" / "E-400-done" / "post.md").write_text("note\n")
    _git(repo, "add", "-A")
    assert _commit_allowed(repo)


def test_red_state_delete_only_from_live_epic(tmp_path: Path) -> None:
    """Deleting a superseded story from a LIVE epic archives nothing. A
    presence-keyed gate would block it on that epic's own cross-references."""
    repo = _make_repo(tmp_path / "r")
    _git(repo, "rm", "-q", "epics/E-500-old/E-500-01.md")
    assert _commit_allowed(repo)


def test_gate_does_not_reuse_the_staged_array(tmp_path: Path) -> None:
    """``STAGED_ARR`` is built with --diff-filter=ACMR and carries no ``D``,
    so a trigger reusing it could never observe the deletion half and would be
    permanently inert. Asserted against the source rather than by behavior:
    the inert form is shape-identical to a gate correctly declining to fire."""
    gate = HOOK.read_text().split(GATE_START)[1].split(GATE_END)[0]
    # CODE only. The comments in this block discuss STAGED_ARR at length --
    # explaining why it is not used is the opposite of using it, and an
    # assertion that cannot tell those apart would forbid documenting the
    # trap. Strip comment lines before asserting.
    code = "\n".join(
        ln for ln in gate.splitlines() if not ln.lstrip().startswith("#")
    )
    assert "--diff-filter=D" in code
    assert "--diff-filter=A" in code
    assert "--no-renames" in code
    assert "STAGED_ARR" not in code
    assert "rename from" not in code


# --------------------------------------------------------------------------
# AC-5 PLACEMENT -- the gate must sit above every early exit
# --------------------------------------------------------------------------


def test_placement_below_scanner_skip_is_inert(tmp_path: Path) -> None:
    """The discriminating case for PLACEMENT.

    The shipped hook and this mutant are byte-identical except for WHERE the
    gate block sits. With the scanner absent -- true of every scratch repo
    here, and of any checkout where ``src/safety/pii_scanner.py`` has been
    deleted -- the mutant's gate never runs and the archiving commit sails
    through. That is the RED state AC-5 names.
    """
    text = HOOK.read_text()
    start = text.index(GATE_START)
    end = text.index("\n", text.index("\n", text.index(GATE_END)) + 1) + 1
    gate, rest = text[start:end], text[:start] + text[end:]
    assert rest.count(SCANNER_SKIP) == 1, "anchor for the mutation is not unique"
    mutant = rest.replace(SCANNER_SKIP, SCANNER_SKIP + "\n" + gate)
    assert mutant != text and len(mutant) == len(text) + 1

    shipped = _make_repo(tmp_path / "shipped")
    _archive_by_rename(shipped)
    assert not _commit_allowed(shipped), "shipped hook failed to block"

    moved = _make_repo(tmp_path / "moved", hook_text=mutant)
    _archive_by_rename(moved)
    assert _commit_allowed(moved), (
        "the mutant blocked too -- this probe does not discriminate, so the "
        "shipped hook's pass says nothing about placement"
    )


def test_gate_blocks_when_its_script_is_missing(tmp_path: Path) -> None:
    """Fail-closed, and deliberately the OPPOSITE of the scanner skip four
    lines below it in the same hook. Do not harmonize them."""
    repo = _make_repo(tmp_path / "r")
    _archive_by_rename(repo)
    (repo / "docs" / "ref.md").write_text("see the archived epic\n")
    (repo / "scripts" / "check_archive_refs.sh").unlink()
    _git(repo, "add", "-A")
    assert not _commit_allowed(repo)


def test_gate_blocks_when_its_script_is_not_executable(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path / "r")
    _archive_by_rename(repo)
    (repo / "docs" / "ref.md").write_text("see the archived epic\n")
    (repo / "scripts" / "check_archive_refs.sh").chmod(0o644)
    _git(repo, "add", "-A")
    assert not _commit_allowed(repo)


def test_no_override_token_exists(tmp_path: Path) -> None:
    """AC-6. The only escape is ``git commit --no-verify``, which also
    disables the PII scan -- an operator decision, not an agent's tool."""
    gate = HOOK.read_text().split(GATE_START)[1].split(GATE_END)[0]
    for token in ("SKIP_", "NO_ARCHIVE", "ALLOW_", "archive-refs: skip", "--force"):
        assert token not in gate
