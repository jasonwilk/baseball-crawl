# Upstream Bug Report — Claude Code Harness Output Drop & Corruption Under Multi-Agent Dispatch

**Intended audience:** Anthropic / Claude Code engineering.
**Purpose:** Report and provide reproduction evidence for an intermittent **tool-output transport** failure in the Claude Code harness — observed as bursty empty returns, garbled-but-nonempty output, and tail truncation under concurrent multi-agent (Agent Teams) dispatch. This is **not** an internal application bug; the root cause appears to be in the harness/transport layer between tool execution and the model's context, which we cannot fix from this repository. We are filing it upstream and have built local detect-and-defend mitigations (see "Local mitigations" below) to survive it in the meantime.

**Status:** Non-fixable from this repository. The disposition is this report plus the sibling mitigations.

---

## Summary

During normal operation — most severely under concurrent multi-agent dispatch (Claude Code Agent Teams) — the channel that carries **tool results back into the model's context** intermittently returns content that does not match what is actually on disk or what the command actually produced. The failure is **bursty** (clusters of bad results, then clean), **recovers on retry**, and affects even zero-I/O commands. Because some of the corruption is *nonempty-but-wrong*, it cannot be fully caught by tooling — an agent can read carefully and still act on garbage.

The planning and dispatch session for our epic **E-231** reproduced this bug severely and repeatedly, providing the primary first-hand evidence below.

---

## Failure taxonomy

Three distinct, co-occurring failure modes were observed:

1. **Empty returns.** A tool call (`Read`, `Glob`, `Bash`) returns empty/no-content for a target that is known to be non-empty. The same call returns correct content on retry seconds later.

2. **Garbled-but-nonempty output.** The result is nonempty but does **not** match reality. The sharpest observed instance: a `Read` of a single unchanged file reported its line count as **19, then 17, then 18 on successive reads**, while a `cat -n` of the *same* file in the *same* session showed a clean, stable **1–31** line range. The bytes were wrong, not absent — no empty-detection or size check would have flagged it.

3. **Tail truncation.** Output is cut off at the end — the head is correct, the tail silently missing. For large results (e.g., a persisted review log) this presents as a short *preview* that looks complete.

**Additional characteristics:**
- **Hits even zero-I/O commands.** The corruption struck a bare `echo` (no file or network I/O), which rules out filesystem/race explanations for those instances and points at the result-transport layer itself.
- **Recovers on retry.** Re-issuing the identical call typically returns correct output, confirming the underlying data is intact and the fault is in delivery, not storage.
- **Correlated with concurrency.** Frequency and severity rose sharply under concurrent multi-agent dispatch (multiple teammates active simultaneously) and fell when activity was serialized.

---

## Reproduction context (this-session evidence)

All of the following were observed first-hand during the E-231 planning/dispatch session, under **concurrent multi-agent dispatch** (Agent Teams with a main session plus PM, CA, SE, and CR teammates active). The one explicitly-marked exception cross-references the immediately prior E-230 dispatch:

- **Stale-line-number Read.** A `Read` of an unchanged file reported line counts **19 → 17 → 18** across successive calls while `cat -n` showed a clean, stable **1–31** on the same file (the garbled-but-nonempty mode). Affected: **CA** and the **PM** channel.

- **Empty returns on known-nonempty files, recovering on retry.** Reads of files that demonstrably existed and were non-empty returned empty, then returned correct content when retried moments later. Affected: **PM**, **CA**.

- **False-negative Glob.** A `Glob` reported **"no files found"** for a path that a clean `Read`/`ls` of the same path immediately confirmed existed — i.e., a flaky empty result masquerading as authoritative proof of absence. (A "no files found" under a flaky channel is **not** proof of absence.)

- **Silent partial-edit appearance.** An `Edit` round-tripped while the agent's own read-back came back dark, so success could not be confirmed from inside the same flaky channel that performed the edit. Affected: **CA**.

- **Garbled-output misread (SE — explicitly the immediately prior E-230 dispatch).** SE acted on garbled-but-nonempty output and reported a spurious "test-isolation leak" that did not exist — the same corruption class as the stale-line-number Read above. SE was again active this session as the E-231-02 predicate-consultation agent under the same concurrent-dispatch channel. Affected: **SE**.

- **Two truncated-read-composed-into-fabricated-findings relays during triage.** Twice during this session's review triage, a **truncated review log** (a short preview of a much larger persisted result) was relayed onward as a **confident, complete finding list** — review findings were composed from output that had not been fully read, and presented as if they came verbatim from the reviewer. In one concrete instance a triage decision was taken against a **~2KB preview of a ~373KB persisted result**, mischaracterizing four valid findings as "2 LOW already-adjudicated." This is exactly the fabrication anti-pattern the E-231 epic exists to stop. Affected: main session relay surface, with **PM**/**CA** downstream.

Across these, the affected agents were **PM, CA, and SE** (plus the main-session relay surface). The unifying signature: **the data on disk / the command's true output was correct; the delivery of that data into the model's context was not.**

---

## Why this is hard to self-detect

- **Empty / truncated / silent-partial-edit** can be partially caught by tooling (a re-read + cross-check, a post-write verification hook).
- **Garbled-but-nonempty** cannot be reliably caught by any tool — the output is present and well-formed, just *wrong*. Only an agent cross-checking against an independent channel (`wc -l`/`cat -n`/`sed -n`, or a second tool) can notice it, and only if it is disciplined enough to distrust a result that looks fine. This is why an upstream fix matters: local discipline reduces but cannot eliminate the blast radius.

---

## Reproduction notes for upstream

- **Environment:** Claude Code with `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`, multi-agent dispatch (main session + several teammates) in a devcontainer.
- **Trigger conditions:** Highest incidence under concurrent teammate activity; lowest when activity is serialized. Affects `Read`, `Glob`, and `Bash` (including bare `echo`).
- **Signature to look for:** identical successive calls returning different/empty/short results on a target that is provably stable; recovery on retry; corruption on zero-I/O commands.
- **Suggested instrumentation:** capture the raw tool-result payload at the transport boundary vs. what the model receives, under concurrent dispatch, and diff them — the divergence should be visible at the delivery layer independent of tool execution.

---

## Disposition: non-fixable from this repository

The root cause is in the Claude Code harness/transport layer and is **Anthropic-internal**; we cannot repair the channel from application code. Our local response is a **detect-and-defend** layer plus this upstream report. We are **not** attempting to fix the transport, cap concurrency via a (non-existent) harness knob, or run a diagnosis spike — the posture is settled and the mitigations below are the durable local response.

### Local mitigations (planned sibling work in epic E-231)

These are **planned** sibling stories in the same epic; they are independent and may land in any order, so none should be assumed already shipped at the time this report is read:

- **E-231-01** — an always-loaded output-integrity discipline rule naming the empty/truncated/garbled taxonomy and prescribing independent-channel cross-check, retry, and escalation (and prohibiting asserting unseen content or co-batching a report with the command it reports).
- **E-231-02** — a PostToolUse Edit/Write verification hook that re-reads the target and signals when an edit did not land (catching the silent partial-edit-success class), while distinguishing transient flakiness from a genuinely-absent edit.
- **E-231-03** — a force-read-findings-before-triage read-receipt gate in the review skills, converting "read the full persisted result before triaging" from a remembered lesson into a structural precondition.
- **E-231-05** — a relay-integrity rule closing the orchestrator-relay surface (no relay of unread content), targeting the truncated-read-composed-into-fabricated-findings failure observed twice this session.

Together these reduce the blast radius locally; only an upstream transport fix removes the garbled-but-nonempty class entirely.
