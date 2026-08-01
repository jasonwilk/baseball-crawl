"""
Integration tests for the PreToolUse worktree write guard
(`.claude/hooks/worktree-guard.sh`).

The guard decides "is a dispatch active?" by reading git's worktree REGISTRY
rather than by globbing for a directory (E-279-01). The distinction is the whole
point: a passive hook or an audit command that creates a path under
/tmp/.worktrees used to put every agent in the session into mode 1, with no
corresponding worktree registered anywhere.

Two things shape how these tests are written:

* **Nothing here may create a directory under the REAL /tmp/.worktrees.** A
  directory there blocks every agent's main-checkout writes **for as long as it
  exists** -- so AC-7's primary conjunct is "no test CREATES one", and "none is
  left behind" is the secondary, aggravating case. Every test that needs a
  directory to be PRESENT plants it under an injected root
  (`BB_WORKTREE_ROOT`), and the registry branches are driven by a stubbed `git`
  on PATH.

  **Two layers enforce this, and the first is the load-bearing one:**

  1. An autouse fixture patches **`os.mkdir`** to raise for any target at or
     under the real root. `Path.mkdir`, `Path.mkdir(parents=True)` and
     `os.makedirs` all funnel through it, so mkdir is blocked **by
     construction, whether or not the root exists**.

     **The reach, at its actual strength** (code-reviewer, E-279 P1-2,
     established by construction): layer 1 binds every location decision it can
     see -- in-process creations directly, and subprocess creations
     TRANSITIVELY when the subprocess's target directory was itself created
     in-process. Layer 2 backstops any creation that reaches the real root by a
     path layer 1 never saw -- including a subprocess given an absolute path it
     did not have to create first.

     Concretely: the GIT_DIR reachability test runs `git init` through
     `subprocess.run`, the only subprocess-mediated creation in this file. It is
     contained because it creates its parent in-process FIRST
     (``foreign = tmp_path / "foreign"; foreign.mkdir()``) and that `Path.mkdir`
     goes through the patched `os.mkdir` -- so a target under the real root
     raises before any child process is handed a `cwd`. It uses real git rather
     than a hand-built `.git` fixture deliberately: that test's whole value is
     that it uses real git with no stub, which a fixture would undermine.

     ⚠️ **That containment is a CONVENTION, not an enforcement.** A future test
     doing `subprocess.run(["mkdir", "-p", str(some_path)])` with a computed
     absolute path skips layer 1 entirely and is caught only by layer 2.

     **This wording is deliberately NARROWER than the patch, and it is the third
     generation on this point** -- `_plant_worktree` "inexpressible", then
     "whatever code path attempts it", now this. Each earlier restatement of
     layer 1's reach was one step wider than what the code binds. **Do not tidy
     it into something cleaner.**
  2. A session-scoped fixture compares the child set **and the root's mtime**,
     catching anything that reached the filesystem despite layer 1.

  **A snapshot alone is NOT the guarantee.** An earlier version of this file said
  so here, and it was the misconception that put four instruments on the wrong
  axis: before/after comparison is a leak detector and a non-detector of
  creation -- `create; remove; before == after` passes it.

* **The pre-fix hook cannot exhibit the headline RED**, because it globs
  /tmp/.worktrees unconditionally and is blind to an injected root -- so against
  these tests it allows, and they pass. The RED that matters pins the BEHAVIOUR
  (detection must not be a directory glob), and it is reachable here: the same
  planted directory under the same root yields ALLOW through the registry branch
  and DENY through the glob fallback. Detection reverting to a glob is the
  regression these tests genuinely catch.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HOOK = PROJECT_ROOT / ".claude" / "hooks" / "worktree-guard.sh"

# Resolved once, at import: the jq fail-open test hands the child an emptied
# PATH, and a bare "bash" would then fail to launch at all -- a green that says
# nothing about the hook.
BASH = shutil.which("bash") or "/bin/bash"

MAIN_PREFIX = "/workspaces/baseball-crawl/"
EPIC_SUFFIX = "baseball-crawl-E-999"

# The real root, referenced ONLY to assert it stays clean. Never created here.
REAL_ROOT = Path("/tmp") / ".worktrees"

# Porcelain output for a checkout with no epic worktree registered. The main
# checkout line is always present in a successful run -- the guard uses it as a
# positive control (see AC-4).
MAIN_ONLY = "worktree /workspaces/baseball-crawl\nHEAD abc123\nbranch refs/heads/main\n"

# Porcelain output that exits 0 but carries no `worktree` line at all: an
# instrument failure, NOT an authoritative "no dispatch" answer.
NO_CONTROL_LINE = "HEAD abc123\nbranch refs/heads/main\n"


def _registry_with_epic(worktree_path: str, prunable: bool = False) -> str:
    """Porcelain output listing the main checkout plus one epic worktree."""
    entry = f"worktree {worktree_path}\nHEAD def456\nbranch refs/heads/epic/E-999\n"
    if prunable:
        entry += "prunable gitdir file points to non-existent location\n"
    return MAIN_ONLY + "\n" + entry


def _git_stub(bin_dir: Path, stdout: str = "", exit_code: int = 0) -> Path:
    """Put a fake `git` on PATH that replays canned porcelain output."""
    bin_dir.mkdir(parents=True, exist_ok=True)
    stub = bin_dir / "git"
    stub.write_text(
        "#!/bin/bash\ncat <<'EOF_STUB'\n" + stdout + f"EOF_STUB\nexit {exit_code}\n"
    )
    stub.chmod(0o755)
    return bin_dir


def _run(
    file_path: str,
    *,
    root: str | None = None,
    stub_bin: Path | None = None,
    path_override: str | None = None,
    hook: Path | None = None,
    tool_name: str = "Write",
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Invoke the guard with a PreToolUse payload on stdin.

    ``extra_env`` exists so the GIT_DIR reachability case can be exercised
    against the REAL git binary rather than a stub -- the P1-2 fail-open was
    reachable through an inherited environment variable, and a stubbed `git`
    cannot demonstrate that it is reachable without one.
    """
    env = os.environ.copy()
    if root is None:
        env.pop("BB_WORKTREE_ROOT", None)
    else:
        env["BB_WORKTREE_ROOT"] = root
    if extra_env:
        env.update(extra_env)
    if path_override is not None:
        env["PATH"] = path_override
    elif stub_bin is not None:
        env["PATH"] = f"{stub_bin}:{env['PATH']}"
    payload = {"tool_name": tool_name, "tool_input": {"file_path": file_path}}
    return subprocess.run(
        [BASH, str(HOOK if hook is None else hook)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
    )


def _decision(result: subprocess.CompletedProcess[str]) -> dict:
    assert result.returncode == 0, "the guard always exits 0, even on denial"
    assert result.stdout.strip(), "expected a denial payload, got no output"
    return json.loads(result.stdout)["hookSpecificOutput"]


def _assert_denied(result: subprocess.CompletedProcess[str]) -> str:
    decision = _decision(result)
    assert decision["permissionDecision"] == "deny"
    return decision["permissionDecisionReason"]


def _assert_allowed(result: subprocess.CompletedProcess[str]) -> None:
    assert result.returncode == 0
    assert result.stdout.strip() == "", f"expected ALLOW, got {result.stdout!r}"


def _real_root_state(root: Path = REAL_ROOT) -> tuple[frozenset, int | None]:
    """AC-7 detector: the child set AND the root's own mtime.

    The set alone detects a LEAK -- a directory still present at teardown. It does
    NOT detect CREATION. A test that makes a directory and removes it before
    teardown leaves `before == after`, yet it put every agent on the machine into
    mode 1 for as long as it existed, which is precisely the defect this story
    closes. AC-7's RED is "any test that creates, OR CAN LEAVE BEHIND, a directory
    under the literal /tmp/.worktrees/" -- two conjuncts, and a snapshot pair sees
    only the second.

    Creating or removing a child updates the PARENT directory's mtime, and that
    does not revert when the child is removed, so this pair catches the transient
    case the set cannot see. Verified against the counterexample in
    `test_ac7_detector_sees_transient_creation`.
    """
    if not root.exists():
        return frozenset(), None
    return frozenset(root.glob("baseball-crawl-E-*")), root.stat().st_mtime_ns


def _is_forbidden_target(target: Path, real: Path) -> bool:
    """Pure predicate: would creating `target` land at or under `real`?

    Split out so the enforcement can be tested against the REAL root **without
    attempting a creation that could succeed**. That distinction is not academic:
    a mutation probe that disabled the guard while the tests still aimed `mkdir`
    at `/tmp/.worktrees` created two real directories there, i.e. the probe
    verifying AC-7 committed AC-7's violation. Predicate tests use the real
    constant; behavioural tests use a stand-in root, so no test in this file can
    ever attempt a creation that lands under the real one.
    """
    resolved = target if target.is_absolute() else Path.cwd() / target
    try:
        resolved = resolved.resolve()
    except OSError:  # pragma: no cover - resolve() is non-strict here
        pass
    return resolved == real or real in resolved.parents


def _make_mkdir_guard(real: Path, original):
    """Build an `os.mkdir` replacement that refuses targets at/under `real`.

    `os.mkdir` is the chokepoint on purpose: `Path.mkdir` and `os.makedirs` both
    funnel through it, so ONE patch binds all three. Patching `Path.mkdir`
    instead -- the previous form -- left `os.mkdir` and `os.makedirs` able to
    create under the real root, measured.
    """

    def guarded(path, *args, **kwargs):
        if _is_forbidden_target(Path(path), real):
            raise AssertionError(
                f"AC-7: refusing to create {path} at or under the real worktree "
                f"root {real}. A directory there puts every agent in the session "
                "into mode 1 for as long as it exists -- the defect this story "
                "closes. Plant it under an injected BB_WORKTREE_ROOT."
            )
        return original(path, *args, **kwargs)

    return guarded


@pytest.fixture(autouse=True)
def _forbid_real_root_mkdir():
    """AC-7's FIRST conjunct, enforced by construction: creating anything at or
    under the real worktree root raises on **every in-process Python mkdir
    path** -- `Path.mkdir`, `Path.mkdir(parents=True)`, `os.makedirs` and
    `os.mkdir`, all of which funnel through the patched `os.mkdir`.

    **Stated bound, because the claim here has outrun the patch twice already:**
    creation from a **subprocess** (a shell `mkdir`) is NOT bound, and no
    in-process patch can bind it. Generation 1 of this docstring claimed
    `_plant_worktree` made the conjunct "inexpressible" -- false, ten bare
    `.mkdir()` calls bypassed it. Generation 2 patched `Path.mkdir` and claimed
    "whatever code path attempts it" -- false, `os.mkdir` and `os.makedirs`
    bypassed it, measured. Each repair closed the bypass set just named and then
    claimed a larger one. This sentence is deliberately narrower than the patch's
    reach rather than wider.

    This is the enforcement; `_plant_worktree` below is only a convenience. An
    earlier form of this file claimed the helper made creation "inexpressible",
    which was false -- ten bare `root.mkdir()` calls, the stub-bin `mkdir`, and a
    direct `baseball-crawl-E-*` create inside the detector's own test all bypass
    it. They are safe because they sit under `tmp_path`, but a convention is not
    an enforcement, and the word was doing work the code did not do.

    Patching the creation call closes the conjunct **independently of whether the
    root exists**, which the snapshot detector cannot do: on a machine that has
    never dispatched, a test creating the root and a child and cleaning both up
    leaves `(frozenset(), None)` at both ends and is invisible. Measured, not
    reasoned -- see the test below that asserts that blind value as a PRECONDITION
    and then attempts the creation against a stand-in root.
    """
    original = os.mkdir
    os.mkdir = _make_mkdir_guard(REAL_ROOT.resolve(), original)
    try:
        yield
    finally:
        os.mkdir = original


def _plant_worktree(root: Path, name: str = EPIC_SUFFIX) -> Path:
    """Create a worktree directory for a test, under an injected root.

    Convenience with a local check, NOT the enforcement -- `_forbid_real_root_mkdir`
    above is what actually closes AC-7's first conjunct, because it binds every
    creation path rather than the ones that happen to call this.
    """
    target = (root / name).resolve()
    assert REAL_ROOT.resolve() not in target.parents, (
        f"AC-7: refusing to create {target} under the real worktree root -- a "
        "directory there puts every agent in the session into mode 1 for as long "
        "as it exists. Plant it under an injected BB_WORKTREE_ROOT instead."
    )
    target.mkdir(parents=True)
    return target


@pytest.fixture(scope="session", autouse=True)
def _real_worktree_root_untouched():
    """AC-7: no test may create a directory under the REAL worktree root.

    Enforces the criterion rather than approximating it. The previous form
    compared only the child set before and after, which is a leak detector and a
    non-detector of creation -- `create; remove; assert before == after` passes it
    (found by Codex, after four of us had passed the fixture).

    A false positive is possible if something outside this suite touches
    /tmp/.worktrees while it runs. That is a loud failure in the conservative
    direction, which is the correct trade under this repo's fail-closed doctrine.
    Inert when the root does not exist, which is the normal state on a machine
    that has never dispatched.
    """
    before = _real_root_state()
    yield
    after = _real_root_state()
    leaked = after[0] - before[0]
    assert not leaked, f"the test suite created real worktree directories: {leaked}"
    assert before[1] == after[1], (
        f"AC-7: {REAL_ROOT} changed during the suite (mtime {before[1]} -> "
        f"{after[1]}) while its contents look unchanged. A worktree directory was "
        "created under the REAL root and removed again -- which wedges every agent "
        "for as long as it exists. Use _plant_worktree() under an injected root."
    )


class TestAC7GuardItself:
    """The AC-7 guard must fail on purpose before it is trusted.

    Codex found the previous fixture enforced "no leak by session end" rather than
    AC-7's "no test creates a real worktree dir" -- a perfectly good leak detector
    and a non-detector of creation. Four reviewers passed it, because everyone
    compared it to the single-path version it replaced instead of to the criterion.
    These two tests are the discrimination evidence for its replacement.
    """

    def test_ac7_detector_sees_transient_creation(self, tmp_path: Path) -> None:
        """Codex's counterexample, run against a STAND-IN root.

        The real root is never touched -- which is the point, and also why the
        detector had to be a pure function of a root rather than a closure over
        the real one.
        """
        fake_root = tmp_path / "worktrees"
        fake_root.mkdir()
        before = _real_root_state(fake_root)

        transient = fake_root / EPIC_SUFFIX
        transient.mkdir()
        transient.rmdir()  # gone before "teardown" -- the whole counterexample

        after = _real_root_state(fake_root)
        assert after[0] == before[0], (
            "precondition: the child SET must look unchanged, otherwise this test "
            "is not exercising the case the old fixture missed"
        )
        assert after[1] != before[1], (
            "the detector must see transient creation via the parent mtime; if "
            "this fails the fixture has reverted to a pure leak detector"
        )

    def test_plant_worktree_refuses_the_real_root(self) -> None:
        """The helper's local check. Not the enforcement -- see the two below."""
        with pytest.raises(AssertionError, match="refusing to create"):
            _plant_worktree(REAL_ROOT)
        assert not (REAL_ROOT / EPIC_SUFFIX).exists()

    def test_ac7_predicate_forbids_the_real_root_paths(self) -> None:
        """PURE check against the REAL constant -- creates nothing.

        This is the bypass CR enumerated: a bare `root.mkdir()` reaching the real
        root would have been permitted by a helper-only convention. Asserted on
        the predicate rather than by calling `mkdir`, because a broken guard plus
        a real-root `mkdir` call is how the probe for this AC violated it.
        """
        real = REAL_ROOT.resolve()
        assert _is_forbidden_target(REAL_ROOT / EPIC_SUFFIX, real)
        assert _is_forbidden_target(REAL_ROOT, real)
        assert _is_forbidden_target(REAL_ROOT / "never-dispatched" / EPIC_SUFFIX, real), (
            "the residual branch: enforcement must not depend on the root or any "
            "intermediate directory already existing"
        )
        assert not _is_forbidden_target(Path("/tmp/somewhere-else/x"), real)

    def test_ac7_guard_raises_on_a_bare_mkdir(self, tmp_path: Path) -> None:
        """BEHAVIOURAL check against a STAND-IN root, so a broken guard is harmless.

        Covers the branch `_real_root_state` is structurally blind to: with the
        root absent, creating it AND a child and cleaning both up leaves
        `(frozenset(), None)` at both ends. The guard fires on the creation
        instead, independently of whether anything exists.
        """
        stand_in = (tmp_path / "worktrees").resolve()  # deliberately NOT created
        assert _real_root_state(stand_in) == (frozenset(), None), (
            "precondition: the detector returns its blind value for an absent root"
        )
        guarded = _make_mkdir_guard(stand_in, os.mkdir)
        with pytest.raises(AssertionError, match="AC-7"):
            guarded(stand_in / EPIC_SUFFIX)
        with pytest.raises(AssertionError, match="AC-7"):
            guarded(stand_in / "nested" / EPIC_SUFFIX)
        assert not stand_in.exists(), "a refused mkdir must create nothing"

    def test_ac7_guard_FIRES_on_a_real_attempted_violation(self) -> None:
        """PM's standard: demonstrate the guard FIRING on a deliberate violation
        under the REAL root -- not an argument that it would.

        Blast-radius limited on purpose. If the guard ever regresses, the finally
        clause removes whatever was created, so a regression costs a transient
        directory instead of a wedge that outlives the run -- and the assertion
        still fails loudly. That limiter is not decoration: disabling this guard
        during a mutation probe is what created two real directories under
        /tmp/.worktrees earlier in this story.
        """
        victim = REAL_ROOT / EPIC_SUFFIX
        try:
            with pytest.raises(AssertionError, match="AC-7"):
                victim.mkdir(parents=True)
        finally:
            if victim.exists():
                victim.rmdir()
        assert not victim.exists()

    def test_ac7_guard_FIRES_on_a_real_violation_below_an_absent_path(self) -> None:
        """The absent-parent branch, exercised against the REAL root.

        The truly-absent-ROOT case cannot be exercised against the real constant
        without removing a live worktree directory, so it is covered
        behaviourally by the stand-in test above. This covers the reachable half:
        an absent intermediate under the real root, where `parents=True` would
        otherwise create the chain.
        """
        nested = REAL_ROOT / "never-dispatched" / EPIC_SUFFIX
        try:
            with pytest.raises(AssertionError, match="AC-7"):
                nested.mkdir(parents=True)
        finally:
            shutil.rmtree(REAL_ROOT / "never-dispatched", ignore_errors=True)
        assert not (REAL_ROOT / "never-dispatched").exists()

    def test_ac7_guard_binds_all_in_process_creation_apis(self, tmp_path: Path) -> None:
        """The bypass that falsified generation 2's claim, against a stand-in root.

        Patching `Path.mkdir` bound one API; `os.mkdir` and `os.makedirs` created
        freely (measured). `os.mkdir` is the chokepoint all three funnel through,
        so one patch binds them. The harmless-sibling control proves the guard is
        discriminating rather than refusing everything -- without it, a guard that
        raised unconditionally would pass every assertion above.
        """
        stand_in = (tmp_path / "worktrees").resolve()
        stand_in.mkdir()
        guarded = _make_mkdir_guard(stand_in, os.mkdir)
        original, os.mkdir = os.mkdir, guarded
        try:
            with pytest.raises(AssertionError, match="AC-7"):
                (stand_in / "via-pathlib").mkdir()
            with pytest.raises(AssertionError, match="AC-7"):
                (stand_in / "via-parents" / "child").mkdir(parents=True)
            with pytest.raises(AssertionError, match="AC-7"):
                os.makedirs(stand_in / "via-makedirs")
            with pytest.raises(AssertionError, match="AC-7"):
                os.mkdir(stand_in / "via-os-mkdir")
            (tmp_path / "harmless-sibling").mkdir()  # control: must succeed
        finally:
            os.mkdir = original
        assert (tmp_path / "harmless-sibling").is_dir()
        assert not any(stand_in.iterdir()), "nothing may have been created"

    def test_guard_does_not_false_positive_on_tmp_path(self, tmp_path: Path) -> None:
        """Ordinary suite usage must be unaffected, including nested creation."""
        (tmp_path / "a" / "b").mkdir(parents=True)
        assert (tmp_path / "a" / "b").is_dir()


@pytest.mark.integration
class TestAuthoritativeRead:
    """AC-1: a directory git does not report is not a dispatch."""

    def test_unregistered_directory_does_not_block(self, tmp_path: Path) -> None:
        # A directory EXISTS under the root; the registry reports no epic
        # worktree. The write is ALLOWED -- the defect under repair.
        root = tmp_path / "worktrees"
        _plant_worktree(root)
        stub = _git_stub(tmp_path / "bin", MAIN_ONLY)
        result = _run(
            f"{MAIN_PREFIX}docs/notes.md", root=str(root), stub_bin=stub
        )
        _assert_allowed(result)

    def test_same_directory_denies_through_the_glob_fallback(
        self, tmp_path: Path
    ) -> None:
        """The RED, executed: same directory, same root, glob detector DENIES.

        This is the behaviour AC-1 pins. The glob is still reachable in the
        shipped hook (it is the registry-unreadable fallback), so the contrast
        is demonstrable without mutating anything: swap the detector and the
        answer flips on identical inputs. A detection block that reverted to a
        glob would make the test above fail exactly here.
        """
        root = tmp_path / "worktrees"
        _plant_worktree(root)
        stub = _git_stub(tmp_path / "bin", "", exit_code=1)  # forces the glob
        result = _run(
            f"{MAIN_PREFIX}docs/notes.md", root=str(root), stub_bin=stub
        )
        reason = _assert_denied(result)
        assert "Dispatch is active" in reason

    def test_distinguishable_from_the_no_directory_case(
        self, tmp_path: Path
    ) -> None:
        """AC-1 and AC-5 must not collapse onto one another.

        AC-5 is "no directory, registry says no dispatch"; AC-1 is "directory
        present, registry says no dispatch". Both allow, but only AC-1's arm has
        a directory for a glob to find -- which is why the test above can go red.
        """
        root = tmp_path / "worktrees"
        root.mkdir()
        stub = _git_stub(tmp_path / "bin", MAIN_ONLY)
        _assert_allowed(
            _run(f"{MAIN_PREFIX}docs/notes.md", root=str(root), stub_bin=stub)
        )
        assert not (root / EPIC_SUFFIX).exists()


@pytest.mark.integration
class TestInjectedRoot:
    """AC-1b: the root variable and its five bounds."""

    def test_one_variable_governs_the_glob_fallback_too(
        self, tmp_path: Path
    ) -> None:
        """Bound 1: the fallback resolves through the SAME variable.

        If the fallback still globbed a hard-coded /tmp/.worktrees it would find
        nothing here and allow.
        """
        root = tmp_path / "worktrees"
        _plant_worktree(root)
        stub = _git_stub(tmp_path / "bin", "", exit_code=1)
        reason = _assert_denied(
            _run(f"{MAIN_PREFIX}docs/notes.md", root=str(root), stub_bin=stub)
        )
        assert str(root / EPIC_SUFFIX) in reason

    def test_set_but_missing_root_fails_closed(self, tmp_path: Path) -> None:
        """Bound 2: a typo is a misconfiguration, not a "no dispatch" answer."""
        missing = tmp_path / "does-not-exist"
        stub = _git_stub(tmp_path / "bin", MAIN_ONLY)
        reason = _assert_denied(
            _run(f"{MAIN_PREFIX}docs/notes.md", root=str(missing), stub_bin=stub)
        )
        assert "BB_WORKTREE_ROOT" in reason

    def test_missing_root_precedes_the_registry_read(self, tmp_path: Path) -> None:
        """Bound 2 precedence: it beats AC-5, which would otherwise allow.

        git lists worktrees whether or not the configured root exists, so with a
        set-but-missing root AND a readable registry both rules apply and
        disagree. The precondition wins and AC-3/AC-4/AC-5 are not reached.
        """
        missing = tmp_path / "does-not-exist"
        stub = _git_stub(tmp_path / "bin", MAIN_ONLY)  # AC-5's exact input
        reason = _assert_denied(
            _run(f"{MAIN_PREFIX}docs/notes.md", root=str(missing), stub_bin=stub)
        )
        assert "BB_WORKTREE_ROOT" in reason

    def test_missing_DEFAULT_root_must_not_fail_closed(self, tmp_path: Path) -> None:
        """Bound 2 is SET-ONLY. Generalising it to the default bricks the repo.

        An absent default root is NORMAL -- /tmp/.worktrees need not exist when
        no dispatch has ever run -- so failing closed there would deny every
        main-checkout write in every session with no dispatch running.

        This RED is not constructible against the real default: /tmp/.worktrees
        exists on any machine that has dispatched, so the obvious "unset the
        variable and expect ALLOW" test passes either way and hides the defect
        precisely where it would be tested. So the probe MUTATES only the default
        value to a path that does not exist, leaving every other byte alone. The
        mutant is written to tmp_path; the real hook is never touched.
        """
        absent = tmp_path / "never-created"
        source = HOOK.read_text()
        original = 'WT_ROOT="${BB_WORKTREE_ROOT:-/tmp/.worktrees}"'
        # Anti-vacuity: a mutation that never applied reports the same green as
        # one that did. Assert, do not warn -- a discarded alarm is not a check.
        assert source.count(original) == 1, "default-root line moved; probe is vacuous"
        mutant = tmp_path / "worktree-guard-mutant.sh"
        mutant.write_text(
            source.replace(original, f'WT_ROOT="${{BB_WORKTREE_ROOT:-{absent}}}"')
        )
        assert not absent.exists()

        stub = _git_stub(tmp_path / "bin", MAIN_ONLY)
        # BB_WORKTREE_ROOT unset, default root absent, no dispatch registered.
        _assert_allowed(
            _run(f"{MAIN_PREFIX}docs/notes.md", stub_bin=stub, hook=mutant)
        )

    def test_default_root_is_the_literal_tmp_worktrees(self, tmp_path: Path) -> None:
        """Bound 3: unset behaves as production does.

        Driven entirely through the registry, so no directory is created
        anywhere: the stub names a worktree under the literal default root and
        the guard must recognise it as a dispatch.
        """
        stub = _git_stub(
            tmp_path / "bin",
            _registry_with_epic(f"/tmp/.worktrees/{EPIC_SUFFIX}"),
        )
        reason = _assert_denied(_run(f"{MAIN_PREFIX}docs/notes.md", stub_bin=stub))
        assert "Dispatch is active" in reason
        assert not (REAL_ROOT / EPIC_SUFFIX).exists()

    def test_set_but_wrong_root_fails_closed(self, tmp_path: Path) -> None:
        """Bound 5: an epic registered outside the configured root.

        RED: mode 2 here. The root-anchored match finds nothing, so without the
        mismatch check the guard would run unguarded beside a live dispatch --
        which is exactly where AC-2's unqualified guarantee would be false.
        """
        wrong = tmp_path / "elsewhere"
        wrong.mkdir()
        stub = _git_stub(
            tmp_path / "bin",
            _registry_with_epic(f"/tmp/.worktrees/{EPIC_SUFFIX}"),
        )
        reason = _assert_denied(
            _run(f"{MAIN_PREFIX}docs/notes.md", root=str(wrong), stub_bin=stub)
        )
        assert "BB_WORKTREE_ROOT" in reason

    def test_mismatch_check_is_inert_when_unset(self, tmp_path: Path) -> None:
        """Bound 5 must not change production behaviour."""
        stub = _git_stub(tmp_path / "bin", MAIN_ONLY)
        _assert_allowed(_run(f"{MAIN_PREFIX}docs/notes.md", stub_bin=stub))


@pytest.mark.integration
class TestCrashedDispatch:
    """AC-2: a registered worktree whose directory is gone still enforces."""

    def test_prunable_worktree_denies(self, tmp_path: Path) -> None:
        root = tmp_path / "worktrees"
        root.mkdir()
        gone = root / EPIC_SUFFIX  # registered, never created: the crash state
        stub = _git_stub(
            tmp_path / "bin", _registry_with_epic(str(gone), prunable=True)
        )
        reason = _assert_denied(
            _run(f"{MAIN_PREFIX}docs/notes.md", root=str(root), stub_bin=stub)
        )
        assert "Dispatch is active" in reason
        assert not gone.exists()  # the glob would have gone quiet here


@pytest.mark.integration
class TestRegistryFailureFallsBack:
    """AC-3 / AC-4: an unusable registry falls back, it does not answer."""

    @pytest.mark.parametrize("exit_code", [1, 127])
    def test_nonzero_exit_falls_back_to_the_glob(
        self, tmp_path: Path, exit_code: int
    ) -> None:
        # 127 is what the command substitution carries when `git` is absent.
        root = tmp_path / "worktrees"
        _plant_worktree(root)
        stub = _git_stub(tmp_path / "bin", "", exit_code=exit_code)
        reason = _assert_denied(
            _run(f"{MAIN_PREFIX}docs/notes.md", root=str(root), stub_bin=stub)
        )
        assert "Dispatch is active" in reason

    def test_nonzero_exit_without_a_directory_allows(self, tmp_path: Path) -> None:
        # The fallback is the old glob, so its no-directory answer is mode 2 --
        # unchanged conservatism, not a new fail-open.
        root = tmp_path / "worktrees"
        root.mkdir()
        stub = _git_stub(tmp_path / "bin", "", exit_code=1)
        _assert_allowed(
            _run(f"{MAIN_PREFIX}docs/notes.md", root=str(root), stub_bin=stub)
        )

    def test_zero_exit_with_no_control_line_is_a_failure_not_an_answer(
        self, tmp_path: Path
    ) -> None:
        """AC-4: empty of `worktree` lines means the instrument failed.

        A successful run ALWAYS lists the main checkout. Treating this as "no
        dispatch" is what re-creates the defect, so it must fall back to the
        glob -- which finds the planted directory and denies.
        """
        root = tmp_path / "worktrees"
        _plant_worktree(root)
        stub = _git_stub(tmp_path / "bin", NO_CONTROL_LINE, exit_code=0)
        reason = _assert_denied(
            _run(f"{MAIN_PREFIX}docs/notes.md", root=str(root), stub_bin=stub)
        )
        assert "Dispatch is active" in reason


@pytest.mark.integration
class TestAuthoritativeNoDispatch:
    """AC-5: a readable registry with no epic worktree is an ANSWER."""

    def test_control_line_present_no_epic_allows(self, tmp_path: Path) -> None:
        root = tmp_path / "worktrees"
        root.mkdir()
        stub = _git_stub(tmp_path / "bin", MAIN_ONLY)
        _assert_allowed(
            _run(f"{MAIN_PREFIX}docs/notes.md", root=str(root), stub_bin=stub)
        )

    def test_no_dispatch_still_denies_implementation_paths(
        self, tmp_path: Path
    ) -> None:
        root = tmp_path / "worktrees"
        root.mkdir()
        stub = _git_stub(tmp_path / "bin", MAIN_ONLY)
        reason = _assert_denied(
            _run(f"{MAIN_PREFIX}src/foo.py", root=str(root), stub_bin=stub)
        )
        assert "Implementation files" in reason


@pytest.mark.integration
class TestPinnedBehaviour:
    """AC-6: the five behaviours the change must not disturb."""

    def _dispatch_active(self, tmp_path: Path) -> tuple[str, Path]:
        root = tmp_path / "worktrees"
        root.mkdir()
        stub = _git_stub(
            tmp_path / "bin", _registry_with_epic(str(root / EPIC_SUFFIX))
        )
        return str(root), stub

    def test_mode_1_has_no_agent_memory_carve_out(self, tmp_path: Path) -> None:
        root, stub = self._dispatch_active(tmp_path)
        reason = _assert_denied(
            _run(
                f"{MAIN_PREFIX}.claude/agent-memory/claude-architect/MEMORY.md",
                root=root,
                stub_bin=stub,
            )
        )
        assert "Dispatch is active" in reason
        assert "ride the closure patch" in reason

    def test_mode_1_denies_a_documentation_path(self, tmp_path: Path) -> None:
        root, stub = self._dispatch_active(tmp_path)
        _assert_denied(_run(f"{MAIN_PREFIX}docs/x.md", root=root, stub_bin=stub))

    def test_parent_dir_segment_rejected(self, tmp_path: Path) -> None:
        root = tmp_path / "worktrees"
        root.mkdir()
        stub = _git_stub(tmp_path / "bin", MAIN_ONLY)
        reason = _assert_denied(
            _run(f"{MAIN_PREFIX}docs/../src/foo.py", root=str(root), stub_bin=stub)
        )
        assert '".." segment' in reason

    def test_double_slash_is_normalised_before_the_denylist(
        self, tmp_path: Path
    ) -> None:
        root = tmp_path / "worktrees"
        root.mkdir()
        stub = _git_stub(tmp_path / "bin", MAIN_ONLY)
        reason = _assert_denied(
            _run(f"{MAIN_PREFIX}/src/foo.py", root=str(root), stub_bin=stub)
        )
        assert "Implementation files" in reason

    def test_worktree_paths_always_pass(self, tmp_path: Path) -> None:
        """The pass-through keys on the main-checkout prefix, not on the root.

        It therefore holds under any root, including a dispatch-active one.
        """
        root, stub = self._dispatch_active(tmp_path)
        _assert_allowed(
            _run(f"/tmp/.worktrees/{EPIC_SUFFIX}/src/foo.py", root=root, stub_bin=stub)
        )

    def test_missing_jq_fails_open(self, tmp_path: Path) -> None:
        empty_path = tmp_path / "empty-bin"
        empty_path.mkdir()
        result = _run(
            f"{MAIN_PREFIX}src/foo.py", path_override=str(empty_path)
        )
        _assert_allowed(result)

    def test_no_file_path_allows(self, tmp_path: Path) -> None:
        stub = _git_stub(tmp_path / "bin", MAIN_ONLY)
        env = os.environ.copy()
        env.pop("BB_WORKTREE_ROOT", None)
        env["PATH"] = f"{stub}:{env['PATH']}"
        result = subprocess.run(
            [BASH, str(HOOK)],
            input=json.dumps({"tool_name": "Write", "tool_input": {}}),
            capture_output=True,
            text=True,
            env=env,
        )
        _assert_allowed(result)


# Porcelain output that exits 0 and DOES carry `worktree` lines -- but describes
# a DIFFERENT repository, so this checkout is absent. Shape-identical to a valid
# answer for every test the original control could run.
FOREIGN_ONLY = (
    "worktree /srv/some-other-repo\nHEAD abc123\nbranch refs/heads/master\n"
)


@pytest.mark.integration
class TestForeignRegistryAnswer:
    """E-279 P1-2: a zero-exit registry that does not list THIS checkout.

    Found by Codex, reproduced by the code-reviewer against real git. The
    original control tested for any `^worktree ` line, while the comment
    justifying it appealed to the MAIN CHECKOUT always being listed -- so an
    answer about a different repository passed the control, matched no epic
    worktree, and dropped the guard to mode 2.

    The case set here is derived from the PROPERTY (does the registry answer
    about THIS checkout?) rather than from AC-4's text, which said "no
    `^worktree ` line at all" and is satisfied by the pre-fix code. Deriving
    cases from the criterion is what let this through the first time.
    """

    def test_foreign_registry_falls_back_to_glob_and_denies(
        self, tmp_path: Path
    ) -> None:
        """The fail-open, stated as its RED: pre-fix this ALLOWED."""
        root = tmp_path / "worktrees"
        _plant_worktree(root)
        stub = _git_stub(tmp_path / "bin", FOREIGN_ONLY, exit_code=0)
        reason = _assert_denied(
            _run(f"{MAIN_PREFIX}docs/notes.md", root=str(root), stub_bin=stub)
        )
        assert "Dispatch is active" in reason

    def test_foreign_registry_with_no_planted_dir_allows(
        self, tmp_path: Path
    ) -> None:
        """The fallback is the glob, not a blanket deny: with nothing planted,
        the conservative pre-E-279 answer is still ALLOW. Without this the case
        above would also pass against a guard that simply denied on anomaly."""
        root = tmp_path / "worktrees"
        root.mkdir(parents=True)
        stub = _git_stub(tmp_path / "bin", FOREIGN_ONLY, exit_code=0)
        _assert_allowed(
            _run(f"{MAIN_PREFIX}docs/notes.md", root=str(root), stub_bin=stub)
        )

    def test_main_checkout_line_must_match_whole_and_literal(
        self, tmp_path: Path
    ) -> None:
        """A path that merely CONTAINS the main checkout's path is a different
        worktree. Substring matching would readmit the fail-open through any
        sibling directory sharing the prefix."""
        root = tmp_path / "worktrees"
        _plant_worktree(root)
        near_miss = (
            "worktree /workspaces/baseball-crawl-other\n"
            "HEAD abc123\nbranch refs/heads/main\n"
        )
        stub = _git_stub(tmp_path / "bin", near_miss, exit_code=0)
        reason = _assert_denied(
            _run(f"{MAIN_PREFIX}docs/notes.md", root=str(root), stub_bin=stub)
        )
        assert "Dispatch is active" in reason

    @pytest.mark.parametrize("var", ["GIT_DIR", "GIT_COMMON_DIR"])
    def test_inherited_git_env_var_does_not_open_the_guard(
        self, tmp_path: Path, var: str
    ) -> None:
        """Reachability, against REAL git -- no stub anywhere in this test.

        This is what makes the finding a fail-open rather than a curiosity: an
        ordinary environment variable inherited by the hook's process, not a
        hostile binary on PATH. Severity is the reachability, not the shape.
        """
        foreign = tmp_path / "foreign"
        foreign.mkdir()
        for args in (
            ["init", "-q", "."],
            ["config", "user.email", "t@example.invalid"],
            ["config", "user.name", "t"],
            ["commit", "-q", "--allow-empty", "-m", "x"],
        ):
            subprocess.run(["git", *args], cwd=foreign, check=True,
                           capture_output=True)

        # Precondition: the poisoned call really does answer about the OTHER
        # repo, exit 0, with this checkout absent. Without this the test could
        # pass for the wrong reason on a machine where the var is ignored.
        probe = subprocess.run(
            ["git", "-C", MAIN_PREFIX.rstrip("/"), "worktree", "list",
             "--porcelain"],
            capture_output=True, text=True,
            env={**os.environ, var: str(foreign / ".git")},
        )
        assert probe.returncode == 0
        assert "worktree " in probe.stdout
        assert f"worktree {MAIN_PREFIX.rstrip('/')}\n" not in probe.stdout

        root = tmp_path / "worktrees"
        _plant_worktree(root)
        reason = _assert_denied(
            _run(
                f"{MAIN_PREFIX}docs/notes.md",
                root=str(root),
                extra_env={var: str(foreign / ".git")},
            )
        )
        assert "Dispatch is active" in reason
