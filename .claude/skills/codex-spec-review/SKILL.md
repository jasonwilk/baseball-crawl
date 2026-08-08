---
name: codex-spec-review
description: This skill should be used when the user says "spec review", "review the spec", "codex spec review", "spec review prompt", "codex spec review prompt", "generate spec review prompt", "check the spec", or "run spec review" -- or otherwise implies reviewing a chunk spec against the spec-review rubric. The word "spec" is the mode discriminator: a review request that LACKS it belongs to the codex-review skill, not this one. A trigger containing "prompt" selects the prompt-generation path; otherwise the headless path runs.
disable-model-invocation: true
---

# Skill: codex-spec-review

**Category**: Workflow Automation
**Adapted for**: baseball-crawl

---

## Execution Path Detection

This skill supports two execution paths, detected from the user's trigger phrase:

- **Headless (default)**: The user's phrase does NOT contain "prompt". Claude runs the review via the script, captures output, presents findings, and offers advisory triage.
- **Prompt generation**: The user's phrase CONTAINS "prompt" (e.g., "spec review prompt"). Claude assembles a lean prompt and presents it in a fenced code block for copy-paste. No execution, no triage.

---

## Prerequisites

Before executing either path, verify:

1. **Identify the target spec.** The user may name a spec file, a slug, or a date. If none is given, ask which spec to review. Live specs are `.project/specs/<date>-<slug>.md`; completed ones are under `.project/specs/done/`.
2. **Resolve the spec file.** Check `.project/specs/` first. If not found there, check `.project/specs/done/` -- and if it is found there, note to the user that the spec is already COMPLETE, so the review may surface learnings but cannot change landed work. Proceed normally.
3. **The spec file exists.** If it does not, report the error with the paths checked and stop.
4. **The rubric file exists.** Verify `/workspaces/baseball-crawl/.project/codex-spec-review.md` is present. Do NOT read its contents. If missing, report the error and stop.

---

## Headless Path

### Step 1: Run the script

Run the spec review script via Bash in the foreground:

```
timeout 1200 ./scripts/codex-spec-review.sh <spec-file>
```

If the user provided additional context, pass it via `--note`:

```
timeout 1200 ./scripts/codex-spec-review.sh <spec-file> --note "Focus on the destructive seams"
```

Codex typically takes 1-2 minutes for a one-page spec. A long or heavily cross-referenced spec may take up to 5 minutes.

### Step 2: Handle errors

- **Exit code 124 (timeout)**: Codex timed out after 20 minutes. Report the timeout to the user and ask how to proceed. Do not retry automatically.
- **Other non-zero exit codes**: The script itself failed (codex not installed, spec file not found, missing rubric). Report the specific error message to the user and stop.

### Step 3: Evaluate output

- If the output states "No findings. This spec is ready to execute." or similar clean result: report "Clean review -- no findings" to the user. Skip triage. Workflow ends.
- If the output contains findings: present the full Codex findings to the user. Proceed to Step 4.

### Step 4: Offer advisory triage

**Read-receipt gate — REQUIRED. Triage MUST NOT proceed until this is satisfied.**

The headless script streams Codex's output to the Bash tool result, which is truncated to a *preview* when the result is large. Triaging off that preview is the motivating failure mode: in the E-230 dispatch a triage question was fired off a ~2KB preview of a ~373KB persisted Codex result, mischaracterizing four valid findings as "2 LOW already-adjudicated." Before ANY triage tool or action runs against the review result you MUST:

1. **Take the `RESULT_FILE` path from the script's own receipt.** The script tees the full review to a deterministic file and prints `RESULT_FILE=<path>`, its `wc -l`, and its `tail -n 1`. Use that file. Do NOT re-run the script with a manual stdout redirect — the manual redirect is the documented fabrication hole (44 of 48 invocations skipped it), which is exactly why the script now emits the receipt itself. Do NOT rely on the inline Bash preview.
2. **Read the file to completion** and produce a complete digest of every finding (the spec section cited, the actual claim). Completeness of findings is the objective — account for EVERY finding, not a head/tail sample. You need not hold the raw bytes in context (a very large result would blow the red-zone budget), but you must process every finding.
3. **Report the receipt** — the `RESULT_FILE` path, its line count, and its last line, as the script printed them — before triage begins.

The receipt is a deliberate speed-bump / discipline aid, NOT a cryptographic guarantee (it can in principle be produced without reading the middle), so the binding obligation is the complete finding digest in step 2; the receipt is the forcing function. This gate structurally enforces the always-loaded tool-discipline rule (`.claude/rules/tool-discipline.md` — never assert or triage content not seen cleanly); it is the structural form of the read-findings-before-triage lesson.

After the receipt and complete digest are satisfied, triage the findings yourself:

