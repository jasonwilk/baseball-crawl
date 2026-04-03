---
name: Design Principles
description: Four reusable UX design principles established during E-178 planning — consequence-oriented labels, question-as-heading, unified verbs, coach modes
type: feedback
---

# Design Principles (E-178)

## 1. Consequence-Oriented Labels

Tell the user what they GET, not what the system found.

**Rule**: Labels and badges should describe the outcome for the coach, not the internal system state.

**Examples**:
- "Connected" (you get full stats) instead of "Discovered" (system found a match)
- "Limited access" (data is partial) instead of "Not available (403)" (system got an error)
- "Stats aren't ready yet" (softer, outcome-focused) instead of "Stats not loaded yet" (technical process state)

**How to apply**: When writing badge text, status labels, or empty-state messages, ask: "Does this tell the coach what they can do or what they'll get?" If it describes system internals, rewrite it.

## 2. Question-as-Heading Pattern

Frame headings as the user's decision, not a system instruction.

**Examples**:
- "Which team do you want to keep?" instead of "Select Canonical Team"
- "Not linked -- find on GameChanger first" instead of "Unresolved -- map first"

**How to apply**: For any page where the user makes a choice (merge, connect, configure), write the heading as the question the user is answering. This grounds the UI in the user's mental model rather than the system's data model.

## 3. Unified Verbs

One verb per action across all pages. Never use synonyms for the same operation.

**Current verb assignments**:
- "Update Stats" — all data refresh actions (replaces "Sync", "Sync Now", "Refresh")
- "Last Updated" — timestamp label for when data was last refreshed (replaces "Last Synced")
- "Updating..." — in-progress status for data refresh (replaces "Syncing...", "Running...")
- "Merge" — combining duplicate teams (replaces "Resolve")
- "Connect to GameChanger" — linking an opponent to a GC team
- "Disconnect" — unlinking an opponent

**How to apply**: Before adding a new action label, check this list. If the action maps to an existing verb, use that verb. If it's genuinely new, propose a single verb and add it here.

## 4. Three Coach Modes

Coaches interact with the system in three distinct modes. Design flows should consider which mode the coach is in.

| Mode | When | Coach mindset | Design implications |
|------|------|---------------|---------------------|
| **Setup mode** | Initial configuration, start of season | "Get me set up" | Guided flows, progressive disclosure, sensible defaults |
| **Game prep mode** | Before a game | "Show me what I need for tomorrow" | Fast access to opponent data, scouting reports, recent form |
| **Check-in mode** | Routine monitoring | "What's new since I last looked?" | Dashboards, change indicators, summary views |

**How to apply**: When designing a new page or flow, identify which mode(s) it serves. A page serving game prep mode should prioritize speed and scannability. A page serving setup mode can afford more explanation and hand-holding. A page serving check-in mode should surface changes and deltas.
