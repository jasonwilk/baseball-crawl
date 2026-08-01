# IDEA-233: `epic-archive-check.sh` is inert for modern status lines — a safety gate that has not fired in at least six epics

## Status
`CANDIDATE` — **a silent no-op, not a false pass.** Found during E-279 closure by `cr-e279`; mechanism verified first-hand by product-manager against the hook source.

## Summary

`.claude/hooks/epic-archive-check.sh` exists to stop an epic being committed as `COMPLETED` while its directory still sits in `epics/` rather than `.project/archive/`. **It matches the status with a bare-line pattern** — the status line must consist of the completed marker and nothing else.

**Modern epic files do not write status lines that way.** E-279's own reads:

```
`COMPLETED` — set **2026-08-01** at closure. Previously `ACTIVE` — set 2026-08-01 on dispatch; `READY` — set 2026-07-28 on operator ruling.
```

The marker is there; it is simply not alone on the line. **The gate does not fire, reports nothing, and the commit proceeds.** The house style that produced this — recording the full status history inline, which is genuinely useful — is what defeats it.

## Why It Matters

**The failure mode is the expensive one: a check that RAN is not a check that WORKED.** A gate that never matches produces output shape-identical to a gate that matched and passed — **silence.** Nobody has seen it fail because nobody has seen it do anything.

**Scope, stated honestly in both directions.**

**Against urgency:** no epic has actually been mis-archived. The closure sequence archives the directory by other means (the implement skill's ordered sub-step 3, and now E-279's worktree-side rename), and PM's own closure checklist requires the move. **This gate is a backstop for a failure that has not occurred**, and its inertness has cost nothing measurable.

**For fixing it:** a backstop believed to be live is worse than a known-absent one, because it is silently counted as coverage. It is cited in closure discussion as protection that exists. **And the count is the argument** — it has been inert for **at least six epics** on the current house style, so the belief has been wrong for months.

## Rough Timing

**Not urgent, and a good passenger rather than an errand.** Promote when either fires:

- Anyone is already editing `.claude/hooks/` — marginal cost near zero.
- An epic is ever found archived incorrectly, which would make this a live gap rather than a dormant one.

## Dependencies & Blockers
- [ ] **Owner is claude-architect** — `.claude/hooks/**` is context-layer machinery.
- [ ] **Sequence after any E-271 hook work** if the two would touch the same file, to avoid a needless collision.
- [ ] ⚠️ **Ratchet-aware.** At filing, the context-layer ratchet is FAILING and its disposition is an open operator decision. A fix here should be **line-neutral or negative** — a regex loosening, not a new block — or it inherits that question.

## Open Questions

- **Loosen the pattern, or standardize the status line?** Loosening the regex to find the marker anywhere on the line is smaller and does not ask thirty epic files to change. Standardizing the line would make the gate reliable but discards the inline status history, which is worth keeping. **Loosening is almost certainly right.**
- **Does loosening introduce a false positive?** A status line reading *"Previously `COMPLETED`"* or quoting the word in prose could match a loosened pattern. Worth checking against the archive before shipping — **this is exactly the over-match-arrives-visibly trade, and the visible direction is the safe one.**
- **Was it ever live?** If an older status-line style did match, this is drift rather than a defect at authorship, and the entry should say which. **Not established — do not assert either.**

## Notes

Filed 2026-08-01 by product-manager at E-279 closure, per the epic's own pre-committed capture address (a post-freeze finding goes to the epic History as a closure item, and the idea file is filed at closure rather than mid-freeze).

**The finding's own shape is the reusable part and it is why this is worth a file rather than a shrug:** the gate was surfaced only because someone asked what a passing run would have *looked* like, not whether it had passed. **An unlabelled null result — a check whose failure output is shape-identical to its success output — cannot be caught by reading the output.** E-279 recorded the same class three separate times: a mutation probe whose mutation never applied reporting the same green, a positive control that could not match because its string was line-wrapped, and this.

Related: [[IDEA-231]] (shipped dead epic-directory references — the same closure-hygiene surface, and E-279's `scripts/check_archive_refs.sh` is the gate that DOES fire); [[IDEA-232]] (a gate skipped by an unrelated early exit, the sibling shape one file over).

---
Created: 2026-08-01
Last reviewed: 2026-08-01
Review by: 2026-10-30
