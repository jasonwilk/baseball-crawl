---
name: dispatch-telemetry-design
description: The steering/self-correction measurement designed for E-279's dispatch to discharge model-behavior-reference checklist item 4 (prune falsification) — operational definitions, the transcript-scoring instrument, pre/post-prune baseline readings, and why the rate metric is a guardrail rather than the verdict.
metadata:
  type: project
---

# Dispatch telemetry — the E-279 prune-falsification measurement

Designed 2026-07-29 by claude-architect (effective model `claude-opus-5`, alias
`opus[1m]`, effort high), commissioned by the main session. E-279 was READY and
undispatched at design time; nothing in the epic's own directory was touched.
(Worded without spelling that pre-archive path: E-279-04's gate makes it
unspellable outside `.project/archive/` once the epic is archived, and this line
is EVIDENCE of what was observed, so it is reworded rather than repointed.)

## What this discharges, and what it CANNOT

`model-behavior-reference.md` checklist item 4 requires every removed passage to
name its defect, its recurrence artifact, and a re-check point, validated by "ONE
table-read per affected model class + the steering/selfcorr telemetry at the next
real epic of each class." E-279 is that epic for the Opus 5 class.

**Read the prune's actual size before designing anything around it.** D5 removed
NOTHING (three sweeps over nine agent definitions found no type-1 scaffolding; the
commit records the empty result as the finding). 3b removed exactly ONE passage —
the enumerated command menu in `tool-output-integrity.md`'s response-protocol step
2. D6 removed agent-memory bulk from the nine `MEMORY.md` files. So the falsifiable
surface is **one shared-rule passage plus a memory-bulk reduction**, not a broad cut.

That size is the design constraint: a one-passage removal cannot move an aggregate
rate detectably against this repo's between-epic variance (measured below, 3-12x).
**So the rate telemetry is a guardrail, not the verdict.** The decisive test is the
targeted recurrence check. Anyone who reports "steering was down, the prune helped"
is reading noise — and the reverse claim is equally unsupported.

Note also what is NOT under test: the prune's BENEFIT (context cost) is already
known from the byte/line deltas in the commits. This measurement tests only for
HARM. There is no "the prune helped" reading available from these numbers, and
inventing one would be a fabricated finding.

## (a) Operational definitions

Scored from transcripts, per agent. Buckets:

| Bucket | Definition | Counts as |
|---|---|---|
| **OP-STEER** | The OPERATOR corrects the main session's course mid-dispatch. | steering (heaviest) |
| **STEER** | Main session / team-lead tells an agent its work or course is wrong and must change. | steering |
| **UPHELD** | The agent objected and the lead conceded ("your refusal was right", "my instruction was wrong"). | NEGATIVE signal — the agent caught something |
| **SELFCORR** | Within its own turns, an agent catches and reverses its own error before external input. | self-correction |
| **GATE** | Code-reviewer findings, PM AC verdicts, review rounds. | EXCLUDED from steering |
| **SPAWN** | The first inbound message to a subagent (its brief). | excluded |
| **LIFECYCLE** | shutdown/idle/terminated JSON, compaction continuations. | excluded |

**The exclusions are where this measurement earns its keep.** A code-reviewer
finding is the process working as designed — counting it as steering would score a
functioning gate as a defect and reward dispatches that review less. Likewise a
message ANSWERING a question the agent asked is not steering: the agent initiated
it, which is closer to a self-catch. And UPHELD runs the opposite direction from
STEER — an agent that pushes back successfully is performing well, so pooling them
into "messages about problems" destroys the sign.

## (b) Instrument

`.claude/hooks/dispatch-telemetry.py` — stdlib Python, manual operator diagnostic,
NOT a registered hook. Same shape and banner convention as
`.claude/hooks/context-ratchet.sh` (a diagnostic that lives in `hooks/` without
being one); `.claude/hooks/` is outside the ratchet's four counted subtrees and the
file is `.py`, so it has zero ratchet impact. It lives under `.claude/` because the
write-guard blocks `scripts/` when no dispatch worktree exists, and because
claude-architect owns that surface.

    python3 .claude/hooks/dispatch-telemetry.py <session-id>   # worksheet + counts
    python3 .claude/hooks/dispatch-telemetry.py --list         # recent sessions

Reads `~/.claude/projects/-workspaces-baseball-crawl/<session-id>.jsonl` plus that
session's `<session-id>/subagents/agent-*.jsonl` and their `.meta.json` siblings —
the meta files carry `customAgentType` and the model ALIAS, and `message.model` in
the transcript carries the EFFECTIVE model, so each run also re-verifies the
alias-to-model register for free.

**It emits candidates and counts, never verdicts.** The prefilter is deliberately
wide; `tool-output-integrity.md` Prohibition 3 binds it like anything else, so
every row needs a read before it counts. Cost is minutes: one command per session,
then adjudication of only the STEER/UPHELD/SELFCORR rows.

⚠ **The script is an uncommitted new file until someone commits it.** If it is
still uncommitted when E-279 dispatches it will ride E-279's closure `git add -A`
as an unrelated change. Commit it separately first, or delete it and re-create it
after closure.

## (c) Baselines — measured 2026-07-29, not notional

