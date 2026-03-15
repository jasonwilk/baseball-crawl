# Skill: multi-agent-patterns

**Category**: Architectural
**Adapted for**: baseball-crawl

---

## Activation Triggers

Load this skill when you are about to:

- **Dispatch a story via Agent Teams** and need to verify the context block is complete
- **Route a request through agents** (main session -> implementing agent)
- **Debug an implementing agent that completed a task incorrectly**

---

## The Telephone Game Problem

When a request passes through multiple agents, each relay risks losing information. An intermediary summarizes, the implementing agent builds against a distortion of the original intent.

### Mitigation: Verbatim Relay

Pass original content at every relay point. Never summarize.

**Main Session -> Implementing Agent**: Include the **full story file text** and **full epic Technical Notes** in every dispatch. Not a summary. Every acceptance criterion, file path, and constraint.

In this project, the main session dispatches directly to implementing agents and spawns PM as a teammate for status management and AC verification. PM is not a relay point for context -- the main session packages context directly for implementers. The primary telephone game risk is in how the main session packages that context.

## Baseball-Crawl's Routing Chain

```
User
  |
  +-- direct: api-scout        (no PM needed)
  +-- direct: baseball-coach   (no PM needed)
  +-- direct: claude-architect  (no PM needed)
  |
  +-- planning: product-manager  (plans epics, refines stories)
  |
  +-- dispatch: main session     (spawns + coordinates implementers directly)
  |
  v
implementing agents   (software-engineer, data-engineer -- require story reference)
```

## Main Session Dispatch Checklist

Before spawning an implementer for a story:

- [ ] Read the story file in full
- [ ] Read the epic Technical Notes in full
- [ ] Include full story file text + Technical Notes in the prompt (not a summary)
- [ ] Route to PM to set story status to IN_PROGRESS
- [ ] Spawn stories in parallel when they have no file conflicts

## When to Shorten the Chain

If the request is consultative (not implementation), the user can invoke agents directly:
- API exploration -> api-scout directly
- Domain questions -> baseball-coach directly
- Agent infrastructure -> claude-architect directly

If the request produces code, schema, or tests -> PM plans, main session dispatches.

## Diagnosing Failures

If an implementing agent's output doesn't match intent:
1. Did it receive the full story file, or a summary?
2. Did the story accurately reflect the user's requirement?
3. Did the main session package the full context, or paraphrase?

Work backward through the chain. The problem is usually at the point where a summary replaced the original.
