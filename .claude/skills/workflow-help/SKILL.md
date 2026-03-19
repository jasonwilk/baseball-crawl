# Skill: workflow-help

**Category**: Quick Reference
**Adapted for**: baseball-crawl

---

## Activation Triggers

Load this skill when the user says any of:

- "/workflow-help", "workflow help"
- "what commands do I have", "what can I do"
- "show me the workflows", "list the workflows"
- "what are the trigger phrases", "cheat sheet"

---

## Purpose

Display a concise cheat sheet of all workflow trigger phrases and their effects. This is a reference card, not a tutorial -- one line per command, grouped by workflow phase.

---

## Action

Print the following cheat sheet exactly. Do not add commentary, explanation, or offer to run any command. Just print it and stop.

```
PLANNING
  "plan an epic for X"              → plan skill: team + spec review + refine + READY
  "plan and dispatch X"             → plan + implement chained (full pipeline)
  "plan this with PM and [agent]"   → plan skill with named experts

DISPATCH
  "implement E-NNN"                 → dispatch stories to implementers
  "start E-NNN"                     → same as implement
  "implement E-NNN and review"      → dispatch + codex review + CR review chained

SPEC REVIEW
  "spec review E-NNN"               → codex spec review (headless)
  "spec review prompt"              → generate prompt for async codex

CODE REVIEW
  "codex review"                    → code review (uncommitted changes)
  "codex review base main"          → code review (branch diff)
  "codex review prompt"             → generate review prompt for async codex

VISION
  "curate the vision"               → PM reviews vision signals with user

API INGESTION
  "ingest endpoint"                 → api-scout processes curl from secrets/gamechanger-curl.txt

DIRECT AGENTS (no PM needed)
  api-scout                         → API exploration, endpoint docs
  baseball-coach                    → domain consultation, stat validation
  claude-architect                  → agent infra, CLAUDE.md, rules, skills
```

---

## Maintenance

When a workflow skill is added, renamed, or retired, update the cheat sheet above. The authoritative source for each workflow's trigger phrases is its own SKILL.md file:

- Plan: `.claude/skills/plan/SKILL.md`
- Implement: `.claude/skills/implement/SKILL.md`
- Spec review: `.claude/skills/codex-spec-review/SKILL.md`
- Code review: `.claude/skills/codex-review/SKILL.md`
- Ingest endpoint: `.claude/skills/ingest-endpoint/SKILL.md`
- Vision curation: PM agent definition (`.claude/agents/product-manager.md`, curate task type)
