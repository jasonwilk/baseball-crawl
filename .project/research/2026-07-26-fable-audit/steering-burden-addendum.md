# Addendum: in-session steering burden by model era (graded, relay-corrected)

16 sessions, ~2,000 user-turns; graders separated genuine operator words from relayed
teammate traffic (which is 70-97% of "user" turns in dispatch sessions — the crude
keyword scan was diluted by it in both directions).

| era | session | type | burden | op-corrections | op-redirects |
|---|---|---|---|---|---|
| 4.8 | c18a724a | dispatch (E-245) | 1/5 | 0 | 0 |
| 4.8 | c05fdb72 | dispatch (E-252) | 1/5 | 0 | 0 |
| 4.8 | 915b8dce | dispatch (E-255) | 1/5 | 0 | 0 |
| 4.8 | 81b88559 | dispatch (E-261) | 1/5 | 0 | 0 |
| 4.8 | 8769fe96 | dispatch+debug | 2/5 | 0 | 1 |
| 4.8 | e109d59d | dispatch+audit | 2/5 | 0 | 5 ("floundering", 07-09) |
| 4.8 | 322e5758 | dispatch (E-247) | 3/5 | 0 | 2 |
| 4.8 | 43c40eeb | dispatch (E-250) | 3/5 | 1 | 0 |
| 4.8 | 38d89eba | dispatch+UX iter | 3/5 | 2 | 13 |
| fable | 633490b0 | planning | 1/5 | 0 | 0 |
| fable | 54034b4d | audit (E-267) | 2/5 | 0 | 2 ("stalled?") |
| fable | e8c17a6c | planning (E-261) | 2/5 | 0 | 2 |
| fable | 3e4dc7ab | platform program | 4/5 | 1 | 13 ("wandering", "running away", "half ass", 07-03) |
| o5 | c0a2a95e | dispatch (E-270) | 1/5 | 0 | 0 |
| o5 | 16d8be7b | audit/triage | 3/5 | 0 | 3 + 2 interrupts + 1 repeat |
| o5 | 58290b38 | dispatch→discovery | 4/5 | 1 | 5 (all in discovery half) |

Findings:
1. Dispatch = 1/5 on ALL THREE models, including Opus 5's E-270.
2. Open-ended meta/discovery = 2-4/5 on ALL THREE models; the operator's wandering
   vocabulary appears verbatim in the FABLE July-3 session and 4.8 July-9 session.
3. What Opus 5 measurably added is hub self-error churn: self-corrections/100
   assistant turns med 1.18 (peak 5.5 on 07-25) vs 0.00 (4.8) / 0.20 (fable) medians;
   plus Read-starvation in the hub (4 Reads vs 86 greps in 10h).
4. Bytes per operator message are flat across eras (~100KB); the cost shows up as
   turns/corrections per deliverable, not per-exchange volume.
5. Session self-reports are unreliable telemetry (16-vs-25 error tally; "all one
   type" false; "7 of 7 silent agents" false). Use steering_scan.py (this dir):
   self-corr/100 turns + graded pushback is a one-query wandering metric.
