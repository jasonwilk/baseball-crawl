---
paths:
  - "**"
---

# Tool-Output Integrity

The harness transport layer can drop or corrupt tool output in bursts -- even on zero-IO commands like a bare `echo` -- and recover on retry. This corruption is not always empty: a nonempty result can be wrong. No tool can detect a garbled-but-nonempty read; only an agent applying this discipline can. This rule binds every agent and the main session on every session.

## Failure taxonomy

Treat any of these as a tool-output FAILURE, not as truth:

- **Empty** -- a read/command returns nothing for a target you know or expect to be non-empty.
- **Truncated** -- output is cut off (tail missing, a partial edit that did not fully land).
- **Garbled** -- output is nonempty but wrong. Examples: line numbers that disagree with an independent count (e.g., a Read reporting 17-19 lines while `cat -n` shows a clean 1-31 on the same file), stale or mismatched content, a different file's bytes, or a command echoed back instead of executed.

## Response protocol (cross-check, retry, escalate)

When a target known or expected to be non-empty returns empty, truncated, or garbled output:

1. **Treat it as a FAILURE** -- do not act on it or report it as the result.
2. **Cross-check via an independent channel** -- e.g., `wc -l` / `wc -c` / `sed -n` / `cat -n`, or a second tool (Read vs. Glob).
3. **Retry** to obtain a clean result.
4. **Escalate rather than assert** if a clean result still cannot be obtained.

When two channels disagree, **the clean read wins** over a flaky empty or garbled result. A "no files found" Glob is NOT proof of absence under a flaky channel -- confirm absence through a second channel before relying on it.

## Prohibitions

- **Never assert or relay file content or a tool outcome you have not seen cleanly in your own context.** Report what you observed, not what you expect.
- **Never co-batch a relay or report with the same-batch command whose output it reports.** A report must describe output already in context from a prior, completed call -- never expected output and never output produced in the same tool batch as the report.

## Related discipline

This generalizes the clean-reread-before-defect discipline in `.claude/agent-memory/product-manager/feedback_clean_reread_before_defect.md` (re-read cleanly and quote literal text before reporting a defect; never rule on a grep match) -- a committed memory reminds the PM; this rule binds every agent. It is also the behavioral half of the detect-and-defend layer whose tooling half is the E-231-02 PostToolUse hook (catches empty/truncated/silent-partial-edit) and whose triage-time application is the E-231-03 triage gate. The same caution applies before triaging review findings: read the actual output to completion before characterizing it.