1. Read the Codex findings and identify which domains they touch (schema, implementation, API, coaching, documentation, UX).
2. Two domain subagents survive -- `api-scout` (GameChanger API archaeology) and `baseball-coach` (coaching semantics). Consult one only when a finding genuinely turns on its domain; don't delegate what a handful of tool calls finishes.
3. Present every finding with a recommended action (refine, fix, defer, dismiss) and let the operator rule.

**Triage is advisory until the operator rules.** Record the dispositions in the spec's progress log.

---

## Prompt-Generation Path

### Step 1: Resolve the spec file

Resolve to an absolute path (e.g., `/workspaces/baseball-crawl/.project/specs/2026-08-05-rung-c-season-year-filter.md`). Do NOT read the file -- the prompt gives Codex the path.

### Step 2: Assemble the lean prompt

Build the prompt matching the format used by `scripts/codex-spec-review.sh`:

```
SPEC-REVIEW REQUEST

Rubric: /workspaces/baseball-crawl/.project/codex-spec-review.md
Spec under review: {absolute spec file path}

Instructions:
1. Read the rubric at the path above.
2. Read the spec file above.
3. Review the spec against the rubric. Follow its Evaluation Checklist exactly.
4. Check the spec's claims against the actual repository -- a spec is a CLAIM, not a fact.
5. Cite the spec's section heading for each finding.
6. If the spec is clean, state: "No findings. This spec is ready to execute."
```

If the user provided a runtime note (via `--note` or inline context), include it between the paths and instructions:

```
SPEC-REVIEW REQUEST

Rubric: /workspaces/baseball-crawl/.project/codex-spec-review.md
Spec under review: {absolute spec file path}

RUNTIME CONTEXT NOTE
{note text}

Instructions:
1. Read the rubric at the path above.
2. Read the spec file above.
3. Review the spec against the rubric. Follow its Evaluation Checklist exactly.
4. Check the spec's claims against the actual repository -- a spec is a CLAIM, not a fact.
5. Cite the spec's section heading for each finding.
6. If the spec is clean, state: "No findings. This spec is ready to execute."
```

### Step 3: Present to the user

Present the assembled prompt inside a fenced code block (triple backticks) so the user can copy-paste it directly into Codex.

Do NOT execute the prompt. Do NOT offer triage. Prompt-generation path ends here.

---

## Workflow Summary

```
User says "spec review <slug>" (or variant)
  |
  v
Load this skill
  |
  v
Detect execution path: "prompt" in phrase? -> prompt-gen, else headless
  |
  v
Resolve spec file (.project/specs/, then done/; ask user if ambiguous)
  |
  v
Verify prerequisites (spec file exists, rubric exists)
  |
  +---> HEADLESS PATH:
  |       Run codex-spec-review.sh <spec-file> [--note]
  |       Read RESULT_FILE to completion; report the receipt
  |       No findings? -> Report clean review, stop
  |       Findings? -> Triage in-session; consult a domain agent only if a finding needs it
  |       Present dispositions; operator rules
  |
  +---> PROMPT-GEN PATH:
          Assemble lean prompt (request header, rubric path, spec path, optional note, instructions)
          Present in fenced code block
          Stop (no execution, no triage)
```

---

## Edge Cases

### Spec not found
Check `.project/specs/` first, then `.project/specs/done/`. If neither has a matching file, report the error with the paths checked and stop.

### Spec is already COMPLETE
If found under `.project/specs/done/`, note to the user that the spec has landed. Proceed normally -- the review may surface learnings, but it cannot change committed work.

### Codex not installed (headless only)
The script checks for `codex` in PATH and exits with an error including install instructions. Report this error to the user and stop.

### Codex returns no findings (headless only)
Report "Clean review -- no findings" to the user. Do not offer triage. There is nothing to triage.

### Rubric file missing
Report the error and stop. Do not attempt to generate a prompt or run the script without the rubric.

---

## Anti-Patterns

1. **Do not spawn a subagent to run the review or its triage.** The session runs both. The only two subagents left are the domain specialists `api-scout` and `baseball-coach`, consulted on a specific domain question.
2. **Do not offer triage in the prompt-generation path.** Triage is headless-only. The prompt-gen path assembles and presents -- nothing more.
3. **Do not embed rubric or spec content in the prompt.** The skill resolves paths and confirms existence; it does not read or cache file contents.
4. **Do not auto-apply Codex suggestions.** Codex findings are presented for the operator's judgment; triage recommends actions, the operator rules.
5. **Do not add separator walls, "Begin your response with" instructions, or team recommendation blocks to prompts.** The lean format has no ceremony.
6. **Do not re-run the script with a manual stdout redirect to satisfy the read-receipt gate.** The script's own `RESULT_FILE` is the receipt; a second run costs another full review and reintroduces the hole the receipt closed.
