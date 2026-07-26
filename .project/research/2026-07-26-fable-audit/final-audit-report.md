# Fable session audit — final report (2026-07-25)

Durable copy of the report delivered to the operator. Ten subagents (5 destructive-path
code audits by execution, 1 transcript forensics, 4 claim-verification passes) plus
script-first corpus analysis over all 63 prior sessions. Working artifacts in this
scratchpad directory: corpus_summary.jsonl, phase3_analyze.py, git_join.py, plus
per-agent harnesses under audit-*/, recon_audit/, e273/, gen-audit/.

See the conversation's final message for the full text. Headline verdicts:

1. The 2026-07-25 prose is TRUSTWORTHY: ~95 factual claims resolved, 3 FALSE (one file
   path missing `reports/`; two sentences confined to caeb9a3's commit message), the
   rest hold — many verified to the byte from primary transcripts. Commit all six
   frozen files (one numeric fix in IDEA-178/README first).
2. The real emergency is OLD CODE: reconcile-at-load's health gate reads "prior" AFTER
   the same run's upsert (E-267 origin, pre-Opus-5). Executed proof: 9 player lines
   hard-deleted on GC id churn through the real loader; newly-completed games flip the
   game-grain floor. Fires on routine report generation; player-line grain uncapped.
   CLAUDE.md's "the intersection keeps the gate sound" sentence is false as executed.
3. Second live defect: `\bvarsity\b` precedes Legion word patterns → summer "Post 12
   Varsity"-style names take NSAA varsity table → UNDER-rests vs Legion at 46-50/61-70/
   81-90 (81-105 pre-April). Worse than the NRBL shadow (which is inert today).
4. Opus 5 did NOT degrade code quality (E-273 pre-switch vs E-270/E-272 post-switch:
   comparable density; sole CRITICAL predates the switch; false-rationale-prose appears
   in BOTH eras). The "7 of 7 agents reported nothing" was main's own spawn prompts
   omitting SendMessage — zero messages were actually lost; reproduced 8-of-10 in this
   audit session. Sonnet subagents delivered unprompted 2/2 there, 2/4 here; Opus 0/6
   both times.
5. The wandering is real but lives in the open-ended main-session role, not the model
   tier: 25 substantive in-flight errors (not 16; not all one type — half unopened-file,
   half count/denominator), 4 Reads vs 86 Bash greps in 10 hours, a 30-line windowed
   Read behind the retraction-wrong-twice chain, and a violated "don't re-investigate"
   constraint. Committed artifacts stayed clean because subagents+operator caught
   errors pre-commit.
6. Layer growth (320→453KB, +42%/5wk) is time-confounded with the model switch across
   the corpus; the within-session experiment shows narrow briefs healthy under the same
   layer on every model. Don't grow the layer; two defect-cited CLAUDE.md corrections
   now exist (reconcile-gate sentence; relative-db-path rationale, IDEA-165 premise
   refuted by execution).

Fix order: (1) health gate; (2) varsity-shadow; (3) CLAUDE.md false rationales;
(4) E-273 audit-row pin + keep-roots comment; (5) commit frozen files; (6) IDEA-178
display-only overlay per PM triage (audit-corroborated).
