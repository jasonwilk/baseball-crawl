# CE-5 Handoff: §3 Curation-Adjacent Decision Rationales (recorded 2026-07-05)

Three SOUND_BUT_UNDERDOCUMENTED items from `PLATFORM-AUDIT.md` §3 (lines 199-201) were routed into the 2026-07-05 vision-curation session for a **decision + recorded rationale**. The decisions are captured here; the **physical context-layer writes belong to claude-architect in CE-5** (audit §7 CA docket, line 286: "Decisions to document: context-growth counterweight; memory lifecycle policy; roster review record"). PM does NOT write context-layer files for these.

**Why:** the routing boundary (agent-routing.md Routing Precedence) sends context-layer files to claude-architect. PM's job in the curation session was to surface the Jason-facing decision and draft the rationale; CE-5's CA codifies it.
**How to apply:** when CE-5 is refined/dispatched, hand these three rationales to claude-architect as the source text for its charter/rule edits. Do not re-litigate the decisions; they are Jason-approved (2026-07-05).

## 1. Nine-agent roster review (audit §3 item #1)
**Decision (D4, Jason-approved 2026-07-05): refocus both ux-designer and docs-writer; retire neither.**
Recorded rationale: *"The 2026-06-12 reports-first reframe (E-239) deleted the coaching dashboard but not the design/documentation need. ux-designer refocuses from dashboard UI to report layout, trust surfaces, and the tools-hub IA pass (2026-06-20 signal — a live forward docket). docs-writer refocuses from dashboard docs to admin runbooks + coaching how-tos for reports and morning-run (it has a live CE-5 docket). Neither is retired; both have forward work."*
Physical home: `.claude/agents/ux-designer.md`, `.claude/agents/docs-writer.md` — CA edits in CE-5. Also referenced in audit §7 CA docket line 284 ("ux-designer repurpose-or-retire (user decision)" — now DECIDED: refocus) and line 300-301 (ux-designer own-memory rewrite around surviving surfaces).

## 2. One-directional context-layer growth (audit §3 item #2)
**Decision: add a counterweight to the closure assessment.**
Recommended shape: a closure-assessment **trigger 7** — "Did this epic grow the context layer net-positive? If so, what was compressed or retired to offset?" A review prompt at closure, NOT a hard line-count cap (the audit notes a line-count budget is density-gameable). Simple-first.
Physical home: `.claude/rules/context-layer-assessment.md` — CA writes in CE-5.

## 3. Persistent agent-memory lifecycle policy (audit §3 item #3)
**Decision: record a lightweight lifecycle policy.**
Recommended policy (simple-first): (a) **promote** a memory to a rule when its lesson is cited across 2+ epics or generalizes beyond one agent; (b) **strike** a memory when the code/flag/decision it names is deleted (staleness eviction at the next epic that touches that area); (c) **per-agent review cadence** rather than a hard KB cap (the ~516KB total is a symptom, not a threshold). Jason may want to set the specific ceiling/cadence when CE-5 is refined.
Physical home: a short new rule or a section in `.claude/rules/context-layer-assessment.md` — CA writes in CE-5.

## Note on item #4 (audit §3, "two-artifact vision system")
REVISIT/defense-held; the agreed remedy was simply running the overdue curation, which was done 2026-07-05. No design change, no CE-5 action — resolved by the curation itself.
