---
name: feedback-clean-reread-before-defect
description: Before reporting an AC defect, do one clean re-read of the exact lines; never assert from a garbled or transient read
metadata:
  type: feedback
---

Before reporting any AC failure or code defect during verification, do ONE clean re-read of the exact lines in question and confirm the literal content. Never assert a defect from a garbled, stale, or remembered read — especially when it contradicts a verified implementer report.

**Why:** During E-230 (2026-05-31) I raised THREE self-inflicted false alarms during AC verification, all retracted: (1) AC-6 FAIL citing an "inline TEMPLATES dict" + "no-op `pass` test" — neither existed; the test read real .html files from disk. (2) A "bare prose line / SyntaxError" that was a misread of my own prior tool output. (3) "CONFIRMED 2 contradictions" in E-230-04's remediated SKILL.md (stale "Epic status updated to COMPLETED" bullet + stale "reverts COMPLETED" abandon clause) — both were GONE; the (a)-deferral fix was complete and consistent. Each forced a retraction and risked routing bogus remediation to the implementer. A wrong FAIL is costly: it sends the implementer chasing a phantom and erodes trust in the gate.

**The grep-match trap (case 3, the sharpest lesson):** I built grep patterns that OR'd the OLD text and the NEW text, saw `[Omitted long matching line]`, and read the *match* as confirming the STALE branch — without reading the literal line. A match on an OR-pattern proves the line matched SOMETHING; it says NOTHING about which branch. `[Omitted long matching line]` is not evidence of stale content — it just means the line was long. NEVER rule on a grep match; always Read the literal line and quote the current text.

**How to apply:** When something looks wrong during AC verification, re-Read the specific line range cleanly and quote the actual literal text before writing any FAIL. Never report a defect from a grep match alone — grep finds candidates, Read confirms content. If two of my own reads disagree, the problem is my read, not the file — re-read, don't escalate. Only report a defect I can quote verbatim from a current, clean Read. A verified implementer report (with RC-checked test output) is strong prior evidence — contradicting it requires first-hand confirmation of the literal text, not a hunch and not a grep hit. See [[feedback_fix_real_findings]].