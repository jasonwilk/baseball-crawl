# IDEA-169: Two hand-maintained Accept-header contracts for one public endpoint

## Status
`CANDIDATE`

## Summary
Two callers hit `GET /public/teams/{public_id}` with different `Accept` headers: `generator.py::_fetch_public_team_info` sends the browser-generic `Accept: application/json, text/plain, */*` (via `BROWSER_HEADERS`, `src/http/headers.py`), while `team_resolver.py` pins GameChanger's vendor Accept (`application/vnd.gc.com.public_team_profile+json; version=0.1.0`) plus `gc-app-name: web`. **Provably a no-op today** — the endpoint ignores `Accept` entirely. The case for aligning them is header fidelity and eliminating a duplicated contract, not correctness.

## Why It Matters
This is a housekeeping/fidelity item, and the evidence bounds it tightly in both directions.

**It is NOT a defect.** api-scout's live probe (n=18, 2026-07-25) settled this: `team_season.season` is returned without the vendor Accept, present and non-null on 18/18 teams and discriminating (17 `"summer"`, 1 `"spring"`). Paired bare-vs-vendor requests across 3 teams produced identical content-length and zero field diffs; the one apparent difference was attributed by a bare-vs-bare control to `avatar_url` CloudFront re-signing, i.e. request churn rather than header effect. The server corroborates: `content-type` stays plain JSON under both variants and `Vary` lists `Origin,Accept-Encoding` — **not** `Accept`. E-272's season signal works on the live path exactly as written.

**The case FOR aligning:** `.claude/rules/http-discipline.md` asks that requests present as a normal browser client would, and one endpoint with two hand-maintained header contracts is a drift surface — a future change to one caller silently diverges from the other. SE's proposed shape is to promote `_ACCEPT_HEADER` to a shared constant both callers import, which removes the duplication without deciding which variant is "right".

**api-scout's caveat, worth recording because it cuts against the obvious framing:** do NOT sell the vendor Accept as a robustness win. If GC ever began enforcing `version=0.1.0` and later retired it, a caller pinning that version would fail **silently** under the current error handling (see the sibling idea on `_fetch_public_team_info` swallowing failures). Pinning a version you do not control is not automatically safer than not pinning it.

## Rough Timing
Low priority. api-scout explicitly recommended NOT doing this as E-272 work. Natural candidates:
- Fold into a housekeeping epic (the E-262 Post-Program Housekeeping pattern is the precedent).
- Do it opportunistically if either caller is being edited for another reason.
- Promote sooner only if a third caller of this endpoint appears — that is the point where two hand-maintained copies becomes three.

## Dependencies & Blockers
- [ ] None. Fully unblocked; it is a small refactor with a settled evidence base.

## Open Questions
- Which direction should the shared constant take — the vendor Accept, or the browser-generic one? The probe says the endpoint does not care, so this is a fidelity judgment, not a technical one. api-scout's caveat argues against reflexively choosing the vendor pin.
- Does the same duplication exist for other GC endpoints with multiple callers, or is this the only one? Worth a quick sweep before doing a one-off fix.
- Should `src/http/headers.py` own per-endpoint Accept variants at all, or does that belong with each endpoint's client code?

## Notes
Surfaced as Codex P1 during E-272's Phase 4 review and **DISMISSED as a defect** on api-scout's live-probe evidence — recorded here so the refutation is not lost and the finding is not re-raised from static reading alone. The dismissal is evidence-based, not a judgment call.

The reason it was raised at all is worth keeping: E-272 changed the CONSEQUENCE of a silent failure in `_fetch_public_team_info` from a missing display field to a wrong pitch-count rest table, because the season signal now feeds league classification. That escalation is real even though this particular header concern turned out to be a no-op — and it is the actual subject of the sibling idea about that function's error handling, which api-scout considers materially more important than the header.

---
Created: 2026-07-25
Last reviewed: 2026-07-25
Review by: 2026-10-23
