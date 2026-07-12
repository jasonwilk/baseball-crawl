"""Guard: no `.dockerignore` pattern excludes a path the Dockerfile COPYs.

This is the only executable assertion `.dockerignore` can carry without a Docker
daemon. A *security* assertion -- "does the built context omit .env?" -- is not
feasible here; that requires a real build. This test guards the other failure
mode: an ignore pattern that silently starves a `COPY`, breaking the image build.

Why `fnmatch` is a sound matcher for this check -- on one axis, and not the other
--------------------------------------------------------------------------------
Python's `fnmatch` and Docker's pattern matcher differ on **two** axes, and they
point in **opposite directions**. Both must be handled, and only one of them can be
handled by `fnmatch` alone.

**Axis 1 -- `*` and `/`. Here `fnmatch` OVER-matches.** `fnmatch`'s `*` crosses `/`;
Docker's (derived from Go's `filepath.Match`) does not. On this axis `fnmatch` is
strictly more permissive, so:

  * **No match under `fnmatch` implies no match under Docker.** Conservative in the
    safe direction: a pattern `fnmatch` calls harmless cannot turn out to exclude a
    COPY target under Docker. This is the implication the whole test rests on.

  * **`fnmatch` cannot certify that a pattern DOES exclude something.**
    `fnmatch("data/app.db", "data/")` is `False`, yet Docker excludes that file.
    The test never asks `fnmatch` to prove an exclusion, only to disprove one.

**Axis 2 -- `**`. Here `fnmatch` UNDER-matches, which inverts the implication.**
`fnmatch` has no `**` concept at all: it collapses `**` to a single `*`, which
already crosses `/`, so `**/x` compiles to a regex *requiring a literal slash*:

    fnmatch.translate("**/x")  ->  (?s:.*/x)\\Z
    fnmatch.translate("*/x")   ->  (?s:.*/x)\\Z

Docker lets `**` span **zero** path segments, so Docker's `**/src/` matches a
root-level `src/` while `fnmatch`'s does not. On this axis `fnmatch` is *less*
permissive than Docker, and "no match under `fnmatch`" would NOT imply "no match
under Docker" -- destroying the guarantee above.

`_excludes` closes that axis **by explicit zero-segment expansion**, not by the
matcher: leading `**/` prefixes are stripped one at a time and the target retested
after each. The loop is what makes this **shape-independent** -- it holds for any
number of leading prefixes, so the over-match property is restored for every pattern
shape, not merely the shapes this file happens to use today. That qualifier is
deliberately absent: a claim scoped to the current file is a claim the next edit
invalidates, which is the exact defect this test was written to catch.

So: **do not** make the matcher stricter on Axis 1 (a stricter matcher matches less,
and the implication silently inverts). **Do** keep the Axis-2 expansion; deleting it
reopens a hole in which a `**/`-prefixed pattern naming a COPY target -- `**/src/` --
breaks the build while this test stays green. That is not hypothetical: the
`.dockerignore` preamble actively instructs the next editor to reach for `**/`.

The COPY targets are parsed from the Dockerfile at test time rather than
hardcoded. A hand-written list would make the enumeration and the guard share an
author: a fifth COPY added later would be invisible to the very check meant to
protect it. And the parse is asserted non-empty before it is used -- an enumeration
that silently finds nothing would satisfy "no target is excluded" for the wrong
reason, which is the same vacuous green in a different costume.
"""

from __future__ import annotations

import fnmatch
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DOCKERFILE = _REPO_ROOT / "Dockerfile"
_DOCKERIGNORE = _REPO_ROOT / ".dockerignore"


def _parse_copy_sources(dockerfile: Path) -> list[str]:
    """Return every source path argument of every COPY in the Dockerfile.

    A COPY is `COPY [--flags] <src>... <dest>`, so the final argument is the
    destination and everything before it is a source.
    """
    sources: list[str] = []
    for line in dockerfile.read_text().splitlines():
        stripped = line.strip()
        if not stripped.upper().startswith("COPY "):
            continue
        args = [a for a in stripped.split()[1:] if not a.startswith("--")]
        if len(args) < 2:
            continue
        sources.extend(args[:-1])
    return sources


