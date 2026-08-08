# IDEA-003: Work Management as Agent Interface

## Status
`CANDIDATE`

<!--
Status definitions:
  CANDIDATE  -- Active idea, worth revisiting. Default status for new ideas.
  PROMOTED   -- Became an epic. Record which one in the Notes section.
  DEFERRED   -- Deliberately set aside. Include a reason and a re-review date.
  DISCARDED  -- Decided against. Include a reason so we don't re-propose it.
-->

## Summary
Replace or extend the current file-based epic and story system with a proper work management tool that serves as the interface between human operators and agents. The core insight: **the system of work IS how agents get tasks**. Work management is not overhead -- it is the protocol through which humans and agents collaborate.

This is not just about convenience. The long-term vision is a feedback loop where a human creates a draft epic in a tool, annotates and refines it through comments, and agents monitor for changes and eventually pick up stories for execution automatically.

## Why It Matters

The file-based system works today, but it optimizes for agent convenience at the expense of human experience. The PM agent maintains index files, numbering schemes, and status by editing markdown. A human operator who wants to see project status has to run Claude Code and ask. There is no place to annotate a story with feedback without editing the file directly, and no mechanism for the agent to notice that feedback arrived.

A richer work management layer would enable:

- **Human-in-the-loop refinement**: An operator reads a draft epic in a real UI, leaves comments, and the agent system ingests those comments and iterates -- without requiring a Claude Code session.
- **Parallel agent execution**: Stories become work items that agents claim and execute concurrently, with visibility into who is working on what.
- **Auditability**: A full record of how an epic evolved -- comments, revisions, approvals -- outside of git history.
- **Operator dashboards**: A coaching staff member or second human contributor can see project status without touching the terminal.

## The Workflow Vision

The ideal workflow looks like this:

1. **Draft creation**: A human describes a need in plain language. The product-manager agent (or the human directly) creates a draft epic in the work management tool -- structured but intentionally incomplete. Stories are not written yet. The epic is a container for the idea.

2. **Feedback loop**: The operator reads the draft in the tool's UI and leaves comments: corrections, missing context, domain knowledge the agent lacked. The agent system monitors for new comments, ingests them, and refines the epic iteratively. This back-and-forth happens in the tool, not in Claude Code sessions.

3. **Ready for dev**: When the operator is satisfied, they tag the epic (label, status change, or designated comment) as "ready for dev." Stories are written (by the PM agent), acceptance criteria are set, and the epic is live.

4. **Parallel execution**: Agents pick up individual stories, work them in parallel where dependencies allow, and mark them done. Progress is visible in the tool without querying an agent.

5. **Completion**: Stories close, the epic closes, the next planning cycle begins.

The meta-principle: **the work management tool is the contract between humans and agents**. A story in the system is a firm specification. The agent executes it without guessing. The human approves it without writing code.

## Tool Evaluation (when this idea matures)

When this idea is promoted to an epic, the first research spike will evaluate candidate tools. Criteria to assess:

| Criterion | What We Care About |
|-----------|-------------------|
| Ease of setup | How quickly can a solo operator get running? (Self-hosted vs. SaaS matters here.) |
| API richness | Can agents read and write issues, comments, status changes programmatically? |
| Comment handling | Are comments first-class objects with IDs and timestamps that agents can diff? |
| Workflow state | Can we define custom states (DRAFT, ACTIVE, BLOCKED, DONE) that agents update? |
| Agent integration | gh CLI, REST API, webhooks -- what does the integration surface look like? |
| Self-hosted vs. SaaS | Operational overhead, data residency, cost at small scale |

**Candidate tools to evaluate:**

- **GitHub Issues + Projects v2** -- native to the ecosystem if we add a GitHub remote; rich API; comment-first design; free at this scale; requires a GitHub remote (currently missing).
- **Plane** (https://plane.so/) -- open-source, self-hosted option; project/cycle/module hierarchy maps naturally to epics/sprints/stories; REST API available.
- **Vikunja** (https://vikunja.io/) -- lightweight open-source task manager; simpler than Plane; self-hosted; good API.

No tool selection yet. The evaluation itself is a deliverable of the first research spike.

## MVP Thinking

Start with the smallest feedback loop that proves the pattern works:

- A human creates a work item (issue, task, card) in the chosen tool.
- The human leaves a comment with feedback.
- An agent reads the comment via API and updates the work item.
- The human approves the result.

That's it. One story, one feedback cycle, one tool. If that loop works cleanly, expand from there. Do not design the full autonomous pipeline until the minimum viable version is proven.

Questions to answer in an MVP:
- Which tool allows an agent to read comments with the least API surface area to manage?
- What does the "ready for dev" signal look like in that tool? A label? A status transition? A magic comment string?
- Can the agent write back to the same tool without human intervention, or does it produce a file for the human to paste?

## Dependencies and Blockers

- [ ] The project must have a GitHub remote (currently not in a git repo -- see env context)
- [ ] A tool must be selected from the candidates above (requires a research spike)
- [ ] The agent system needs API access to the chosen tool -- gh CLI, REST, or webhook receiver
- [ ] A migration plan for existing file-based epics and stories must be decided (import, let expire, or hybrid)
- [ ] Architectural design for the feedback-loop integration (which agents monitor for comments? how often? triggered or polling?) -- this is a claude-architect concern

## Open Questions

- Does the E-NNN numbering scheme survive the move? GitHub assigns its own sequential issue numbers. We could use labels (e.g., `epic:E-001`) or abandon our numbering in favor of native references.
- Do we keep the file-based system as a fallback / offline working mode, or fully migrate?
- Would agents read epic context from the tool at runtime, or would they sync to local files first? The runtime option requires network access and auth inside agent sessions.
- What does the "ready for dev" trigger look like, and how does an agent detect it reliably?
- Does the ideas backlog move to the tool (e.g., GitHub Discussions), or stay as files until an idea is promoted?
- For a self-hosted tool (Plane, Vikunja): where does it run? A local machine feels fragile; a VPS adds infrastructure; Cloudflare Workers cannot host a traditional server.

## Collaboration Note

When promoted to an epic, this will involve both the **product-manager** (work management workflow, story structure, numbering scheme migration) and **claude-architect** (system design for agent-to-tool integration, monitoring architecture, feedback loop mechanics). Neither can design this in isolation.

This is a meta-layer decision: how agents and project management interface with each other. It deserves careful design before implementation.

## Notes

This idea subsumes the original narrower framing ("GitHub-Native Project Management"). The scope has grown: this is no longer just about moving files to GitHub -- it is about designing the agent-operator collaboration protocol.

Promote only when:
- The project has a GitHub remote (or a self-hosted tool is running), AND
- The file-based system is demonstrably causing friction (navigation overhead, missed feedback, coordination failures), OR
- A strategic decision is made to build toward a more autonomous agent workflow

Do not compete with epics that deliver coaching value. This is infrastructure for the team, not value for the coaches.

---
Created: 2026-02-28
Last reviewed: 2026-02-28
Review by: 2026-05-29
