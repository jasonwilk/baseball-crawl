---
name: gate-behavior-needs-the-executable
description: E-275 spec audit — I ruled a PII gate did NOT cover epics/ from a SKIP_PATHS literal plus a rule file, never opening .githooks/pre-commit, which gates it. A config constant scopes ONE mechanism; the hook composes several.
metadata:
  type: feedback
---

**Never rule on what a GATE covers from a config constant or a rule file. Open the hook.**

**Why:** E-275 spec audit, 2026-07-27. I reported as MUST FIX that TN-17's *"epics/** is a gated tree, so a real identifier blocks the planning commit"* was **false**, citing (a) `SKIP_PATHS` in `src/safety/pii_patterns.py` containing `"epics/"`, and (b) `.claude/rules/pii-safety.md` saying the byte-gate is *"scoped to docs/api only … planning artifacts rest solely on author discipline."* PM2 refuted it by reading `.githooks/pre-commit`, which runs **two** gates in sequence: the pattern scanner (which `SKIP_PATHS` governs — my source (a) was true and about the wrong mechanism), then a doc-PII byte-gate that builds `GATE_TREES` by literal prefix-match against `epics` and `.project` and blocks on a bad exit. Source (b) was simply stale; the fix it tracked as IDEA-102 had landed without the rule being updated.

Two compounding traps:
1. **A config constant scopes ONE mechanism. A hook composes several.** Finding the constant feels like reaching the executable and is not. Ask "what else runs?" before concluding coverage.
2. **My proposed fix was the more ALARMING sentence** (*"caught by nobody — author discipline is the only control"*), which is why nobody would have challenged it. Committed inside the audit whose stated job was to catch document-over-executable reasoning.

**How to apply:** when a finding turns on whether a gate/hook/CI check covers a path, read `.githooks/*`, `core.hooksPath`, and the CI config **before** filing it — a rule file describing a gate is a claim about the gate, not the gate. If blocked from verifying (e.g. `secret-read-guard` refusing a credential path — correct, do not route around it), say the check is unavailable and name the cheap operator diagnostic instead of inferring. Related: [[stale_defect_characterization]], [[ratio_gate_population_claims]], [[finding_withdrawal_shared_branch_reasoning]].

**The residual worth keeping** (survived the refutation, relocated): the gate matches only identifiers already on the curated denylist and exits `3` = INCONCLUSIVE = **non-blocking** in example mode — then prints `[pii-hook] PII scan passed.`, the exact line CLAUDE.md tells the operator to look for. A **novel** real name is still caught by nobody, and the operator-facing success line does not discriminate a real pass from a certified-nothing pass.
