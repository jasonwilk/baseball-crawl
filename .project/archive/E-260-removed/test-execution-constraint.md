# Removed/corrected text snapshot — Test Execution Constraint (false claim)

- **Story:** E-260-02 (Correct the false Test Execution Constraint, all sites)
- **Date:** 2026-07-11
- **Nature:** CORRECTION, not deletion. Each site's false rationale ("worktree pytest tests main's code") is replaced with the true behavior; the "no per-story worktree pytest" conclusion is retained. Source of truth: `.claude/agent-memory/code-reviewer/worktree_pytest_loads_the_worktree_src.md`.

Sites (verbatim pre-edit text):

---

## Site 1 — `.claude/agents/code-reviewer.md` :304 (Test Execution Constraint block)

Do NOT run `pytest` from the epic worktree for **per-story review**. The project uses an editable install whose meta path finder hardcodes the main checkout's `src/` path -- pytest from the worktree tests main's code, not the worktree's changes. Instead:

---

## Site 2 — `.claude/agents/code-reviewer.md` :62 (Per-story default vs. closure gate cross-ref)

**Per-story default vs. closure gate**: Targeted test discovery (above) is the **per-story default** -- run only the tests that import from the changed modules, and only when assigned a per-story review (note the Worktree Review Test Execution Constraint: no worktree pytest for per-story review). The **full** `python -m pytest tests/` runs at exactly one point: the **Phase 5 Step 1b full-suite-green closure gate** (`.claude/skills/implement/SKILL.md`), executed against the **main checkout**, when the main session assigns that closure pass. Do not run the full suite during per-story review and do not self-initiate the closure pass.

(Note: this cross-ref carries no false phrasing — it references the constraint by name and states the retained conclusion. Captured for completeness; no rationale change required.)

---

## Site 3 — `.claude/skills/implement/SKILL.md` :228 (Pytest limitation note)

**Pytest limitation**: pytest tests the **main checkout's** code (not worktree changes) due to the editable install's meta path finder. Run tests for verification but understand this. Report results in your completion message.

---

## Site 4 — `.claude/skills/implement/SKILL.md` :259 (code-reviewer assignment template caveat)

Review via `cd [epic-worktree-path] && git diff` (unstaged = this story). Do NOT run pytest for this per-story worktree review -- verify through file inspection (worktree pytest tests main's code via the editable install, so it is misleading per-story). The one place you run `python -m pytest tests/` is the Phase 5 Step 1b closure gate, against the main checkout.

---

## Site 5 — `.claude/skills/implement/SKILL.md` :458 ("Why it runs in Step 8" rationale)

**Why it runs in Step 8, not here.** The per-story "no pytest in the worktree" rule (the Phase 3 Step 5 item 2 code-reviewer template and `.claude/agents/code-reviewer.md` Test Execution Constraint) exists because the editable install's meta path finder makes worktree pytest test **main's** `src/`, not the worktree's changes -- so a worktree run is misleading. The only point at which pytest is authoritative for *this epic* is after Step 8's `git apply --3way` patches the epic's accumulated changes onto main. Running the gate here (before Step 8) would test main's *pre-epic* code -- meaningless. The reconciliation is therefore real, not a loophole: the per-story ban stands, and the one authoritative full-suite run happens at closure, in main, after the merge.

---

## Site 6 — `.claude/rules/workflow-discipline.md` :104 (Full-Suite-Green Closure Gate rationale — trailing clause)

...The full-suite run at closure is the named exception to the per-story "no worktree pytest" rule (`.claude/agents/code-reviewer.md` Test Execution Constraint) -- per-story worktree pytest tests main's code and is misleading, but at closure the epic's changes are in the main checkout where pytest is authoritative.
