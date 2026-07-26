# IDEA-197: A 415 (stale Accept pin) mis-signals as a transient 5xx all the way to the operator

## Status
`CANDIDATE`

## Summary
When GameChanger returns **415 Unsupported Media Type** — the signature of a stale or wrong vendor `Accept` version pin — the client correctly does **not** retry it, but raises `GameChangerAPIError`, whose documented meaning everywhere else is *"5xx after retries."* Downstream, every consumer reads that as transient. The operator is told to wait and retry a condition that will never resolve on its own: the request itself is wrong and stays wrong until a pin is corrected.

## Why It Matters
The failure is **deterministic but reported as transient**, which points the operator away from the cause at exactly the moment they need pointing toward it. Concretely, a stale boxscore pin yields a team crawling **zero games with only warnings**, summarized as a transient error — a silent-ish failure wearing a "try again later" label.

**Mechanism, verified in code (2026-07-26):**
- `src/gamechanger/exceptions.py:46` — `GameChangerAPIError`: *"Raised when the API returns a 5xx error after all retries are exhausted."*
- `.claude/rules/auth-module.md` states the same in its exception hierarchy: `GameChangerAPIError` — HTTP 5xx after retries.
- `src/gamechanger/client.py` — a 415 does not reach any 4xx-specific branch; it falls to the generic tail: *"Unexpected non-success status -- treat as a non-retryable API error"* → `raise GameChangerAPIError(...)`. **There is no literal `415` anywhere in `src/`** (confirmed by search), so the classification is by omission, not by decision.
- `src/reports/morning_run.py` — the preflight message *"...connection), not an auth failure"* and the per-team handler *"Transient error (5xx/connection) for team %s; isolating it and..."*
- `src/gamechanger/crawlers/scouting.py` warns-and-skips per game, so the zero-games outcome accumulates quietly.

**The asymmetry that makes this worth fixing:** the **403** path already carries an operator hint naming the Accept version pins (`.claude/rules/auth-module.md` has a whole "False-403 Misdiagnosis Trap" section for exactly this cause). The 415 path — the *same root cause*, a version pin — has wording that points away from it. One sibling of this failure is well-signposted and the other is actively misleading.

## Rough Timing
**Low urgency, and honestly so** — this fires only when a pin goes stale, and the pin inventory was clean when last checked. But a stale pin is precisely the unexpected-day scenario, and that is the day the diagnostic wording matters. Natural carrier: **the next epic touching the HTTP client layer or morning-run reporting.**

## Dependencies & Blockers
- [ ] None.

## Open Questions
- Distinct exception subclass, or a 415 branch that reuses the existing hierarchy? Either separates *"deterministic — fix the request"* from *"transient — retry later"*; nobody has compared them.
- Should the morning-run **summary** wording change too, or only the per-team log line? The summary is what the operator actually reads on a scheduled run.
- Is 415 the only status in this position? The generic tail catches **any** unexpected status, so other deterministic 4xx values may inherit the same mislabel. Worth enumerating rather than assuming 415 is alone.

**⛔ Fix design is OUT OF SCOPE for this capture** — the shape above is a sketch recorded so the option space is not lost, not a chosen design.

## Notes
Source: api-scout's Accept-header pass, 2026-07-26. **Context anchor: nine pinned call sites, zero mismatched** at that inventory — so this is a latent diagnostic-quality problem, not an active outage. The pin inventory itself lives in `docs/api/error-handling.md`'s new section if a durable pointer is needed.

**Three corrections to the finding as relayed, all from checking the cited sites rather than restating them:**

1. **The `morning_run.py` line numbers had drifted by exactly 9** — relayed as `:693` and `:258`, actually **`:702`** (the transient-error handler) and **`:266`** (the preflight). Cite these by message text or symbol, not by line; this file is actively edited and the numbers will rot again.
2. **The count of misleading client docstrings is four, not three** — `Raises:` entries documenting `GameChangerAPIError` as 5xx-only appear at four separate call sites in `client.py`.
3. **One docstring is already correct, and its location is the interesting part.** The entry on the method that actually *contains* the raise reads *"On 5xx after all retries exhausted, **or on any unexpected status**"* — accurate, and it is the only accurate one. So the truth is documented **at** the raise site and lost in every summary that propagated outward from it, including the class docstring and the rule file. That is the more precise statement of the defect than "the docstrings are wrong": the information was never missing, it failed to travel.

Cross-reference for whoever plans a **client/creds hygiene** epic: [[IDEA-193]] and [[IDEA-194]] sit in `src/gamechanger/credential_parser.py` — different files and a different mechanism, but the same family of *"the error path tells the operator something unhelpful or false,"* and all three want the same reviewer's attention. See them together rather than one at a time.

---
Created: 2026-07-26
Last reviewed: 2026-07-26
Review by: 2026-10-24
