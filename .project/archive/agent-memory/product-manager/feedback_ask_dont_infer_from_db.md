---
name: feedback-ask-dont-infer-from-db
description: Ask the operator about history instead of inferring it from surviving DB rows — the database is current state, not a historical record
metadata:
  type: feedback
---

# Ask the operator; do not infer history from what survives in the database

When a planning question is about **what has happened** — has this feature ever been used, has this population ever run through the pipeline, has anyone hit this path — **ask the operator.** Do not answer it by counting rows.

**Why:** during E-274 discovery, api-scout correctly measured "37 reports across 18 distinct target teams, none of them school-family." That was reported as **"no high-school opponent report has ever been generated,"** and PM adopted it as the epic's highest-priority gate, escalating "generate one before any build decision" to the operator ahead of everything else. The operator corrected it directly: **dozens of HS-opponent reports have been generated.** They are simply gone.

The `reports` table is **current state, not a historical record**. `cleanup_expired_reports()` unlinks expired reports, `bb report cleanup` runs opportunistically at the start of every `bb report generate`, and `bb db purge-scouting` wipes the tier outright. A report that ran and expired leaves nothing to count. So the row count answered "what exists now," and was silently substituted for "what has ever existed."

The operator's own framing, and the instruction: **ask them for things rather than infer from whatever survives in the database.** It applies to the whole team, not just PM.

**How to apply:**
- Any question phrased "has X ever…", "has anyone…", "has this ever been…" is a **history** question. The DB cannot answer it for any table subject to expiry, cleanup, or purge — which on this project includes `reports`, and everything `bb db purge-scouting` touches.
- A row count answers "what exists now." If you need "what has ever existed," ask. It is one message and it is free.
- State the distinction explicitly when reporting: "N rows exist now" is a different claim from "N have ever existed," and the first does not license the second.
- This is the sharpest instance of a broader pattern from the same session — **a measurement over one population reported as a statement about a different one**. The number is real and survives every accuracy check; what needs checking is the noun it is attached to. See [[feedback_verify_relayed_claims]] for the relay-side version.

Do not treat this as a reason to distrust api-scout's measurements. The measurement was correct and carefully scoped; the failure was in what two other agents concluded from it.
