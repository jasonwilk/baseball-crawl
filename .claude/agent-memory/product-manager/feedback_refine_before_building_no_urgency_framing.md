---
name: refine-before-building-no-urgency-framing
description: Operator wants refinement before building and rejects urgency framing derived from code structure; four months of uneventful operation outweighs an inferred fragility
metadata:
  type: feedback
---

Do not attach urgency framing to a finding derived from reading code structure when the operator has direct operating evidence that contradicts it. Record the finding as fact; let the operator set the priority. And do not frame a DRAFT epic as "awaiting a probe result" — that manufactures a promotion path outside the normal plan/refine workflow.

**Why:** On 2026-07-26 I triaged E-174 (GC client-key extractor) and wrote it up as latent high-priority infrastructure: `extract_client_key()` is step 1 of the primary credential bootstrap, the failure would be invisible until a key rotation, so it would surface at the worst moment. Structurally sound, and the operator overrode it: *"We need to actually refine before we build. We shouldn't overengineer. I've been using the system since March with no real breakage."* Four months of continuous use is real evidence about the live system; my reading was an inference about what the code *would* do in a state nobody had entered. The queued api-scout probe was cancelled and the epic note rewritten to drop the urgency and the probe-gated promotion.

**How to apply:** When a triage finding says "this is worse than it looks," check whether the operator has lived experience bearing on it before escalating — and say plainly what we do NOT know rather than asserting a break is waiting. Keep the mechanism in the artifact (it is real and worth recording); drop the urgency. Live-system questions get answered during refinement, when the operator picks the work up, not by dispatching a probe to justify a priority I assigned. Also watch the reverse temptation: "no breakage in four months" is not proof the code is correct either — the honest position is that the live behavior is unknown, which is exactly why it is a refinement step and not a promotion trigger.

Companion to [[feedback_dont_rationalize_weak_assertions]] — same discipline (do not let a plausible-sounding case substitute for evidence), pointed at my own escalation rather than at someone else's assertion. Related: the E-174 entry in [[MEMORY]].