All Opus 5. Rates are per 100 agent turns. The layer pass landed 2026-07-26
(D5 `983ca8b` 20:57Z, D6 `4584192` 21:08Z, 3b `1fb180e` 22:00Z).

| Session | Work | Date | Prune | Turns | STEER | SELFCORR | UPHELD |
|---|---|---|---|---|---|---|---|
| `32e9948e` | E-273 dispatch | 07-24 | PRE | 483 | 4.3 | 1.2 | 1.2 |
| `58290b38` | E-272 dispatch | 07-25 | PRE | 820 | 7.6 | 7.2 | 1.7 |
| `af996904` | E-277 plan+dispatch | 07-26/27 | POST | 1664 | 7.8 | 14.8 | 9.9 |
| `15538a3f` | E-278 dispatch | 07-28 | POST | 690 | 2.9 | 8.0 | 4.3 |
| `1aa90651` | E-275 planning | 07-26/27 | POST | 469 | 9.6 | 19.0 | 2.6 |

(E-275 is a PLANNING session, listed for context and excluded from the dispatch band.)

**The finding that shapes the whole design: STEER pre-prune spans 4.3-7.6 and
post-prune spans 2.9-7.8 — overlapping, with the lowest reading of all five sitting
POST-prune and the highest also post-prune.** SELFCORR spans 1.2-7.2 pre and
8.0-14.8 post, a rise that is NOT attributable to the prune: the same boundary
added the D5 model adapters, the epics differ in size and review depth, and the
vendor confound already recorded in `model-behavior-reference.md` — Opus 5 narrates
corrections more, so correction-count is not error-count — sits directly on this
metric. Two dispatches per side cannot separate those.

**"The prune did no harm"** = (i) zero recurrence of the specific defects named
below, AND (ii) E-279's STEER rate inside the 2.9-7.8 dispatch band. **A reading
outside the band is a prompt to LOOK, never a verdict** — E-279 is a context-layer
epic and the band is drawn from code epics, so a class difference is a live
alternative explanation.

### The decisive check: targeted recurrence, per removed passage

1. **3b — the command menu in `tool-output-integrity.md` step 2.** Defect it was
   written against: E-231 harness output corruption (verbatim from E-231-01 AC-3).
   Recurrence artifact: `.project/research/E-231-harness-repro/harness-output-reliability-report.md`
   (untouched). Re-check: did any E-279 agent hit a tool-output failure and fail to
   cross-check it through an independent channel, or assert a result from a dirty
   read? Boolean, and findable — grep the transcripts for the empty/garbled
   response protocol firing. The gate/retry/escalate/read-findings steps were NOT
   removed, so a failure to gate at all would indict something other than the prune.
2. **D6 — `claude-architect/MEMORY.md`, the 8,554-byte codification bullet.**
   Re-check: does CA, which owns 4 of E-279's 5 stories, need a fact it lost? Every
   project fact was verified present in `data-model.md`, `canonical-seams.md`,
   `architecture-subsystems.md` and CLAUDE.md before removal, so the failure mode is
   CA reaching for something and not finding it — visible as a wrong claim about
   prior codifications, or a question to the operator that the bullet would have
   answered.
3. **D6 — code-reviewer's memory copy of the five Mandatory Review Checks** (kept in
   `code-reviewer.md`, replaced in memory by a tombstone). Re-check: does `cr-e279`
   run all five? Directly observable in its review output.
4. **D6 — software-engineer's respx/`create_session` lines** (duplicated verbatim in
   its own definition). **E-279 gives this WEAK coverage and that should be stated
   rather than glossed:** SE's only story (E-279-05) is a memory reconciliation that
   writes no code and touches no HTTP mocking. Treat this removal as still open
   after E-279; its real re-check is the next SE story that writes tests.

## (d) Model classes E-279 exercises

Read from the epic's Dispatch Team section and the per-story Agent Hints:
claude-architect (stories 01-04) and software-engineer (story 05), plus PM and
code-reviewer as dispatch infrastructure. **All four pin `opus[1m]` → `claude-opus-5`.**

**So E-279 discharges checklist item 4 for the Opus 5 class ONLY.** Sonnet 5
(baseball-coach, ux-designer, docs-writer) and Fable 5 remain unfalsified and need
their own next-epic-of-that-class reading. One conditional exception: if E-279's
documentation assessment gate fires and pulls docs-writer in at closure, that yields
an incidental Sonnet 5 reading — take it if it happens, do not assume it will.

## (e) Where the results get recorded

Append a dated `## Reading — E-279 (YYYY-MM-DD)` section to THIS file carrying:
the session id, the raw bucket counts, the per-100-turn rates, the four targeted
recurrence verdicts, and the effective model per agent as read from `message.model`
(not the alias). One line in `epic-codifications.md` under E-279 pointing here.
Per checklist item 8, new behavioral-lesson entries carry date + provenance +
effective model.

**Do not write a rate from a live dispatch into any memory file before the dispatch
closes** — `context-layer-assessment.md`'s "never write a number from a live thread
into a memory file" applies exactly here.

Related: [[model-behavior-reference]], [[epic-codifications]], [[agent-design]].
