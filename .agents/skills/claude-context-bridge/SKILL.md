---
name: claude-context-bridge
description: Use when work in baseball-crawl depends on the existing Claude context and you need to load the right files without bulk-reading .claude. Keeps Codex in a watchful-partner role focused on review, verification, risk detection, and context integrity.
---

# Claude Context Bridge

Use this skill when the task depends on existing Claude workflow context, active epic or story files, or selected `.claude/` artifacts.

## Role

Codex is a watchful partner in this repo:

- prioritize review, verification, risk detection, and bounded implementation
- preserve context integrity
- do not recreate the Claude PM system or the full agent roster

## Workflow

1. Read `CLAUDE.md` first.
2. If the task is tied to a story, epic, or review request, read only the active files for that work.
3. Load only the specific `.claude/` files the task requires.
4. Stop loading context once you have enough to act.

## Load `.claude/` Selectively

- For workflow triggers or routing, read the relevant file under `.claude/skills/` or `.claude/rules/`.
- For agent memory or archived context, read only the single file the task names or clearly requires.
- Do not scan, summarize, or mirror the whole `.claude/` tree.

## Avoid

- duplicating the Claude agent roster inside Codex-owned files or outputs
- inventing a parallel PM workflow
- depending on spawned agents, `multi_agent`, or other experimental Codex features for baseline repo work
