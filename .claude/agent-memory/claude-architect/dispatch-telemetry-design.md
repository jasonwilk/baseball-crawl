---
name: dispatch-telemetry-design
description: The steering/self-correction measurement for checklist item 4 (prune falsification) — definitions, the transcript-scoring instrument, baselines (RAW/pre-adjudication, proven by re-run), the TAKEN E-279 reading with its 89%-false-positive adjudication, why the instrument was never measuring steering, and the SendMessage-payload method for measuring report length.
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

⚠ **CORRECTION 2026-08-02: every rate in this table is RAW — a pre-adjudication
CANDIDATE count, not an adjudicated one.** The file did not say so, and the omission
is a trap, because §(b) tells you to adjudicate every row before it counts. Proof by
re-running the instrument: `32e9948e` returns 21 candidates / 483 turns = 4.35 against
the 4.3 recorded here; `15538a3f` returns 20 / 690 = 2.90 against the recorded 2.9.
Both reproduce exactly, so no adjudication was ever applied to the baselines.
**Consequence: an adjudicated reading is NOT comparable to this table.** Compare raw to
raw, or adjudicate all four baselines first (4x the work, for a band §(c) already says
cannot discriminate). This is why the E-279 reading below records the raw rate as the
comparable figure and treats its adjudication as a taxonomy rather than a rate.

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

## Reading — E-279 (taken 2026-08-01, dispatch closed; recorded 2026-08-02)

Session `fd615ae6-f076-4675-8b8c-a2bf6321b47e`, 1,331 agent turns. Effective models
re-verified from `message.model`: all five `opus[1m]` agents → `claude-opus-5`,
`sonnet` → `claude-sonnet-5`. **Register unchanged; no drift.**

Raw buckets: STEER? 79 · UPHELD 83 · SELFCORR? 180 · GATE 82 (excluded) · OP-STEER 0.
**Comparable (raw) STEER rate = 5.94/100**, inside both the pre-prune (4.3–7.6) and
post-prune (2.9–7.8) bands. The guardrail reads NO SIGNAL, exactly as designed.

**Adjudicated, and the value is a TAXONOMY not a rate** (79 rows, disjoint,
priority-ordered): wrong direction (agent→main, and STEER is defined main→agent) 8 ·
assignment/spawn 7 · gate relay 7 · **freeze/release/hold/confirm choreography 32** ·
UPHELD-shaped praise, orchestrator self-corrections, questions, refinements 16 ·
**genuine steering 9** (8 firm, 1 weak). **89% false-positive rate.**

**The instrument was never measuring steering, and this bounds every future reading.**
The largest real class — 41% — is freeze/release choreography: coordination overhead,
neither steering nor error. E-280 removes exactly that class, **so a post-E-280 STEER
delta will move for reasons unrelated to steering.** Do not read one as evidence about
steering. (Adjudicated on ONE session; the three big FP classes are structural — cue
matching plus the dispatch protocol — so a similar rate in the baselines is expected
but is INFERENCE, not measurement.)

Recurrence verdicts: **1 (3b command menu)** — no counter-evidence; response-protocol
vocabulary present across all agents. A presence signal, not proof of correct handling.
**2 (CA's 8,554-byte bullet)** — PASS; CA worked from `epic-codifications.md`
throughout, the designed post-collapse behavior, with no instance of reaching for a
lost fact. **3 (CR's five Mandatory Review Checks)** — SPLIT, do NOT score as pass: the
tombstone's pointer verifies (SQL query scope, return-value consumption, status
lifecycle all present in fuller form in `code-reviewer.md`), but the behavioral half is
UNCOVERED because E-279's stories were shell/markdown/memory. **4 (SE respx)** — OPEN,
as predicted. Incidental Sonnet 5: `dw-e279` participated at 7 turns — far too small to
discharge the Sonnet class; record as participated, not as a reading.

## Report length: measure `SendMessage` payloads, not tok/turn

Method note, because E-280 needed this and no prior measurement existed. **A report IS
a `SendMessage` payload**; extract `input.message` from `tool_use` blocks named
`SendMessage` across the session jsonl plus `<sid>/subagents/agent-*.jsonl`, attribute
by the sibling `.meta.json` `customAgentType`, and measure characters per role.

**Tokens-per-turn is NOT report length and does not transfer.** The 2x per-turn figure
in the wallclock analyses averages over ALL turns; measured at the report grain, E-279
(532 payloads, all-role p50 3,080) sits INSIDE the peak-4.8-week range (three sessions,
p50 1,620 / 4,941 / 1,917) and below that era's heaviest on every statistic — where 4.8
SE ran p50 7,760 and CR p50 8,191, roughly double E-279's. **There was no report-length
inflation to cap.** Full tables are quoted in E-280's TN-19; this note records the
METHOD and the population trap, which outlive the epic.

Companion hazard: **a report-length cap on code-reviewer is a review-bar-literalism
trap** — vendor-documented for Opus 5, which CR pins ("ask it to report everything and
filter in a separate pass"). CR is the longest role in BOTH eras because length tracks
finding count, making it the most tempting target and the worst one.

Related: [[model-behavior-reference]], [[epic-codifications]], [[agent-design]].
