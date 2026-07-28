# A complete enumeration does not protect against mis-weighting REACHABILITY

**The rule:** enumerating every branch of a function correctly, and then rating one of them
unlikely, is a distinct failure from missing the branch — and **re-reading the enumeration
cannot catch it, because the enumeration is right.** Only asking "what INPUT reaches this
branch, and does that input occur in live data?" catches it, and that question has to be
answered by executing or querying, never by judging the input exotic.

**Why (E-278 planning, 2026-07-27 — cost a full reversal to PM).** I enumerated
`_derive_game_date`'s four reachable branches correctly and even flagged branch C
(unresolvable timezone -> `derive_local_date` logs a WARNING and returns the **UTC** date
through its SUCCESS return, not the caller's `or` fallback) as a correction to IDEA-218's
own enumeration. Then I told PM candidate 2 was "effectively excluded" — because I assumed
`US/Central` was a resolvable IANA name. It is not in this image. 24 live rows take that
branch; 9 hold a genuinely wrong `game_date`. **The branch was in my list and I had rated
it exotic.** Concrete case and executed evidence: [[endpoint-parsing-notes]].

**The tell to search for: a branch you labelled `invalid` / `unknown` / `unparseable` /
`malformed`.** That label IS the reachability assumption, smuggled in as a name. Real
systems feed those branches ordinary-looking data — `US/Central` is not malformed, it is a
timezone name a human would write and that GameChanger actually stores.

**Second, independent half — a borrowed magnitude argument.** My reason for dismissing the
branch was "an afternoon start is nowhere near midnight." That is sound for
**zone-versus-zone** comparisons (adjacent US zones differ by 1 hour) and has **zero**
purchase on **local-versus-UTC** (5-6 hours for Central), where every start at or after
~19:00 local crosses the date line. I carried a magnitude argument across to a comparison
between two different quantities without re-checking it. **When you reuse a "too small to
matter" argument, verify it is about the same two quantities as where you first derived it.**

**How to apply.** After enumerating branches: for each, name the concrete input that reaches
it, then go find out whether that input is present — grep the live data, run the resolver,
execute the function. Do not rank branches by how unusual their names sound. Where an
enumeration feeds a verdict, state the reachability evidence per branch alongside the branch,
so a reader can see which branches were *measured* absent versus *assumed* absent.

**Validated, not just self-diagnosed:** de-epicA explicitly preferred this diagnosis to their
own ("asserted a property of the environment without running it"), on the grounds that theirs
was true but generic while this one names a failure mode careful enumeration does not defend
against. Related discipline: [[testing-gotchas]] (a check that RAN is not a check that WORKED).
