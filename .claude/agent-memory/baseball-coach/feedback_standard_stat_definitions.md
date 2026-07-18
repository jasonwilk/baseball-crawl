---
name: feedback-standard-stat-definitions
description: Operator principle -- never invent a non-standard definition of a recognized stat, even for cleaner internal logic
metadata:
  type: feedback
---

Prefer the standard, widely-recognized definition of a stat over a cleaner-but-invented variant, even when the invented version reads more cleanly on the page.

**Why:** During E-266 (2026-07-17), I ruled that the per-outing XBH column should be **2B+3B only, excluding HR** -- reasoning that HR already has its own column, so an inclusive XBH (the standard 2B+3B+HR definition) would force a coach to mentally subtract HR out of XBH to get the doubles/triples count. The operator overrode this on principle, not on coaching merit: "don't invent new definitions of any stats." Shipped the textbook inclusive XBH (2B+3B+HR) instead, with HR still separately broken out (conventional, if slightly redundant). The report must speak only in recognized definitions -- a coach who knows what XBH means everywhere else in baseball should get that same number here, even if it costs a little "additive cleanliness" on the row.

**How to apply:** When ranking or ruling on stat sets going forward, favor a well-known/textbook stat over an invented rebalancing of it, EVEN IF the invented version is more internally consistent with an adjacent column. This is distinct from picking among several standard stats for a brand-new surface (e.g., [[e265-krate-and-highlight-ruling]]'s K/BF-over-K/G call, which chose between two REAL, already-defined stats) -- that kind of choice is fine. The line is: choosing between existing standard definitions = fine; redefining a standard stat's math to make it fit better next to another column = not fine, flag it but don't ship it without asking. If a genuine redundancy or confusion risk exists (like XBH sitting next to a separate HR column), solve it with labeling/footnote clarity, not by changing the stat's math.
