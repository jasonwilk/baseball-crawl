# E-279-02 completion report — Dispatch-log telemetry deletion

**Author**: `ca-e279` (claude-architect) | **Date**: 2026-08-01

Written as an artifact rather than a message because AC-3 requires a **per-line
verdict table** and AC-4 a specific residue statement — neither survives a message
summary. Story 01 proved the point when the implementer→reviewer message leg
failed twice and this artifact became the delivery mechanism.

**Citations are phrase anchors, not line numbers**, per story 01's five
generations of citation rot. An anchor printed with a trailing `…` is truncated
for display: **cut at the ellipsis and grep the part before it.**

---

## Files Changed — the closed list, pre-registered before any edit

| Path | Change |
|---|---|
| `.claude/hooks/send-message-counter.sh` | **deleted** |
| `.claude/settings.json` | fourth Bash hook object removed; SendMessage block removed |
| `.gitignore` | the whole 55-58 stanza removed |
| `.claude/agent-memory/claude-architect/epic-codifications.md` | two authored verdicts (AC-3) |
| `.project/research/E-279-02-completion-report.md` | this file |

Nothing outside the list was touched **by story 02**. **No test, script or `src/`
file referenced the hook** — measured before starting, so no test change was in
scope.

### ⚠️ Separately: ROUTED REMEDIATION of story 01's artifacts — NOT story 02 scope

**Two further files appear in the staging boundary and are deliberately NOT on the
list above.** They are `cr-codex` findings against **story 01's** artifacts, routed
by the main session under `workflow-discipline.md`'s **post-review remediation
exception**, and authorized by that rather than by story 02's ACs:

| Path | Change | Authority |
|---|---|---|
| `tests/test_worktree_guard.py` | docstring cited `test_ac7_blocks_creation_when_real_root_is_absent`, which exists in no file; re-cited **by behaviour** | routed remediation (story 01) |
| `.project/research/E-279-01-completion-report.md` | `24 passed` / `4367` annotated with the current measured figures; **transcript preserved** | routed remediation (story 01) |

**Why the separation is recorded rather than folded in** (PM's ruling, and it is
the point): story 02's file list was **pre-registered and closed at five, and held
with zero growth** — the one candidate that arose mid-pass (`.dispatch-log/`
artifacts) was reported rather than actioned. **That closed list is the process
change working. Widening it to carry another story's fixes would falsify the very
claim that makes it evidence**, and "no growth" would become false the first time
someone checked it against the diff. **Story 01's DONE stands: PM ruled neither
finding violates any AC** — AC-7 governs directory creation, not docstring
citations, and AC-6b/AC-8 require verdicts *recorded in* the report, not its test
figures kept current.

---

## AC-1 — mechanism removed in all three repo places

| Observable | Result |
|---|---|
| hook file exists | **no** |
| `grep -c send-message-counter .claude/settings.json` | **0** |
| `grep -c dispatch-log .gitignore` | **0** |
| line above the stanza (`!/ephemeral/scratch/.gitkeep`) | unchanged |

**Surviving references, each with its inherited verdict** — the sweep is scoped to
LIVE references by design, and dated historical framing is exempt:

| Site | Verdict |
|---|---|
| `.claude/skills/implement/SKILL.md` — "The failure is not hypothetical…" (E-278 phantom-finding narrative) | **leave alone** — inherited evidence; it anchors a live rule |
| `.project/research/E-271-e267-audit-findings.md` — the P-6 finding row | **leave alone** — inherited evidence |
| `.claude/agent-memory/software-engineer/dispatch-git-gotchas.md` | **out of scope — E-279-05** |
| `.claude/agent-memory/product-manager/archived-epics.md` — E-260 record | **PM's own**, reconciled at closure |
| `.claude/agent-memory/claude-architect/epic-codifications.md` | **mine — authored verdicts below** |

---

## AC-2 — the two removals are NOT symmetric

**Executed, not eyeballed.** `python -c "import json; json.load(...)"` succeeds, and
the resulting matcher/hook map is:

