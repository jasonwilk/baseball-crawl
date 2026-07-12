---
paths:
  - "**"
---

# Tool-Output Integrity

The harness transport layer can drop or corrupt tool output in bursts -- even on zero-IO commands like a bare `echo` -- and recover on retry. This corruption is not always empty: a nonempty result can be wrong. No tool can detect a garbled-but-nonempty read; only an agent applying this discipline can.

## Failure taxonomy

Treat any of these as a tool-output FAILURE, not as truth:

- **Empty** -- a read/command returns nothing for a target you know or expect to be non-empty.
- **Truncated** -- output is cut off (tail missing, a partial edit that did not fully land).
- **Garbled** -- output is nonempty but wrong. Examples: line numbers that disagree with an independent count (e.g., a Read reporting 17-19 lines while `cat -n` shows a clean 1-31 on the same file), stale or mismatched content, a different file's bytes, or a command echoed back instead of executed.

**Silent-empty from a tool quirk, not from absence:** the environment's `grep` is ugrep, which returns EMPTY (no error) for `grep -rn "a\|b" <path…>` -- recursive BRE alternation over multiple path args. Use `grep -rnE "a|b"` (ERE), or a single pattern / single path. Treat an unexpected empty grep as an **Empty** FAILURE to cross-check (re-run with `-E` or per-file), never as proof of absence -- in E-256-15 this exact quirk returned "no matches" for symbols that were present, and driving a deletion-eviction sweep off it would have shipped a false-clean no-op.

## Response protocol (cross-check, retry, escalate)

When a target known or expected to be non-empty returns empty, truncated, or garbled output:

1. **Treat it as a FAILURE** -- do not act on it or report it as the result.
2. **Cross-check via an independent channel** -- e.g., `wc -l` / `wc -c` / `sed -n` / `cat -n`, or a second tool (Read vs. Glob).
3. **Retry** to obtain a clean result.
4. **Escalate rather than assert** if a clean result still cannot be obtained.
5. **Read persisted review/tool findings to completion BEFORE characterizing, summarizing, or triaging them.** A preview, a `head`/`tail`, or a truncated view is not the content; a large output's first screen is not its findings. Never characterize findings, ask to triage them, or co-batch a triage decision with the command that produced them until you have read the full persisted output in your own context. (The E-230 fabrication failure was exactly this -- findings characterized before they were read; the ad-hoc main-session triage context is the thin spot.)

When two channels disagree, **the clean read wins** over a flaky empty or garbled result. A "no files found" Glob is NOT proof of absence under a flaky channel -- confirm absence through a second channel before relying on it.

## Prohibitions

1. **Never assert or relay file content or a tool outcome you have not seen cleanly in your own context.** Report what you observed, not what you expect.
2. **Never co-batch a relay or report with the same-batch command whose output it reports.** A report must describe output already in context from a prior, completed call -- never expected output and never output produced in the same tool batch as the report.
3. **Never rule on a grep / OR-pattern match -- Read and quote the literal line.** A grep hit proves a line matched *something*; it says NOTHING about which alternative of an OR-pattern matched, and an omitted or truncated matching line (`[Omitted long matching line]`) is not evidence of any particular content -- it just means the line was long. grep finds candidates; only a clean Read of the exact line range confirms the current literal text. Never report a defect, rule a claim stale-or-current, or characterize content from a match alone.
