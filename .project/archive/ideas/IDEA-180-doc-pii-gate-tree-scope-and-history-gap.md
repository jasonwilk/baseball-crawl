# IDEA-180: The doc-PII byte-gate certifies two trees and no history — so most of the repo, and every past commit, has never been examined

## Status
`CANDIDATE`

## Summary

**Read the mechanism correction first — the premise this was filed under is wrong in a way that changes the finding.** This was routed as "the gate runs on STAGED content only, so it has never examined what is already committed." Reading `.githooks/pre-commit` (the `doc-PII byte-gate` block) and `scripts/check_doc_pii.sh` shows that is not how it works, and the real gap is a different shape:

- The gate's scan target is **`git checkout-index --ignore-skip-worktree-bits -a`** into a temp dir — a snapshot of the **entire index**, not of the staged diff. `check_doc_pii.sh` then `grep -rn`s a whole directory. So **committed-and-still-present content inside a gated tree IS examined**, on every commit that trips the gate. "Staged content only" is false.
- What is actually narrow is **which trees get grepped**: the hook builds `GATE_TREES` from exactly two prefixes, `epics` and `.project`, and only when a staged path falls under one of them. `docs/api` is covered only by a separate **manual/CI** invocation, never by this hook.
- So the byte-gate is **never pointed at** `.claude/**`, `docs/admin/`, `docs/coaching/`, `docs/VISION.md`, `tests/`, `migrations/`, `scripts/`, `src/`, or `CLAUDE.md` — in any tree, staged or committed, at any time.
- And on the temporal axis it reads the **index**, i.e. current state. **No gate has ever examined a past commit.** An identifier that was committed and later scrubbed survives in reachable git objects where nothing looks.

**A note on how this file is written, which is itself a small finding.** This idea deliberately quotes **no** denylisted identifier, because it lives in `.project/` — a gated tree — and an idea that named its own subjects would block its own commit. The gate therefore makes its own coverage awkward to *discuss* anywhere it applies, which is worth knowing before someone tries to document a finding about it. Subjects below are named descriptively.

**The evidence that motivated the filing is explained by tree scope, not by staging.** LSB's own program name (the two-word form, denylisted) sits in **24 tracked files** — `CLAUDE.md`, 4 `.claude/agents/*.md`, 2 `.claude/rules/*.md`, 4 `.claude/agent-memory/**`, 2 `docs/admin/*.md`, `docs/coaching/README.md`, `docs/VISION.md`, `migrations/001_initial_schema.sql`, and **8 `tests/test_*.py`** (1+4+2+4+2+1+1+1+8 = 24) — and **zero** occurrences anywhere under `epics/` or `.project/`. Every one of those 24 is in a tree the gate is structurally never aimed at. Nothing about history or staging is needed to explain the silence.

**One sub-claim I could not settle, and am not asserting.** The filing also cited a real opponent school name (a Nebraska HS, on the E-274 block list) present in 5 committed files as evidence. Two of those five (`.project/ideas/IDEA-059-opponent-flow-spray-gaps.md:25`, `IDEA-082-twin-athlete-uuid-resolution.md:18`) are inside a **gated** tree and have been in the index for months, while `.project/` is staged on nearly every commit — so if that name were a `plain` denylist entry, those two lines would have blocked every recent commit, including the one this session. They did not appear in the 2026-07-25 block output. Either the name is not on the denylist, or the relayed finding list was partial. **Nobody working this can read `secrets/pii-denylist.txt` (agent-blocked), so this needs the operator to resolve** — and it matters, because it decides whether those two `.project/ideas` hits are a live gate failure or a non-finding.

## Why It Matters

The gate's own reporting invites the wrong conclusion. It prints `[doc-pii: REAL, 0 matches]` — a clean bill of health whose scope is "the two trees that happened to be staged." A reader has no way to tell that from "this repo is clean," and `.claude/rules/pii-safety.md`'s byte-gate section describes the harness without naming the two-tree limit (its "Coverage footgun" section is now **stale in the other direction** — it still says the gate is "scoped to `docs/api/` only" and that planning artifacts are UNGATED, which the hook contradicts; IDEA-102 evidently shipped without that prose being reconciled).

The two axes want different fixes and should not be bundled:

