# Handoff-session evaluation protocol (P1-P5)

## E. Cost per deliverable (transcript bytes as token PROXY — not billed tokens,
## no cache accounting; same proxy the corpus audit used)

Baselines (dispatch epics, session+subagent transcript MB / landed insertions):
  E-245 7.6MB/4058ins = 1.9 KB/ins   E-261 8.2/3710 = 2.2   E-252 11.1/3372 = 3.3
  E-270 13.3/3469 = 3.8 (Opus 5)     E-255 12.4/2824 = 4.4
  E-272 18.3/2171 = 8.4* (*contaminated: session also ran E-274 discovery;
  insertions counted for E-272 only — treat as upper bound, not a data point)
DISPATCH BAND: ~2.0-4.5 KB transcript per landed insertion.

P1 measurement at close (one command; corpus_scan.py handles a single session too):
  1. total MB = main jsonl + all subagents for P1's session id(s).
  2. landed insertions = numstat sum over P1's commits.
  3. KB/ins vs band. Above ~6 needs a decomposition before judgment:
     pre-pivot vs post-pivot bytes (the abandoned path's cost), convergence-round
     bytes (SE/DE gate debate), review/remediation bytes. A number above band that
     decomposes into NECESSARY discovery (executed counterexamples that changed the
     design) reads differently from one that decomposes into re-litigation.
  4. Report the number WITH its densest consumer (which agent burned the most).
Same measurement applies to P2/P3 sub-lead runs — plus MY inbound bytes as a
separate line (the experiment's whole point is keeping that near zero).

Wall clock (report BOTH; span alone is misleading — it counts operator idle):
  span = last-first event timestamp; ACTIVE = inter-event gaps <10min summed across
  main+subagent transcripts (gaps >=10min treated as idle/waiting).
Baselines: E-245 2.3h span/2.3h active; E-261 3.9/2.4; E-270 4.8/3.6 (Opus 5);
  E-252 9.2/3.3; E-255 23.8/3.6 (span dominated by an overnight pause);
  E-272 12.3/4.4 (contaminated, includes E-274 discovery).
DISPATCH BAND: ~2.5-4h ACTIVE per epic. Judge P1 on active hours + the same
pivot decomposition as bytes; span only matters if the OPERATOR was blocked
waiting (that's a real cost of the serial-handoff model worth noting for the
sub-lead experiment, where I absorb the waiting instead).

When the operator reports a handoff thread done, evaluate on four axes. Spawn one
cheap verifier per landing; the navigator thread reads conclusions only.

## A. Deliverable verification (per prompt, mechanical)
- P1: re-run the audit's failing inputs against the new code (harness at
  scratchpad/recon_audit/): id-churn 9v9 must REFUSE with 0 deletions; game-grain
  newly-completed padding must REFUSE. ALSO verify the positive direction AGAINST THE
  SHIPPED SPEC (conjunction semantics chosen 2026-07-25, settled by execution): a
  legitimate retirement that today's gate PERMITS must still retire; shapes today's
  gate refuses (e.g. the 10-rostered/2-dropped/20-nonroster roster shape) legitimately
  STAY refused under the conjunction — do NOT flag that as a defect, it was never
  chartered. Verify the team's own three fixture claims: 9 player-line / 2 game /
  2 roster wrongful deletions all blocked, and conjunction provably a no-op on the
  player-line grain. FIXTURE-RANGE CHECK (added after CR-2's catch): any sweep or
  parametrized fixture cited as safety evidence must COVER PRODUCTION SIZES —
  seasons run 20-30 games, rosters 12-15; a zero-failure sweep over 0-12 per
  parameter is under-coverage dressed as strength. Verify ranges, not counts.
  Check prose: reconcile_at_load.py:596-603 /
  :962-968 comments and the CLAUDE.md KNOWN DEFECT paragraph replaced (not merely
  appended to). 72 prior reconcile tests green. E-270-03 e2e pollution audited or
  explicitly declined. Note which gate semantics shipped (documented-restoration vs
  conjunction vs other) — feed into the hiccup ledger's item 3 regardless of verdict.
- P2: coach ruling recorded BEFORE the ordering change; before/after table for the
  three shadow names; LEGION==NRBL tripwire test exists and discriminates (mutate one
  constant → fails); ground-truth fixture pack present and green.
- P3: MAJOR-1 decision explicit (pin vs document, not silence); in_transaction
  fail-fast present in both public passes; migration-005 comment consistent with the
  chosen behavior.
- P4: deletion list was presented to operator BEFORE execution; net-negative diff;
  MEMORY.md indexes consistent with surviving files.
- P5: gate removal complete per doc-sweep (semantic sweep, not token grep — closure
  skills + PM memory carry ratchet procedure without the word "ratchet");
  self_games==0 still enforced somewhere named; CLAUDE.md block actually shrank.

## B. Prompt adherence (did the thread do what the prompt said)
Checklist per prompt: epic number obtained by glob; scope stayed tight (nothing rode
along); gates honored (P2 coach ruling first); fail-first test discipline (P1: tests
demonstrably red against pre-fix code); report-back format delivered.

## C. Steering burden (the operator's own cost)
Run steering_scan.py (this dir) pointed at the handoff session's transcript once known:
genuine-operator corrections/redirects + self-corr per 100 turns. Compare: dispatch
baseline is ~1/5 burden, selfcorr ≈ 0-0.2/100. Elevated numbers in a BOUNDED dispatch
= new signal (the 07-25 elevation was confined to open-mandate work).

## D. Hiccup classification → context-refinement routing
For every deviation, name ONE cause:
- PROMPT (my prompt ambiguous/wrong → fix prompt style for later handoffs)
- LAYER (a rule/CLAUDE.md passage caused a detour or contradiction → defect-cited
  layer refinement candidate; the freeze allows these)
- MODEL (hub asserted-without-reading, self-corr churn → evidence for the
  all-modes no-self-verify extension)
- HARNESS (delivery/idle/relay artifacts → spawn-prompt conventions)
Uncategorized hiccups get investigated, not binned.

Known context state these sessions run under: CLAUDE.md carries the KNOWN DEFECT
reconcile note (b106b79) which P1 itself must replace — its presence is intentional;
a P1 thread confused by it is a PROMPT/LAYER data point, not a surprise.
