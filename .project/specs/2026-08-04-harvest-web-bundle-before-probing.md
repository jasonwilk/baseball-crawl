# Harvest the web bundle before guess-probing an API surface

**Date:** 2026-08-04 · **Status:** STUB — a method note; adopt or discard, do not half-adopt
**Source:** org probe 2026-08-04. Evidence:
`.claude/agent-memory/api-scout/organization-scope.md`.

## The observation

Probing `/organizations/…` by guessing path names cost ~450 calls. The web app's own JS bundle
lists **24 `/organizations/…` API templates** outright, including **9 that were never guessed**:
`/internal-id`, `/brand-settings`, `/widgets`, `/leaderboards/stats`, `/leaderboards/stats/export`,
three `/events/bulk/*` forms, and `/game-summaries/{event_id}`.

*(An earlier revision said "8" and then listed 9 — the source report used a brace shorthand
that collapses two of these, and expanding it moved the count. Trust the enumeration, not the
headline; that is this note's own lesson applied to itself.)*

The bundle also yielded two **closed client-side enums** that sampling had gotten wrong:
`OrganizationType = ["league","tournament","travel"]`, and `OrganizationTeamStatus` with **six**
values where only two had ever been observed live.

## ⚠ The bound that makes this a method and not a shortcut

**Neither source is complete.** The bundle **omits four templates that demonstrably work** —
`/opponents`, `/opponent-players`, `/users`, `/pitch-count-report`. So:

- Bundle-first is **cheaper**, not sufficient. It cannot replace probing.
- A path's **absence** from the bundle is **not** evidence the endpoint does not exist. Four
  counterexamples, already in hand.
- An enum read from source **is** better evidence than an enum read from a sample — that half
  is a genuine upgrade, and it is the part most worth keeping.

## Why this is worth writing down

The failure it prevents is not "wasted calls" — it is **a confident negative**. A guess-probing
sweep that misses `/internal-id` concludes the surface lacks a public_id→UUID bridge, and
nothing ever contradicts that. Silent capability loss, the same shape as the
`/teams/{id}/opponents` "likely 403" claim that stood for months and turned out to be
completely ungated.

## Shape

Before probing a new GC surface: fetch the app bundle and its lazy chunks, extract API path
templates and any client-side enums, then probe **the union** of bundle paths and guesses —
and record which source produced each finding, so a later reader knows what a gap means.

Caveat from the same session: the bundle carried **zero router path literals**, so it answers
"what API paths exist" but did **not** answer "what web UI URL renders this" — that question
stayed unresolved.

## Progress log

- **2026-08-04** — Noted during the org probe. Not adopted; no rule or skill changed. If
  adopted it belongs with api-scout's measurement discipline, not in a per-endpoint doc.