- **Tree scope** is cheap to widen and is the half with a real instance behind it (the program name × 24 files, plus IDEA-170's `public_id` in `src/` docstrings). Widening is a noise question, not a design question.
- **History** cannot be fixed by widening anything. A one-off audit over past commits is a different tool with a different output (you cannot un-commit an identifier without a rewrite), and its honest deliverable is an *inventory and a decision*, not a gate.

Worth stating plainly so this is not over-sold: the identifier in those 24 files is **LSB's own program name**, not a minor and not an opponent, and the operator has already ruled it stays. So the 24 files are the *measurement*, not the harm. The harm this sizes is the class — a real athlete name landing in `tests/` or `.claude/agent-memory/` would be invisible to exactly the same degree, and `.claude/rules/pii-safety.md` records that a real minor's name has already reached a planning artifact once (the IDEA-096 capture, caught by Codex, not by a gate).

## Rough Timing

Not urgent; no known live leak. Natural triggers:
- Whoever works **[[IDEA-170]]** should absorb the tree-scope half — that idea already gates on a noise dry-run, which is the same dry-run this needs.
- The history half wants its own deliberate pass, and is only worth doing *after* the denylist question above is settled — auditing history against a denylist whose membership is uncertain produces an unfalsifiable result.

## Dependencies & Blockers
- [ ] **Operator must confirm denylist membership** for the two opponent school names discussed above (both on the E-274 block list; not quoted here for the reason given in the Summary). Agents cannot read `secrets/**`, so the `.project/ideas` question is unresolvable from inside.
- [ ] The tree-scope widening is gated on a noise dry-run (shared with [[IDEA-170]]) — a `plain` grep of a person's surname across `tests/` and `.claude/` may hit ordinary prose.

## Open Questions

- **Is the two-tree scope deliberate or incidental?** The hook comment says the pattern scanner "skips `epics/` and `.project/`… the byte-gate greps them instead," which reads as *this gate exists to cover the pattern scanner's skip list* — a coherent design in which not covering `tests/` is intentional rather than an oversight. If so, the gap is that **nothing** covers identifier-class PII in `tests/`/`.claude/`, and the right fix may be a third mechanism rather than widening this one.
- **Should the gate's success line state its scope?** `[doc-pii: REAL, 0 matches]` reads as a whole-repo pass. `[doc-pii: REAL, 0 matches in epics/, .project/]` costs nothing and stops the over-read. Cheapest piece of this whole idea and independently shippable.
- **What is the history deliverable?** An inventory of which denylisted identifiers appear in reachable objects, with a per-identifier keep/rewrite call — or nothing, if the operator's answer for every one is "it is our own program name, leave it." Establish the decision rule before running the scan, or the output has no owner.
- **Does a `git log -S` sweep even terminate usefully at this repo's size?** Unmeasured. If it is slow, a cheaper proxy is to scan only the blobs of files that ever lived in the gated trees.

## Notes

Filed separately from its two neighbours at the operator's direction (2026-07-25) rather than folded into either. The three are genuinely distinct and each would be a wrong home for this:
- **[[IDEA-137]]** — identifier **CONTENT** inside `docs/api`: a corpus that needs certifying. Says nothing about which trees the gate visits.
- **[[IDEA-170]]** — the gate not covering **`src/`**, framed from one instance (a real `public_id` in two `team_resolver.py` docstrings). A subset of this idea's tree-scope half, and the natural carrier for that half.
- **This one** — the gate's **coverage boundary itself**: a two-tree allowlist plus a manual `docs/api` invocation, and an index-only view with no history axis at all.

**Provenance and a process note worth keeping.** Surfaced when the byte-gate blocked the E-274 planning commit (2026-07-25) on real school names in epic/idea artifacts. The mechanism above was read out of `.githooks/pre-commit` and `scripts/check_doc_pii.sh` rather than taken from the relay that requested this capture — and the relay's central premise ("staged content only") did not survive that read. Recording it because the correction is the more useful artifact than the original idea: **a claim about what a gate examined is a claim about its target argument, and the target here is `checkout-index -a`, not the staged diff.** Per `.claude/rules/tool-output-integrity.md`, an inherited claim becomes the restater's own.

Related: [[IDEA-102]] (extend gate coverage to planning artifacts — apparently shipped; its rule-file prose was not reconciled, which is its own small cleanup), [[IDEA-112]] (narrow the pattern scanner's suppressors), [[IDEA-167]] (the PII-fixture comment that names the wrong shape).

---
Created: 2026-07-25
Last reviewed: 2026-07-25
Review by: 2026-10-23
