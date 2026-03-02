# Skill: multi-agent-patterns

**Category**: Architectural
**Adapted for**: baseball-crawl

---

## Activation Triggers

Load this skill when you are about to:

- **Dispatch a story via Agent Teams** and need to verify the context block is complete
- **Route a request through multiple agents** (orchestrator -> PM -> implementing agent)
- **Debug an implementing agent that completed a task incorrectly**

---

## The Telephone Game Problem

When a request passes through multiple agents, each relay risks losing information. The orchestrator paraphrases, the PM summarizes, the implementing agent builds against a distortion of the original intent.

### Mitigation: Verbatim Relay

Pass original content at every relay point. Never summarize.

**Orchestrator -> PM**: Pass the user's request verbatim. If it's ambiguous, ask the user — don't guess.

**PM -> Implementing Agent**: Include the **full story file text** and **full epic Technical Notes** in every dispatch. Not a summary. Every acceptance criterion, file path, and constraint.

## Baseball-Crawl's Routing Chain

```
User
  |
  v
orchestrator          (routes all requests)
  |
  +-- direct: api-scout        (no PM needed)
  +-- direct: baseball-coach   (no PM needed)
  +-- direct: claude-architect  (no PM needed)
  |
  v
product-manager       (plans, dispatches via Agent Teams)
  |
  v
implementing agents   (general-dev, data-engineer -- require story reference)
```

## PM Dispatch Checklist

Before spawning a teammate for a story:

- [ ] Read the story file in full
- [ ] Read the epic Technical Notes in full
- [ ] Include full story file text + Technical Notes in the prompt (not a summary)
- [ ] Set story status to IN_PROGRESS
- [ ] Spawn stories in parallel when they have no file conflicts

## When to Shorten the Chain

If the request is consultative (not implementation), skip the PM:
- API exploration -> api-scout directly
- Domain questions -> baseball-coach directly
- Agent infrastructure -> claude-architect directly

If the request produces code, schema, or tests -> route through PM.

## Diagnosing Failures

If an implementing agent's output doesn't match intent:
1. Did it receive the full story file, or a summary?
2. Did the story accurately reflect the user's requirement?
3. Did the orchestrator pass the request verbatim, or paraphrase?

Work backward through the chain. The problem is usually at the first relay where a summary replaced the original.