```
matcher=Bash       hooks=['pii-check.sh', 'epic-archive-check.sh', 'secret-read-guard.sh']
matcher=Read       hooks=['secret-read-guard.sh']
matcher=Write      hooks=['worktree-guard.sh']
matcher=Edit       hooks=['worktree-guard.sh']
```

- **Bash block survives with its three siblings** — the PII gate, the
  unarchived-epic gate and the credential guard are all still registered. Only the
  fourth object was removed.
- **SendMessage matcher is gone entirely** (sole occupant) — no `SendMessage` key
  remains in `PreToolUse`.
- `epic-archive-check.sh` specifically confirmed present: **E-279-03's design
  argues the restructure is safe partly because that hook still clears**, so
  removing it would have falsified this epic's own premise with no failing test.

> ⚠️ **One check needed disambiguation rather than a pass/fail read.**
> `grep -c secret-read-guard.sh` returns **2**, not 1 — because it is registered on
> both `Bash` and `Read`. A naive "each sibling must appear once" assertion would
> have flagged a correct file. Resolved by enumerating the parsed structure instead
> of counting strings, which is why the evidence above is the JSON map and not a
> grep tally.

---

## AC-3 — sweep with a WRITTEN VERDICT per surfaced line

Patterns, fixed in advance: `\.dispatch-log`, `sends\.count`, `rides the closure
patch`, `\brounds\b` — case-insensitive ERE, with a known-present control in the
same pass so a zero is interpretable.

**Surface measured before starting: 34 files.** Classification below is the whole
scope; nothing was added to it during the pass.

> **DERIVATION — the exact command every class row below came from, so it can be
> reproduced rather than taken.** Three tokens only; `rounds` is **excluded** here
> and dispositioned separately (see its own section), because folding it in changes
> several rows:
> ```
> grep -rlniE "\.dispatch-log|sends\.count|rides the closure patch" <dir> | wc -l
> ```
> Run per directory, counting **files** (not lines), `.git` never traversed.
> Re-derived 2026-08-01T18:01Z: `.project/archive` **17**, `.project/ideas` **4**,
> `.claude/agent-memory` **5**, `epics` **4**, `.claude/rules` **1** +
> `.claude/skills` **1**, plus `.gitignore` and the hook = **34**.
>
> **⚠️ `cr-e279` measures two of these differently — `epics` 5 and rules+skills 0 —
> and this is recorded as an unreconciled difference, not settled in my favour.**
> On this tree the four `epics/` hits are E-279-02, -03, -05 and `epic.md`;
> **E-279-01's story file carries zero of the three tokens** (measured), which is
> the obvious candidate for a fifth and does not hold. The rules/skills hits are
> `workflow-discipline.md` and `implement/SKILL.md`, both on *"rides the closure
> patch"*, both individually adjudicated above.
>
> **A hypothesis I tested and REFUTED rather than reported:** this repo documents a
> ugrep quirk where BRE alternation over multiple path args returns a silent empty,
> which would have explained a `0` exactly. **It does not reproduce here** — BRE
> over both paths returned 2, same as ERE. So I cannot account for CR's figures,
> and I am not inventing a mechanism that fits.
>
> **Stating the command is the actual repair.** This note exists because a class
> breakdown was eyeballed and never re-derived; **correcting the numbers again
> without publishing the derivation would continue that lineage rather than end
> it** — the `14/14` shape, where the explanation of a counting error is itself an
> unreproducible count.

