---
name: workflow-help
description: This skill should be used when the user says "/workflow-help", "workflow help", "what commands do I have", "what can I do", "show me the workflows", "list the workflows", "what are the trigger phrases", or "cheat sheet". Prints the workflow cheat sheet.
---

# Skill: workflow-help

**Category**: Quick Reference
**Adapted for**: baseball-crawl

---

## Purpose

Display a concise cheat sheet of the chunk lifecycle and the surviving trigger phrases. This is a
reference card, not a tutorial. Plain text output, no markdown rendering.

---

## Action

Print the following cheat sheet exactly as plain text. Do not add commentary, explanation, or
offer to run any command. Do not render as markdown. Just print it and stop.

```
/workflow-help  ─────────────────────────────────────────

THE CHUNK LIFECYCLE  (full text: CLAUDE.md)
  1 spec        plan-mode interview -> .project/specs/
  2 spec-review headless: codex exec against the spec file
  3 execute     FRESH session, from the spec
  4 verify      the spec's commands; code -> full suite
  5 review      /code-review  (+ /security-review, /simplify)
  6 scan        python3 src/safety/pii_scanner.py --staged
  7 approve     operator reads the staged diff
  8 commit      [pii-hook] line is the receipt
  9 handoff     flip spec Status; next-session prompt
 10 clear       operator types /clear

LINE OF MARCH
  .project/specs/README.md   what's NOW / NEXT / parked

CODE REVIEW
  "codex review"            Codex audits the diff
  └─ + "prompt"             Returns copy-paste prompt

API CAPTURE  ⚠ time-sensitive
  "ingest endpoint"         Execute curl + document endpoint
                            gc-signature expires in minutes

VISION
  "curate the vision"       Review parked vision signals

─────────────────────────────────────────────────────────
CLI commands:  bb --help
```

---

## Maintenance

When a workflow skill is added, renamed, or retired, update the cheat sheet above.

**The cheat sheet is a RENDERING of its sources, never a second source.** Re-derive it rather than
editing it independently:

- Lifecycle steps and the line-of-march pointer: **`CLAUDE.md`**, sections "How work gets done
  here" and "Line of march".
- Code review: `.claude/skills/codex-review/SKILL.md` frontmatter.
- Ingest endpoint: `.claude/skills/ingest-endpoint/SKILL.md` frontmatter.
- Vision curation: `.claude/rules/vision-signals.md`, which carries the trigger phrase and the
  rule that `docs/VISION.md` is edited only in a deliberate curation session.

`codex-spec-review` is deliberately absent: it resolves only `epics/` directories, so it cannot
review a spec file. Lifecycle step 2 runs headless `codex exec` instead. Add it back when Step 3
rewrites its input resolution.
