# IDEA-211: `pii-safety.md` says the planning trees are ungated; the pre-commit hook gates them

## Status
`CANDIDATE` — **a stale safety rule that has already produced one false finding.**

## Summary

`.claude/rules/pii-safety.md` §"Coverage footgun — planning/idea/epic artifacts are UNGATED (IDEA-102)" states two things that are no longer true:

- that `epics/**` and `.project/**` are ungated, and
- that the doc-PII byte-gate is *"scoped to `docs/api/` only"*.

`.githooks/pre-commit` gates both trees. After the pattern-scanner pass it builds a `GATE_TREES` array by literal prefix-match against `epics` and `.project`, snapshots the index with `git checkout-index`, runs `scripts/check_doc_pii.sh` per staged tree, and blocks on a non-zero exit — with an explicit counter check that refuses to pass if a gate was staged but never executed. The hook's own comment states the division: *"The pattern scanner skips epics/ and .project/ … The byte-gate greps them for literal known identifiers instead."*

The rule's other half remains **correct and load-bearing**: the pattern scanner does carry `epics/` and `.project/` in `SKIP_PATHS` and cannot regex-detect names. The stale part is the conclusion drawn from it.

The section also names **IDEA-102** as tracking "the systematic fix (extending gate coverage to planning artifacts)". That extension appears to have landed. **IDEA-102's status needs re-checking** — it may be closeable, and if so this section should have moved with it.

## Why It Matters

**It has already caused a defect, on its first contact with a reviewer.** During the E-275 spec audit, code-reviewer read this section, concluded the planning trees are ungated, and filed a MUST FIX proposing that the epic adopt the sentence *"A real identifier here is caught by nobody — author discipline is the only control."* That sentence would have been written into a binding safety constraint in an epic. It was caught only because PM read the hook instead of the rule.

Note the shape: the false claim was the **more alarming** one, in a **safety** note, which is the combination least likely to be challenged. A reviewer doing exactly the right thing — citing a rule file rather than guessing — was led to a wrong conclusion by the rule file.

**The honest statement has two halves and the rule should carry both.** A real identifier *already on* `secrets/pii-denylist.txt` does block the planning commit. A **novel** real name, not on the denylist, is caught by nobody — and the gate passes non-blocking in example mode (exit `3`) where the real denylist is absent. Either half alone misleads, in opposite directions.

## ⚠ FIX THESE SPECIFIC SENTENCES. **DO NOT REWRITE THIS SECTION.**

**The next reader's instinct will be to rewrite it. Resist that** — a sweep destroys two things worth keeping, and both are things a well-meaning cleanup removes first.

Code-reviewer applied the criterion/evidence cut to the rule section clause by clause (spec-audit F12). **Correct only the coverage conclusion. Preserve these:**

