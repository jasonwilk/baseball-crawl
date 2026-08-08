# Name / Free-Text Matching Gotchas

Detection code in `src/reports/starter_prediction.py` classifies teams from free-text
GameChanger fields (`team_name`, `age_group`). Every miss here fails SILENTLY to a
suppressed card or a wrong rest table -- there is no error, so the tests are the only
thing standing between a bad regex and a wrong pitch-count recommendation.

## `\b` does not fire against an underscore

`_` is a word character, so there is NO word boundary between `high_` and `freshman`:

```
'high_freshman'   \bfreshman\b -> False      <-- GC sends this age_group form live
'high freshman'   \bfreshman\b -> True
'high-freshman'   \bfreshman\b -> True
```

Bit us in E-272: api-scout observed `age_group: "high_freshman"` in the wild, and the
obvious fix ("also scan `age_group` with `_LEVEL_WORD_PATTERNS`") would NOT have worked
-- it preserves the exact failure being fixed. Normalize `_` to a space before matching.

## Plural / suffix forms need `s?`

`\breserve\b` does not match `"Reserves"` for the same boundary reason. Before E-272 a
team named "X Reserves" matched no level word at all, fell through to `unknown`, and
rendered a SUPPRESSED card -- silently, for however long it had been live. Fixed to
`\breserves?\b`.

Whenever adding a level/keyword pattern, ask: plural? hyphenated? underscored? Any of
the three silently misses.

## First-match tables encode a precedence you may not intend

`_LEVEL_WORD_PATTERNS` is first-match, and `\bvarsity\b` sits AHEAD of the legion
patterns. So `"Norfolk Legion Varsity"` resolves the VARSITY branch -- an explicit
"Legion" in the name loses to "Varsity". Today the season signal masks it (summer
varsity -> legion anyway); with season absent it resolves `nsaa_varsity`. When
reordering such a table, diff old-vs-new across real names rather than reasoning about
it (see below).

## Reconstruct the old table to find out what actually changed

When restructuring a matching table, do not trust the spec's description of the blast
radius. Rebuild the OLD table verbatim in a throwaway script and diff old-vs-new over
candidate strings. In E-272 this showed the change was wider than either the story or
the reviewer had scoped -- Freshman and JV were affected, not just the two names cited:

```
Lincoln 14U Reserve   old=nsaa_subvarsity  new=youth_travel   CHANGED
Lincoln 14U Varsity   old=nsaa_varsity     new=youth_travel   CHANGED
Lincoln Reserves      old=unknown          new=nsaa_subvarsity CHANGED
```

## Related

- [[testing-gotchas]] -- the ugrep BRE-alternation silent-empty trap; a grep that
  "finds nothing" in this area is a cross-check trigger, not proof of absence.
