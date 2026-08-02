---
name: workflow-help
description: This skill should be used when the user says "/workflow-help", "workflow help", "what commands do I have", "what can I do", "show me the workflows", "list the workflows", "what are the trigger phrases", or "cheat sheet". Prints the workflow cheat sheet.
---

# Skill: workflow-help

**Category**: Quick Reference
**Adapted for**: baseball-crawl

---

## Purpose

Display a concise cheat sheet of all workflow trigger phrases and their effects. This is a reference card, not a tutorial. Plain text output, no markdown rendering.

---

## Action

Print the following cheat sheet exactly as plain text. Do not add commentary, explanation, or offer to run any command. Do not render as markdown. Just print it and stop.

```
/workflow-help  ─────────────────────────────────────────

PLAN
  "plan E-NNN"              PM writes stories
  "curate the vision"       PM reviews vision signals

SPEC REVIEW
  "spec review E-NNN"       Codex audits planning docs
  └─ + "prompt"             Returns copy-paste prompt

DISPATCH
  "implement E-NNN"         Full agent dispatch + merge
  └─ + "and review"         Chains code review after

CODE REVIEW
  "codex review E-NNN"      Codex audits implementation
  └─ + "prompt"             Returns copy-paste prompt

API CAPTURE  ⚠ time-sensitive
  "ingest endpoint"         Execute curl + document endpoint
                            gc-signature expires in minutes

─────────────────────────────────────────────────────────
HAPPY PATH:  plan → spec review → implement [and review]
─────────────────────────────────────────────────────────
CLI commands:  bb --help
```

---

## Maintenance

When a workflow skill is added, renamed, or retired, update the cheat sheet above.

**The cheat sheet is a RENDERING of the single source, never a second source.** The authoritative location for each workflow's trigger phrases is the **`description` frontmatter** of its own SKILL.md -- the cheat sheet displays an abbreviated selection of those phrases for the user, which is its whole function, and it must be re-derived from them rather than edited independently:

- Plan: `.claude/skills/plan/SKILL.md` frontmatter
- Implement: `.claude/skills/implement/SKILL.md` frontmatter
- Spec review: `.claude/skills/codex-spec-review/SKILL.md` frontmatter
- Code review: `.claude/skills/codex-review/SKILL.md` frontmatter
- Ingest endpoint: `.claude/skills/ingest-endpoint/SKILL.md` frontmatter
- **Vision curation: `CLAUDE.md`'s `## Workflows` section** -- it is the one workflow with no skill file, so CLAUDE.md carries it in full and is its single source

Internal-only skills (context-fundamentals, filesystem-context, multi-agent-patterns, agent-standards) are omitted -- they load automatically and are never triggered by the user directly.