| clause | disposition | why |
|---|---|---|
| `epics/` + `.project/` are in the pattern scanner's `SKIP_PATHS`, and it cannot regex-detect NAMES | **PRESERVE — still true** | This is the mechanism that genuinely remains uncovered. Correcting it replaces a true statement with nothing. |
| the doc-PII byte-gate is "scoped to `docs/api/` only" | **CORRECT** | False against `GATE_TREES`. This is the whole defect. |
| "planning artifacts are UNGATED … rest solely on author discipline" | **CORRECT, to the two-sided form** | True only for identifiers not on the denylist, and in example mode. |
| the **IDEA-096 incident** (a real minor's name reached an idea file, caught by Codex, remediated in E-254 Phase-4b) | **PRESERVE — EVIDENCE** | Records what happened. Editing it destroys the record. |
| "the systematic fix … is tracked in IDEA-102" | **RE-CHECK** | That fix appears to have landed. IDEA-102 may be closeable. |

## SECOND DEFECT IN THE SAME FAMILY: the success line does not discriminate (spec-audit F13)

**On exit `3` the hook prints `[doc-pii: INCONCLUSIVE — example mode]`, does NOT set `BLOCKED`, and falls through to print `[pii-hook] PII scan passed.` and exit 0 — the identical terminating line it prints when the gate ran REAL with 0 matches.** `CLAUDE.md` → Git Conventions tells the operator to verify exactly that line.

So **the line the operator is told to check is printed whether the gate certified the tree or certified nothing.** The discriminating line is printed immediately above it, and nothing tells anyone to read it.

This is a named failure mode in `.claude/rules/tool-output-integrity.md`: *"require an instrument to emit evidence that it OPERATED, separate from its result — then do not filter that evidence away."* Here the evidence **is** emitted. The guidance filters it away. That is a sharper form than the rule's own example and is worth carrying back into it.

> **⚠ The CLAUDE.md passage is DELIBERATELY ARGUED — this is not a one-word swap.** It explicitly reasons about `[pii-scan]` versus `[pii-hook]` and explains why the terminating line was chosen: the `[pii-scan]` line is legitimately absent from good commits, which makes it a poor thing to require. **That argument is still sound on its own terms.** Whoever fixes this is revisiting considered reasoning, not correcting an oversight — a claude-architect judgement.

**The fail-open itself is deliberate and the hook explains why** (blocking on a fresh clone would make it uncommittable, and the hook would be uninstalled, taking the exit-1 detection with it). **Do not "fix" the fail-open.** The defect is the reporting, not the policy.

### This has already bitten, once, on the day it was found

Team-lead ran the gate **from inside the E-275 worktree**: exit `3`, EXAMPLE mode, INCONCLUSIVE. Re-ran the **same command against the same trees from the main checkout**: REAL mode, 36 patterns, PASS. **Same command, same trees, opposite epistemic status — and only the discriminating line distinguishes them.** Reading a terminating "passed" line would have recorded a certification that certified nothing.

**Root cause of the mode split — stated at the right level of generality, because the narrower form misleads in BOTH directions.** The script **resolves its denylist relative to the CURRENT WORKING DIRECTORY**. So: **any run whose CWD lacks `secrets/` is in EXAMPLE mode, regardless of the script path used to invoke it and regardless of which paths it is pointed at.**

> **The worked instance, which is the operationally common one and the one that actually bit us:** worktrees have no `secrets/` directory, so a pre-commit run made from inside a worktree lands in EXAMPLE mode. **Keep this — but do not mistake it for the rule.**
>
> **Established by execution, not reasoning.** Team-lead attempted to dodge the trap by invoking the gate with an **absolute script path** from inside the worktree; it still returned exit `3`. So the trigger is neither the script's location nor "being in a worktree." Only changing CWD fixes it. **The person hunting the trap hit it four times tonight while actively looking for it — twice during this epic's own final verification — and the absolute-path attempt was a fifth.**
>
> **Both errors the narrow form invites are live.** A reader who takes "don't run it from a worktree" concludes that a run from **anywhere else** is safe — but any CWD without `secrets/` (a scratchpad, a subdirectory, another repo) yields a confident example-mode pass. **And the reverse is worse:** they conclude a worktree-path check is inherently uncertifiable, when it certifies fine **from the right CWD** — which is precisely the technique every certification of record in E-275 depends on (main-checkout CWD, worktree target paths, REAL mode).

**None of this is stated anywhere today**, and it is the practically important consequence.

### The operator diagnostic

**On any commit touching `epics/` or `.project/`, read which `[doc-pii: …]` line appears** — `REAL, 0 matches` means the gate ran; `INCONCLUSIVE — example mode` means it certified nothing. Costs nothing and needs no secret access.

Code-reviewer hit `secret-read-guard` checking whether the denylist file exists and **left it blocked rather than routing around it** — correct, and [[IDEA-203]] argues the same independently: **the right diagnostic is the exit code, never the token.**

## Rough Timing

Cheap and contained: one section of one rule file, plus an IDEA-102 status check. Worth doing before the next agent reasons about PII coverage from the rules rather than the hook. **Not urgent in the exposure sense** — the gate is *stronger* than the rule claims, so nothing is unprotected that the rule says is protected. The risk is bad downstream reasoning, not a live leak.

## Dependencies & Blockers
- None. `.claude/rules/**` is claude-architect's to edit per the ownership table in `.claude/rules/context-layer-assessment.md`.

## Open Questions
- **Is IDEA-102 closeable?** Its stated fix appears to have landed. If it is, does anything remain in its scope beyond the trees now covered?
- **Does `CLAUDE.md` carry the same stale framing?** Its Security Rules section describes the byte-gate via `scripts/check_doc_pii.sh docs/api`, which reads as the whole story. Check before editing only the rule.
- **Should the rule state the denylist-scope caveat explicitly?** The gate catching only pre-listed identifiers is the part a reader is most likely to over-trust once they learn the tree *is* gated — the correction risks creating the opposite error.

## Notes

Found 2026-07-27 during E-275 spec-audit triage, by reading `.githooks/pre-commit` after the audit and PM's own memory disagreed about the same fact. Recorded in E-275 as **TN-10 closure obligation B** with a Success Criterion, so the epic carries a checkable surface for it rather than a routing hope.

Corroborated independently: [[IDEA-204]] already states the pre-commit gate covers the planning trees per `GATE_TREES`. So two artifacts written days apart both know what the rule file does not — which is the argument for fixing the rule rather than trusting that readers will find the ideas.

(One detail worth checking during the fix, not a finding: IDEA-204 describes `GATE_TREES` as covering `docs/`, `epics/` and `.project/`. The hook's loop iterates `epics` and `.project` only; `docs/api` coverage comes from a separate manual invocation. Small, and in the safe direction, but the fix should state the real set.)

Domain: claude-architect.

Related: [[IDEA-203]] (what the gate blocks that it maybe should not), [[IDEA-204]] (what the gate never sees), [[IDEA-102]] (the tracking idea whose fix appears to have landed), [[IDEA-180]] (gate tree scope and history gap).

---
Created: 2026-07-27
Last reviewed: 2026-07-27
Review by: 2026-10-25
