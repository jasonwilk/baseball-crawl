---
paths:
  - "**"
---

# Operator Comms

The operator has not been following your investigation. Every operator-facing message — prose,
plan text, question options — is written for someone arriving cold. Ruled at audit 5 (2026-08-16)
from a measured exhibit: a question whose load-bearing news ("a safety check I promised you tests
nothing") was buried inside an instrument reading, next to its six-line plain rewrite.

- Lead with the finding or the decision, in sentence one. Never open with an instrument reading.
- Name the decision the operator can actually make — usually a risk trade — in their vocabulary,
  not the investigation's.
- Define every session-internal label on first use, or drop it. Labels from the operator's own
  kickoff or the spec are fair; your own shorthand (mutant letters, bucket codes) is not.
- Send no message that carries no finding, decision, or question. Progress narration between
  tool calls is noise on the operator's screen.
- Numbers quoted to the operator are PASTED from tool output, never retyped from memory — two
  measured incidents of a correct measurement garbled in restatement ("all 6 are X" over a 3+3
  output; a five-number list not reproducible from any output).
- First mention of any subsystem or mechanism in an operator-facing message gets a one-clause
  plain gloss — "the reaper (the janitor that cleans up stuck report generations)", "a race
  (two parts of the program touching the same thing, outcome decided by milliseconds)". The
  operator ruled this in after decoding "reaper race" cold (2026-08-22); defining your own
  labels is not enough when the subject itself is jargon.
- A question box must survive ALONE on the operator's screen: restate the premise inside the
  question in product language (two sentences max), state the decision as the trade it is, and
  keep implementation detail below the options or in the spec. A question that depends on a
  briefing message three bubbles up has already failed (measured: the divergence-bound and
  guard-no-op exhibits, both of which the operator could not answer unaided).
