---
name: Peer DM relay drops messages — never silent-fail, sanity-check against task list
description: Peer-to-peer SendMessage drops messages on this team; before declaring idle, sanity-check inbox state against live tasks and ack receipt explicitly to recover the channel
type: feedback
---

Peer-to-peer SendMessage between PM and team-lead drops messages on this team. The project rule already says main-session relay is the default channel for substantive content and peer DMs are reserved for lightweight acknowledgments — but PM-side discipline is also required to detect drops when they happen.

**Why:** During E-228 Codex iteration-2 triage, team-lead's substantive assignments arrived as task-creation events (CX2-1 through CX2-5) but the corresponding peer-DM context messages dropped. PM read the inbound task-assignment echoes as "stale duplicates of iteration-1 work" and dismissed them. Team-lead was sitting on completed work waiting for PM triage while PM was reporting "no forward motion / awaiting handoff" — a silent fail on both sides. Multiple cycles of this happened before the user flagged it directly.

**How to apply:**

1. **No polling, no inbox.** Messages from team-lead arrive automatically as `<teammate-message>` blocks. If you don't see one, none arrived. Don't fabricate "I'm waiting on the team lead" without checking the actual conversation state.

2. **Before declaring idle**, sanity-check: does the last inbound message match the current state of the work? If team-lead is asking about iteration N but the last inbound message in the conversation is from iteration N-1, something dropped. Send a brief status check via SendMessage(to="team-lead", ...): "last assignment I have is X, is that current?" Do not go idle — that is the silent-fail mode.

3. **The task list is a recovery channel.** When peer DM drops, team-lead creates tasks (TaskCreate) for the work. If TaskList shows live tasks (e.g., CX2-1 through CX2-5) that don't match what's in the conversation stream, the conversation is behind. Call it out and ask team-lead to re-send rather than guessing.

4. **Don't dismiss recent inbound as "stale echoes."** When the same task-assignment ID appears multiple times, that's usually team-lead re-sending after a drop, not a duplicate. The default disposition is "ack receipt explicitly and ask before discarding." Echoes are only stale if their content matches work you can prove is done (sweep + match the description against current spec state) AND no live task by that ID is open. If a task by that ID is `pending` or `in_progress`, it's live — process it, don't dismiss.

5. **Ack pattern when team-lead asks for it.** If a message starts with "ACK FIRST" or similar, send a one-line SendMessage reply ("received, working it") before any other action. That's the cheap way for team-lead to confirm the channel is alive.

6. **When in doubt, ack and ask.** The cost of an extra status check is one message; the cost of a silent fail is hours of lost work on both sides.

This applies during any multi-iteration review cycle, not just E-228. The relay-reliability problem is structural to the team, not specific to one epic.
