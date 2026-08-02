# E-280-08 — gate-retirement sweep, per-site verdicts, and the global verifications

Deliverable for AC-6 (regenerated superset of TN-15's floor, written verdict per site),
AC-5/AC-11/AC-13 (global verifications), and the TN-7 reading. Review base:
`eba9a2e994675da4866f81bd49c6f5690ceb9b63`. **Enumerated and reported before the first edit.**

---

## AC-6 — 14 sites, 10 changed, 4 `no change needed`

**Surfacing is not ruling: every site below carries a written verdict, `no change needed` included.**

### `.claude/rules/context-layer-assessment.md` — 8 sites

| # | Site | Verdict |
|---|---|---|
| 1 | Assessment Triggers header, *"All eight verdicts are recorded"* | **CHANGED** — cardinal count (AC-11); now *"Every verdict is recorded"* |
| 2 | **Trigger 7**, the gate itself | **CHANGED** — AC-10a/5/10; see below |
| 3 | **Trigger 8** condition (b) | **CHANGED** — AC-12 re-pricing; see below |
| 4 | Assessment Procedure step 1, *"each of the eight triggers above"* | **CHANGED** — cardinal count (AC-11) |
| 5 | Procedure step 3, *"Triggers 7 and 8 additionally invoke"* | **`no change needed`** — **ordinal**, which AC-11 requires to survive |
| 6 | Learning-Loop opener, *"Triggers 7 and 8 make the context layer prune…"* | **CHANGED** — the retired-claim site TN-15 named; carries no gate token, so no token sweep reaches it |
| 7 | *"Promotion under trigger 8 means…"* | **`no change needed`** — ordinal |
| 8 | `### Cadence and the ratchet` | **CHANGED** — the strongest surviving gate sentence; now the Cadence section |

### `.claude/rules/context-layer-guard.md` — 2 sites, both AC-7

| # | Site | Verdict |
|---|---|---|
| 9 | `## CLAUDE.md Scope` closer, *"the four context-layer subtrees are bounded by the ratchet"* | **CHANGED** |
| 10 | `## MEMORY.md Scope`, *"priced by the ratchet baseline -- there is no separate unenforced line target"* | **CHANGED** |

### Ruled OUT of scope, with the reason — 4

| # | Site | Verdict |
|---|---|---|
| 11 | `implement/SKILL.md`, 5 lines | **`no change needed`** — reconcile-scoreboard instrument, retired 2026-07-26. AC-13 protects. |
| 12 | **`CLAUDE.md`**, *"the one-way ratchet against a committed baseline was retired 2026-07-26"* | **`no change needed`** — same instrument; a correct historical statement |
| 13 | **`.claude/rules/canonical-seams.md`**, *"the ratchet's baseline-ownership rule; it retired with the gate on 2026-07-26"* | **`no change needed`** — same instrument |
| 14 | `.claude/rules/agent-routing.md`, Fable model escalation | **`no change needed`** — states *when to use* Fable, **no cadence**, so AC-1 is safe. Recorded because it is the nearest neighbour a future editor would duplicate the cadence into. |

⚠️ **Sites 12 and 13 are NOT in TN-15's floor.** A regenerated search that returned exactly the floor
would not have searched; these two are the evidence it did. Both resolve to `no change needed`, which
is a **successful sweep, not a wasted one**.

---

## AC-11 — the instrument, and why its zero is interpretable

**Seeds were written from the CLASS before any regex existed** (story Status item 1; E-280-07's first
negative control was circular for exactly the opposite reason). Four seeds, two of them deliberately
carrying **no `trigger` adjacency**:

> S2 *"Record a verdict for each of the eight."* S4 *"There are eight of them and every one needs a verdict."*

| Pattern | Result on the 4 independent seeds |
|---|---|
| adjacency pattern (`(eight\|8)…trigger`) — **the one I would naturally have written** | **2 of 4 — BLIND to S2 and S4** |
| bare cardinal, over-match then resolve by reading | **4 of 4** |

So the sweep used the bare cardinal: **under-match is silent, over-match is visible.** Every hit was
resolved by reading the enclosing sentence, not by the match.

**Result, stated as a result (Status item 6).** Cardinal `eight` across `CLAUDE.md`, `.claude/rules/`,
`.claude/skills/`, `.claude/agents/`: **ZERO**. Five ordinal references survive in
`context-layer-assessment.md` and were **deliberately preserved** — stripping them would destroy the
file's navigability, which is the cardinal-versus-ordinal distinction AC-11 states.

**The other three count sites are already gone** — `implement/SKILL.md` (E-280-02),
`product-manager.md` (E-280-04), `workflow-discipline.md` (E-280-07). **No fourth site survived and no
owner missed theirs.** A count restated in four places went wrong in four places at once; that class
of future defect is now removed rather than corrected.

---

## AC-13 — tested against the FINISHED EPIC DIFF, not a remembered state

```
git diff $(git merge-base epic/E-280 main) -- .claude/skills/implement/SKILL.md | grep -E '^[+-].*[Rr]atchet'
```
**Zero matching lines.** Positive control in the same command: that file's epic diff is **177
insertions / 41 deletions**, so the diff is real and the zero is absence rather than an empty diff.

⚠️ **CORRECTION TO AC-13's OWN FIGURE, recorded here because a correction that lives only in a
completion report has not landed (Status item 7).** AC-13 says *"All **FIVE** `ratchet` occurrences."*
The true figures are **five LINES and SIX OCCURRENCES** — line 644 carries two (*"was RETIRED
2026-07-26 with the ratchet"* … *"the one-way ratchet against a baseline"*). PM's verified "still
five" is correct about **sites**. **This changes no verdict** — byte-identity holds for both figures —
but a wrong cardinal inside the story that retires wrong cardinals is worth the two lines.

## AC-10 — the instrument survives untouched

`md5sum` identical before and after (`00a28f09…` / `42a05027…`), and both files are **absent from the
epic diff**. Retiring a gate is not deleting an instrument.

---

## AC-9a — the reading this story was implemented under

AC-1a mandates **three** closures and AC-8 mandates **five**, both operator-ruled with no latitude, so
**AC-9a cannot mean one interval.** The reading applied: of the three replaced cadences, **two vanish
entirely** — the per-epic size gate and the per-epic audit expectation — and only the batched audit
survives *as a schedule*, stated as one clause of the same section, counted in the same unit, checked
the same way. **One mechanism, one section, two work-proportional multiples.** Not RED, because only
one of the three remains a separately-satisfiable obligation.

## AC-2 — a heading RENAME, flagged not assumed

`### Cadence and the ratchet` → `### Cadence`, because the old title pointed at a retired gate. The
epic diff for these two files contains **exactly one heading line each way** — the rename. **No
net-new heading and no new file**, which is what AC-2's RED enumerates. Flagged to the orchestrator
before the edit rather than resolved silently.

---

## TN-7 — the measurement, and the ledger, both stated

**Bytes rose.** `context-layer-assessment.md` 10,678 → 11,922 B; `context-layer-guard.md` 4,204 →
4,589 B. **Net +1,629 bytes, +4 lines.** Reported as observed; **no byte figure here is a criterion**,
and the size gate is retired, so nothing fails on this reading.

**The per-fact ledger, which is TN-7's actual instrument.** What a reader must now satisfy:

| Removed | Added |
|---|---|
| per-epic size gate: offset-to-baseline **or** an operator-signed exception | — |
| per-epic audit expectation | batched audit, one clause of the pass |
| trigger 8's baseline-arithmetic condition (b) | (b) reviewed at the pass |
| 2 cardinal count restatements (5 across the epic) | — |
| 2 false-after-retirement justifications in `context-layer-guard.md` | — |

**Three recurring per-epic obligations become one scheduled pass with one nested clause.** The bytes
rose because AC-7 required each surviving paragraph to state **what actually disciplines the thing it
is about** — where before it discharged that duty by pointing at the gate in four words. **A pointer
to a retired mechanism is cheap and false; naming the live discipline costs bytes and is true.**