> **⚠️ The archive row read `19` until 2026-08-01 and is corrected to `17`.**
> `pm-e279` could not reproduce the total from my own class rows — its arithmetic
> was **correct on my inputs** (`19 + 4 + 3 + 10 = 36`); my input was wrong.
> Re-derived independently, per class: **17 archive + 4 epic/story + 4 ideas
> (3 inherited + IDEA-161) + 5 agent-memory + 2 rules/skills + 2 removed = 34.**
>
> **The diagnosis is sharper than "a miscount": the total was MEASURED (`wc -l` on
> real output) and the class breakdown was EYEBALLED off the same screen and never
> re-derived** — so a measured figure and an estimated figure sat in one table,
> **indistinguishable in presentation.** Same shape as the unmeasured timestamp on
> story 01: the artifact carried the marks of derivation for a number that had
> none. Presentation does not distinguish them; only re-derivation does.
>
> **Third count-asserted-rather-than-derived defect on this epic**, after the
> `14/14` and its own explanation. **One recurring form, not three incidents: a
> subsidiary figure that agreed with everything around it and was never produced
> from the thing that would produce it.**
>
> **What it says about property-defined classes**, which is worth separating: the
> property was sound, **no file changed class, and every disposition stands.**
> A property-defined class protects *membership* by construction; **it does not
> protect the COUNT of members.** Those are separable, and the count is the part
> that still needs deriving — the one failure mode the technique is not immune to.

### Bulk classes (pre-declared dispositions)

| Class | Files | Verdict |
|---|---|---|
| `.project/archive/**` | 17 | **no change needed** — archived records of what was true then |
| E-279's own epic + story files | 4 | **no change needed** — this story's own specification |
| `IDEA-230`, `IDEA-116`, `.project/ideas/README.md` | 3 | **no change needed** — inherited verdict; IDEA-230 is the source record of the defect |

### Individually adjudicated lines

**Two classes, and they are not the same thing** *(clarification added 2026-08-01;
held while gates were reading and landed in this batch rather than mid-flight)*:

- **EDITED by me** — files this story changes. Of the judgement set, **exactly
  one**: `.claude/agent-memory/claude-architect/epic-codifications.md` (my own
  memory directory, own-memory carve-out).