def _parse_ignore_patterns(dockerignore: Path) -> list[str]:
    """Return the active patterns, dropping comments and blank lines."""
    return [
        line.strip()
        for line in dockerignore.read_text().splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def _plain(pattern: str, target: str) -> bool:
    """`fnmatch`, tolerant of a trailing slash on either side."""
    return fnmatch.fnmatch(target, pattern) or fnmatch.fnmatch(
        target.rstrip("/"), pattern.rstrip("/")
    )


def _excludes(pattern: str, target: str) -> bool:
    """True if `pattern` plausibly excludes `target` (over-approximate; see module docstring).

    Axis 2: `fnmatch` reads `**/x` as requiring a literal slash, but Docker lets `**`
    span zero segments. Test the zero-segment expansion explicitly, or `**/src/`
    would be invisible to this guard.

    The expansion loops rather than stripping one prefix: `**/**/src/` collapses to
    `src/` under Docker too, and a single strip would leave `**/src/` -- still a
    non-match under `fnmatch`. Looping makes the guarantee independent of how many
    prefixes a pattern carries, so it does not have to be re-checked when the file's
    pattern shapes change.
    """
    if _plain(pattern, target):
        return True
    while pattern.startswith("**/"):
        pattern = pattern[3:]
        if _plain(pattern, target):
            return True
    return False


def test_dockerfile_and_dockerignore_exist() -> None:
    assert _DOCKERFILE.is_file(), f"missing {_DOCKERFILE}"
    assert _DOCKERIGNORE.is_file(), f"missing {_DOCKERIGNORE}"


def test_copy_sources_are_discoverable() -> None:
    """The guard below is vacuous if the parse yields nothing. Assert it does not.

    Without this, deleting every COPY -- or breaking the parser -- would turn the
    exclusion test green rather than red.
    """
    sources = _parse_copy_sources(_DOCKERFILE)
    assert sources, "parsed no COPY sources from the Dockerfile; the guard below would be vacuous"
    assert len(sources) == 4, (
        "the Dockerfile is expected to COPY exactly four sources; a parser that "
        f"silently finds fewer makes the exclusion guard vacuously green. Got: {sources}"
    )
    assert "src/" in sources, "expected `COPY src/`; parser or Dockerfile has drifted"


def test_ignore_patterns_are_discoverable() -> None:
    """Likewise: an empty pattern list makes the guard vacuous."""
    patterns = _parse_ignore_patterns(_DOCKERIGNORE)
    assert patterns, "parsed no patterns from .dockerignore; the guard below would be vacuous"


def test_no_ignore_pattern_excludes_a_copy_target() -> None:
    """No `.dockerignore` pattern may exclude a path the Dockerfile COPYs.

    Falsifying input: adding `src/` to `.dockerignore` makes this fail.
    """
    sources = _parse_copy_sources(_DOCKERFILE)
    patterns = _parse_ignore_patterns(_DOCKERIGNORE)

    collisions = [
        (pattern, target)
        for target in sources
        for pattern in patterns
        if _excludes(pattern, target)
    ]

    assert not collisions, (
        "these .dockerignore patterns exclude paths the Dockerfile COPYs, "
        f"which would break the build: {collisions}"
    )


@pytest.mark.parametrize(
    ("pattern", "target", "expected"),
    [
        # The guard fires on an exact directory collision -- the falsifying input.
        ("src/", "src/", True),
        ("src", "src/", True),
        # ...and on a wildcard that happens to reach a COPY target.
        ("*.toml", "pyproject.toml", True),
        # Axis 2. Docker's `**` spans zero segments, so each of these DOES exclude a
        # COPY target and must fire. Bare `fnmatch` returns False for every one of
        # them -- these cases exist to pin the zero-segment expansion in `_excludes`.
        ("**/src/", "src/", True),
        ("**/src", "src/", True),
        ("**/pyproject.toml", "pyproject.toml", True),
        ("**/requirements.txt", "requirements.txt", True),
        ("**/migrations/", "migrations/", True),
        # Repeated prefixes collapse the same way under Docker. A single-strip
        # expansion leaves `**/src/` and misses this; the loop catches it.
        ("**/**/src/", "src/", True),
        ("**/**/**/src", "src/", True),
        # The expansion strips only LEADING `**/`. The next two pin that from both
        # sides; they kill disjoint mutants, and neither subsumes the other.
        #
        # `**/x/src/` requires an `x` directory and does not exclude a root `src/`.
        # Kills a "just take the last component" expansion.
        ("**/x/src/", "src/", False),
        # `src/**/x` requires an `x` under `src/` and does not exclude `src/` itself.
        # Kills a "split on `**/` and test each literal run" expansion, which
        # `**/x/src/` waves through. Note that the guard cannot distinguish that
        # mutant on the patterns this file currently ships -- this pin is the only
        # thing that does, and it is exactly the mutant a future editor writes when
        # generalizing the expansion to mid-path `**`.
        ("src/**/x", "src/", False),
        # It does not fire on the patterns the file actually ships.
        ("data/", "src/", False),
        ("**/__pycache__/", "src/", False),
        ("**/*.pyc", "src/", False),
        ("tests/", "src/", False),
        ("**/.env*", "src/", False),
    ],
)
def test_excludes_helper_behavior(pattern: str, target: str, expected: bool) -> None:
    """Pin the matcher itself, so the guard's negative results mean something."""
    assert _excludes(pattern, target) is expected


def test_bare_fnmatch_would_miss_the_zero_segment_case() -> None:
    """Pin the defect the expansion exists to close, so nobody removes it as dead code.

    `fnmatch` alone says `**/src/` does not exclude `src/`. Docker says it does.
    If this test ever fails, `fnmatch` grew a `**` concept and `_excludes` can be
    simplified -- until then, the expansion is load-bearing.
    """
    assert _plain("**/src/", "src/") is False
    assert _excludes("**/src/", "src/") is True
