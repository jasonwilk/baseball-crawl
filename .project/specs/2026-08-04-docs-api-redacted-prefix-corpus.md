# `docs/api` `-REDACTED` placeholders use REAL UUID prefixes

**Date:** 2026-08-04 · **Status:** RULED 2026-08-08 — rule RELAXED, scrub CANCELLED. Real team/org/game ID prefixes are acceptable in `-REDACTED` placeholders (operator team-ID policy); PERSON-scoped identifiers (player/user ids) remain synthetic-only. The `api-docs.md` rule edit rides the PII-docs chunk; the measurement below stays as the record
**Related:** `.claude/agent-memory/api-scout/docs-api-pii-corpus.md` (2026-07-06, E-254-07),
which already recorded that `docs/api` embeds real identifiers corpus-wide and that the
denylist cannot certify the tree clean.

## The defect

`.claude/rules/api-docs.md` is explicit:

> The `<prefix>-REDACTED` placeholder form is approved, but the placeholder MUST use a
> SYNTHETIC prefix (e.g. `00000000-REDACTED`) — never a real team's prefix, which would
> re-embed the identifier the redaction is meant to remove.

Much of the corpus violates this. A real 8-char prefix is an identifier; the redaction removes
the *rest* of the UUID and keeps the part that identifies.

## Measured extent (2026-08-04, `docs/api/**/*.md`)

**32 distinct prefixes across 144 occurrences** (re-derived by running the command below; an
earlier revision said "~31 / ~140" and mis-split the synthetic/real counts — the split is the
part that scopes the work, so it is the part worth getting exact).

Only **3** are unambiguously synthetic — the all-repeated-digit forms the rule itself models,
of which `00000000` alone accounts for 44 occurrences. That leaves **29 real-looking**.
A couple of others (e.g. an `abc12345`-style prefix) are probably hand-made but are not
mechanically distinguishable from a real hex prefix, and **deciding which is which IS the
mapping exercise** — so they are counted as real here rather than assumed away.

Distribution: the most frequent single prefix appears **27 times** across multiple files, then
one at **7**, one at **5**, **three** at **4**, and a long tail at 1–3.

**The prefixes are deliberately NOT listed here** — writing them into this file would commit
the identifiers into a second tracked location, which is the defect this spec exists to
describe. `.claude/rules/pii-safety.md` is explicit: *"When authoring `.project/**` or
`epics/**`, never paste real names or identifiers."* Reproduce the full list locally instead:

```
grep -rhoE "[0-9a-fA-F]{8}-REDACTED" docs/api --include="*.md" | sort | uniq -c | sort -rn
```

**The bare-prose form is worse and was fixed in this pass** — an unwrapped prefix sitting in a
sentence (`"the org used for testing (<8-hex>)"`) carries no redaction marker at all, so a
reader does not even register it as an identifier. Three such sites were corrected, in
`get-organizations-org_id-standings.md` and `get-organizations-org_id-events.md`.

## Why it was not remediated here

1. **Scope.** This chunk was org doc corrections. A ~140-site rewrite is a different piece of
   work with a different risk profile.
2. **Blind replacement is unsafe.** Some prefixes recur across files as *consistent*
   identifiers — the most frequent appears 27 times, and `get-teams-team_id-users.md` uses two
   prefixes side by side precisely to say "two different teams." Mapping each real prefix to a
   *stable* synthetic one preserves that meaning; replacing them all with `00000000` destroys
   it. That is a mapping exercise, not a sed.
3. **No scanner catches it**, so it will not regress louder if deferred — but equally, it will
   not surface on its own. It needs a deliberate pass.

## Shape of the fix

Build a real-prefix → synthetic-prefix map (one stable synthetic per distinct real prefix,
preserving cross-file identity), apply it, then re-run the enumeration and require every
surviving prefix to be synthetic. Add the enumeration to whatever doc-PII checking exists so
it cannot silently regrow.

## Known-remaining sites (found by sweep, left in place deliberately)

Named by FILE, not by prefix, for the reason above:

- `get-teams-team_id-public-team-profile-id.md` — 2 placeholder occurrences of one real prefix
- `get-teams-team_id-users.md` — 2 occurrences spanning two distinct real prefixes
- …and the rest of the ~140-occurrence corpus.

These are named rather than silently skipped: leaving a known real prefix in place is a
decision, and it should be visible as one. Run the command above to see which.

## Progress log

- **2026-08-04** — Found while correcting org endpoint docs. Fixed: **three bare-prose sites**
  (`get-organizations-org_id-standings.md` ×1, `get-organizations-org_id-events.md` ×2) plus
  **three** real prefixes inside `-REDACTED` placeholders in
  `get-organizations-org_id-teams.md`. Corpus-wide remediation stubbed, not
  started. api-scout flagged 2 files; a structural sweep found 3 more plus a prefix nobody had
  listed — the sweep is the instrument here, not recall.
- **2026-08-04 (Codex review)** — **This file originally listed the real prefixes in a
  frequency table**, i.e. it committed the identifiers into `.project/specs/` while describing
  why they must not be committed to `docs/api/`. Codex caught it; the listing was replaced with
  counts plus a reproduce-locally command. **Neither gate would have caught this**: the
  pre-commit `pii_scanner` cannot regex-detect identifiers of this class at all (only
  credentials/email/phone), and `check_doc_pii.sh` is scoped to `docs/api/` — and even pointed
  at `.project`, it PASSED, because these particular ids are not in the denylist. Both gates
  returned exit 0 on a file full of real prefixes. Treat that as the standing lesson: on this
  identifier class the gates are not evidence, and only reading is.
