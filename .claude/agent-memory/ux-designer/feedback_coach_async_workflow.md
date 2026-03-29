---
name: Coach async workflow reality
description: Coaches don't watch progress -- they trigger actions and come back later. Status must be correct on return, not just during wait.
type: feedback
---

Coaches don't sit on one page watching progress indicators. They click around, open tabs, walk away to talk to a player. Auto-refresh / polling is nice-to-have polish, not the core interaction.

**Why:** Baseball-coach validated this during E-178 design review. The coaching workflow is inherently async: trigger an update, go do coach things, come back later.

**How to apply:** For any background operation (stats update, scouting sync, report generation):
- The **database-backed status badge** is the truth signal -- always correct on page load. This is the primary design.
- **Auto-refresh / live updates** are polish -- useful if they happen to stay, but never the thing you count on.
- **Flash messages** confirm the action was triggered, not that it completed.
- Design for the "come back later" moment, not the "sit and wait" moment.
