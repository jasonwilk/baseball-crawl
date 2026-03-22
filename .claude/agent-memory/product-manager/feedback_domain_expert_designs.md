---
name: Domain expert drives design, PM frames ACs
description: For context-layer epics, CA designs stories; PM frames ACs. Specialist leads design in their domain.
type: feedback
---

When writing stories in a domain expert's territory (context-layer for CA, schema for DE, etc.), wait for the domain expert's design before writing ACs. PM's job is to frame the expert's design into testable acceptance criteria, not to independently design the solution.

**Why:** During E-148-03 expansion, PM wrote the story independently before receiving CA's design. CA's design was materially different (separate ancillary commit vs folding into closure merge, no preflight modification needed, no step resequencing). PM had to fully rewrite the story.

**How to apply:** When the team lead directs "CA will design, you frame ACs" -- wait for the design. Do not draft ACs based on your own analysis of context-layer files. The expert knows the insertion points, interaction effects, and design constraints better than PM does.
