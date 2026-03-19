---
name: Fix all valid findings, never dismiss based on size
description: Valid code review findings must be fixed regardless of size/cosmetic nature -- only invalid findings (false positives) can be dismissed
type: feedback
---

All valid code review findings (MUST FIX and SHOULD FIX) must be fixed, regardless of size or cosmetic nature. The team still judges whether a finding is valid (correct analysis) or invalid (false positive, misunderstanding, targets untouched code). What's eliminated is the "correct but not worth fixing" category.

**Why:** Jason said "I can't understand why...if you see something real...you don't want to fix it." The previous triage model allowed dismissing valid SHOULD FIX findings with user confirmation based on size or effort. That felt like cutting corners.

**How to apply:** When designing review/triage workflows:
- Valid finding → fix it, always. Size and cosmetic nature are not dismissal grounds.
- Invalid finding → dismiss with explanation. No user confirmation needed.
- The team's judgment on correctness is preserved. "Is this finding right?" is still a valid question. "Is it worth fixing?" is not.
- Implemented in E-137 (triage simplification TN-6) and inherited by E-138 (full pipeline).