- **VERDICT-ONLY** — I surface and disposition; **the owner edits, or nothing
  changes.** Everything else below, including `.project/**` (PM's under TN-5) and
  all `agent-memory/` outside my own. `workflow-discipline.md` and
  `.claude/skills/implement/SKILL.md` sit in the class I am *authorised* to edit
  and both earned "no change needed" — **an authorisation is not a prediction of
  an edit.**

*(`.gitignore`, `settings.json` and the hook file are AC-1 removals, not judgement
sites; they appear below for completeness of the sweep record.)*

| Site (phrase anchor) | Verdict |
|---|---|
| `.gitignore` — "Dispatch send-counter (transient; see…" + "stays TRACKED so it rides the closure patch" + `.dispatch-log/sends.count` | **REMOVED.** The load-bearing case: the comment named the hook by path, so removing only the rule would have left a comment pointing at a deleted file. |
| `.claude/hooks/send-message-counter.sh` (whole file) | **REMOVED.** |
| `epic-codifications.md` — "**SendMessage counter** — `.claude/hooks/send-message-counter.sh`…" | **REWRITTEN as a dated retirement record.** Not preserved: it described the hook in the present tense, carried thresholds (`WARN_AT=15`/`DENY_AT=25`) that were **already stale** before deletion (raised to 40/60 at `dc1cc9e`, deny retired at `c990446`), and asserted the log "rides the closure patch" — **a claim that was never true.** |
| `epic-codifications.md` — "**Hook defect fixed in place**… the `rounds` column has NO producer" | **ANNOTATED AS HISTORY, body preserved.** Its durable lessons — two-tree visibility, and co-locating a value with its provenance — outlive the mechanism and are unaffected by its removal. A dated tombstone marks the hook as deleted; **the evidence itself is not rewritten**, because editing it would falsify what was observed. |
| `.claude/rules/workflow-discipline.md` — "PM authors the COMPLETED flip in the **epic worktree's** `epic.md`… so it rides the closure patch into main" | **NO CHANGE NEEDED.** True and live, about *closure patches in general* and the COMPLETED flip. Nothing to do with the TSV. |
| `.claude/skills/implement/SKILL.md` — "claude-architect's codification… is authored in the **worktree copy**… so it rides the closure patch" | **NO CHANGE NEEDED.** Same shape: a true, live statement about the closure patch mechanism. |
| `.project/ideas/IDEA-161…` — "Does it live in the epic History (operator-visible, rides the closure patch) or a separate trail?" | **NO CHANGE NEEDED.** **This site was NOT in the story's inherited verdict list** — flagged during pre-registration rather than discovered mid-pass. Read in full to check whether its judgement rested on the mechanism: it does not. IDEA-161 concerns a main-session *decision* record and never cites the telemetry hook; the phrase refers to the epic History. |
| `agent-memory/product-manager/archived-epics.md` — E-260 record; and "the CA+docs codification **rides the closure patch**" (E-264 record) | **NO CHANGE NEEDED — and not mine to edit.** The E-264 line is the story's own worked example of a hit whose correct verdict is "no change needed": a true statement about closure patches generally. The E-260 record is PM's, reconciled at closure. |
| `agent-memory/product-manager/e276-health-gate-triage.md` — "Verified by PM reading `.dispatch-log/E-276.tsv` directly"; and the TSV schema row | **NO CHANGE NEEDED — PM's own.** Both are dated evidence of what was read at the time. |
| `agent-memory/product-manager/e277-reclamation-followups.md` — "**'Durable' is not being on disk — it is being inside the artifact that ships.**" | **NO CHANGE NEEDED — PM's own.** A general lesson, **and one this deletion vindicates**: the TSV was on disk for nineteen epics and never shipped. |
| `agent-memory/software-engineer/dispatch-git-gotchas.md` | **OUT OF SCOPE — E-279-05.** |
| `.project/ideas/IDEA-173-send-cap-reset-destroys-its-own-measurement.md` | **LEFT UNTOUCHED — PM-owned (`.project/` under TN-5); ROUTED TO CLOSURE for a moot/close disposition.** Added 2026-08-01 on `cr-e279`'s MUST FIX; **it was missing from this table entirely.** Not a rephrasing of the retired claim — **a whole idea built on the deleted mechanism.** Its thesis (*"clearing the send cap destroys the data that would justify raising it"*), its worked E-272 example, and all four open questions (*"is the log actually meant to accumulate threshold evidence?"*, *"can a reset be made non-destructive?"*) are now **referent-less**: there is no log, no cap, and the `25` threshold it reasons about was raised to 40/60 and then retired. **Verified first-hand: zero of the four sweep tokens, against a control (`send cap`) returning 2 — verified absence, not an unread file.** |

### The `rounds` token, run separately

**966 raw hits repo-wide.** Deliberately not pre-filtered: over-match arrives
visibly, under-match arrives silently. **Essentially all are the English word in
"review rounds"** — the circuit breaker, CR round counts, triage rounds — and are
unrelated to the TSV column. **Verdict: no change needed, as a class.** The only
hits about the *column* are the two `epic-codifications.md` sites above, the TSV
schema line in PM's triage file, and the epic/story text specifying this sweep.

### The token-free pass, bounded as pre-registered

I read **the four judgement files in full** — not the repository — looking for
judgements that rested on the mechanism rather than rephrasings of its claim. This
is the half a grep cannot do: this epic's own E-271 residuals said *"a bash hook"*
and carried **none** of the four tokens. **Result: no token-free judgement form
found in those four files.** The nearest candidate, IDEA-161, was read in full and
ruled no-change on its content rather than on its tokens.

> **⚠️ THE BOUND WAS UNREACHABLE FROM INSIDE ITSELF, and that is a flaw in the
> pre-registration technique rather than in its execution.** `cr-e279` found
> **IDEA-173** — a whole idea built on the deleted mechanism, carrying zero sweep
> tokens. My bounded pass could not have found it, and the reason is structural:
>
> The escape hatch read *"a token-free judgement form found **outside** the four
> judgement files is a STOP-and-ask."* **But the pass was bounded TO those four
> files — so the hatch can only fire if someone outside the bound looks.** It is
> unreachable from within its own scope. The statement I reported (*"no token-free
> judgement form found in those four files"*) was **true, correctly executed, and
> correctly qualified** — and still left the finding unreachable.
>
> **This is a real limit on the pre-registration change, not an argument against
> it.** The bound met PM's test — a third party could rule a fifth file in or out
> from the text alone — and it was still blind to a class it was partly written to
> catch. **Bounding a pass by FILE SET makes it checkable; it also makes it unable
> to discover membership.** A token-free judgement form is, by definition, found by
> reading something you had no token-based reason to open — which no file-set bound
> can authorise in advance.
>
> **What would have worked here is not a wider bound but a different instrument:**
> the finding came from a reviewer reading the *idea corpus* by subject rather than
> by token or by pre-declared file list. Registering *"who reads what by subject"*
> as a second axis, alongside the file set, is the candidate that falls out of this.

---

## AC-4 — the residue that no commit can remove

**`.git/info/exclude:19` still contains `.dispatch-log/` in every existing clone.
No commit made by this story, or any story, removes it. It is a manual per-clone
operator item, left alone deliberately** (epic TN-11 item 3): the file is untracked
and per-clone, so no story could change it verifiably and no reviewer could see the
change. Once nothing creates `.dispatch-log/`, it is inert.

**Executed rather than asserted** — the story's own lesson is that for what git
does with a path, `git check-ignore -v` is the check and reading `.gitignore` is
not:

```
$ git check-ignore -v .dispatch-log/E-279.tsv
/workspaces/baseball-crawl/.git/info/exclude:19:.dispatch-log/   .dispatch-log/E-279.tsv

$ git check-ignore -v .dispatch-log/sends.count
/workspaces/baseball-crawl/.git/info/exclude:19:.dispatch-log/   .dispatch-log/sends.count
```

> **⚠️ A finding that falls out of that command: `sends.count` is STILL excluded
> after I removed the `.gitignore` rule for it.** `exclude:19` covers the entire
> directory, so **the committed `.gitignore` rule is redundant NOW** — removing it
> changes no git behaviour, which is exactly why the deletion is safe.
>
> **⚠️ Corrected 2026-08-01: this note originally claimed the rule "was redundant
> for its whole life." That is NOT derivable, and the one datable fact points the
> other way.** Measured: the `.gitignore` rule was added **2026-07-12**
> (`c16de84`, `feat(E-260)`). `.git/info/exclude` is untracked — `git log` on it
> returns **0 commits**, so it has no history — and its only timestamp is an mtime
> of **2026-07-28 02:56**, *sixteen days later*. **So the exclude line cannot be
> shown to predate the rule**, and the evidence is consistent with the rule having
> been effective for some interval.
>
> **The irony is the transferable part, and it is a different failure from not
> running the command.** This story's own lesson is *"for what git does with a
> path, `git check-ignore -v` is the check."* I ran it, correctly — and it
> establishes a **present-tense** fact, which I then extrapolated across the entire
> past. **The instrument was used correctly and its output over-read.** Dropping
> "for its whole life" costs the argument nothing: the safety conclusion rests on
> the present fact alone.

**Two live artifacts remain in this worktree** — `.dispatch-log/E-279.tsv` and
`.dispatch-log/sends.count`, last written **17:34Z and 17:38Z**. Both are invisible
to `git status` (measured: zero entries), so no commit can carry them.

> **The mechanism is still LIVE in this session and will be until closure.**
> `settings.json` is invoked as `"$CLAUDE_PROJECT_DIR"/.claude/hooks/…`, which
> resolves to the **main checkout** — where the hook file and both registrations
> still exist. This story deletes the worktree copies; they take effect when the
> closure patch reaches main. `sends.count` being modified *after* the worktree
> deletion is direct evidence of this, not a failed deletion.

---

## Test Results — verbatim

```
$ python -m pytest tests/
============================== 4375 passed, 1 warning in 105.74s (0:01:45) ==============================
```

Bound: run from the epic worktree, so it exercises the worktree's own `src/`. It is
not the authoritative closure signal. **No test referenced the deleted hook**
(measured: zero matches across `tests/`, `scripts/`, `src/`), so the suite count is
unchanged from story 01's — which is the expected result for a deletion with no
code coupling, not an absence of coverage.

---

## Branch B

Not implemented, per the operator's DELETE ruling. Its retired criteria (an
existence check before `mkdir -p`; reconciling the `.gitignore`/header claims to
the per-clone reality) remain in the story file as considered-and-declined.
