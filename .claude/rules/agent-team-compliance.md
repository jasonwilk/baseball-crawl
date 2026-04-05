---
paths:
  - "**"
---

# Agent Team Compliance

## User Request Classification -- Execute Before Responding

When you receive a user message, scan it against the three patterns below BEFORE selecting any tools. If a pattern matches, follow its required action. These patterns fire at the decision point -- before you choose between Task tool, Agent Teams, or answering directly.

## Why These Rules Exist

**When a user names specific agents, they are requesting those agents' judgment -- not any correct answer.** The act of consulting is itself part of the deliverable. Substituting your own answer -- even if factually correct -- violates the user's intent.

## Scope

These patterns apply to **explicit agent naming only** -- cases where the user names specific agents or roles in their request. They do NOT govern domain-implied consultation (e.g., "the PM's advisory Consultation Triggers table recommends checking with baseball-coach for stat questions"). Domain-implied consultation remains advisory per the PM's agent definition.

## Pattern 1: Explicit Team Request

**Trigger**: The user names 2 or more agents or roles in a team-formation context (e.g., "start a team with PM and architect", "get SE and DE working on this together", "I want architect, coach, and PM on this").

**Required action**: Use Agent Teams. Create the team via TeamCreate and spawn each named agent as a teammate. Assign work through the team.

**Prohibited**:
- Spawning one agent via Task tool and asking it to consult the others on your behalf.
- Using sequential Task tool calls instead of a team when the user requested a team.
- Silently downgrading to a non-team workflow without telling the user.

## Pattern 2: Explicit Consultation Directive

**Trigger**: The user names a specific agent as a required participant -- e.g., "consult [agent]", "work with [agent]", "ask [agent]", "have [agent] look at this", "check with [agent]", "get [agent]'s input", or any phrasing that designates a specific agent to contribute.

**Required action**: Actually spawn that agent (via Agent Teams if Pattern 1 also applies, or Task tool otherwise). Send the question or context to the spawned agent. Wait for the agent's response. Incorporate the agent's actual response into your work.

**Prohibited**:
- Answering on the agent's behalf based on what you think they would say.
- Claiming to have consulted the agent without spawning them.
- Paraphrasing the agent's likely response instead of getting their actual response.
- Skipping the consultation because you believe you already know the answer.

## Pattern 3: Anti-Fabrication Rule

**Trigger**: A spawned agent reports that it cannot reach or spawn another agent (e.g., PM says "I can't spawn SE" or an implementer says "I need input from architect but can't reach them").

**Required action**: The main session spawns the missing agent directly (the main session has full spawning capability even when nested agents do not). Relay the original question to the newly spawned agent. Return the agent's actual response to the requesting agent.

**Prohibited**:
- Answering the question yourself and relaying your answer as if it came from the missing agent.
- Telling the requesting agent "I'll handle it" and then providing your own judgment instead of the named agent's.
- Claiming the missing agent is unavailable without attempting to spawn them.
