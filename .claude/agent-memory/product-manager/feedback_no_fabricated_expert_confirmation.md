---
name: Never cite expert input from memory without verification
description: When story Notes/ACs claim "expert X confirmed Y," verify by reading the actual relay before writing it; fabricated confirmations are anti-fabrication violations
metadata:
  type: feedback
---

When PM writes a story Notes/AC/TN that cites an expert's confirmation of a domain fact (e.g., "DE confirmed `team_rosters.batting_order` is populated by the scouting pipeline"), PM MUST verify the claim by re-reading the actual expert relay before writing it. Citing an expert's input from memory — without re-reading — risks fabricating a confirmation the expert never gave.

**Why:** During E-229 Phase 2, PM wrote in E-229-07 Notes: "The batting-order data dependency was confirmed during round-2: scouting pipeline may not populate batting_order for opponent rosters." DE's actual round-2 message addressed five specific engineering items (jersey lookup, raw BIP coordinates, sample-size threshold, marker collision, mixed orientation) — batting_order availability was NOT one of them. DE never confirmed anything about batting_order in round 2. PM conflated what coach raised in coach Q-D (batting-order need + fallback) with what PM hoped DE had confirmed about its availability, and wrote a story Note that fabricated the confirmation. DE caught this in round-1 holistic review as a Blocker (B-5).

This is a direct violation of `.claude/rules/agent-team-compliance.md` Pattern 3 (Anti-Fabrication Rule), even though that rule was written for main-session-relays-fake-expert-input scenarios. The same anti-fabrication principle binds PM when writing planning artifacts: never claim an expert confirmed X when the expert did not in fact confirm X.

**How to apply:**

1. **Before writing a story Note/AC/TN that claims expert confirmation**, grep or re-read the actual expert relay. The relay is in the conversation history or saved to PM scratch — find the verbatim text that confirmed the claim.

2. **If the claim cannot be sourced to a specific expert message**, downgrade the language. "DE confirmed X" → "Per current schema (verify against `migrations/001_initial_schema.sql`), X" or "PM assumed X based on roster structure" or simply ask the expert in a round-2 consultation.

3. **The high-risk surfaces are**:
   - Story Notes sections (free-form prose where PM tends to add context)
   - Story Technical Approach paragraphs (where PM cites why a decision was made)
   - Open Questions answers (where PM may claim "DE/coach resolved this in round 2")
   - Cross-story references ("per DE round-2 confirmation in E-229-07")

4. **Cheap verification**: when writing a story Note that cites an expert, copy the verbatim quote into the Note (or paraphrase tightly with a "per round-N relay" marker). If you can't quote, you don't actually have the confirmation.

5. **If you discover a fabrication after the fact**: own it explicitly in triage (as PM did in E-229 iteration 1 triage), accept the corresponding finding, fix the affected files, and capture the lesson here.

The agent-team-compliance Pattern 3 fires when the main session is the fabricator; this memory fires when PM is the fabricator during planning. Same anti-pattern, different role.

This applies during any planning artifact production where expert input is being incorporated, not just E-229.
