---
paths:
  - "**"
---

# Tool Discipline

- A read that disagrees with memory has two causes: the transport garbled it, or the file MOVED under you. Run the differential before naming one — a "modified on disk since you last read it" notice is primary evidence of a move, as is a later `stat -c '%y'`; then ask who else can write this tree. "Garbled" says discard what you read; "moved" says what you read was real.
- Grep finds candidates; only a Read of the exact line confirms. Never rule on an OR-pattern hit, an omitted long matching line, or a match you did not open — you cannot tell which alternative fired.
- An unexpected COUNT is a cross-check trigger, never a finding, in EITHER direction. One hit where you expected two looks exactly like a deletion; two where you expected none look exactly like a defect. Both have been wrong here.
- A clean result counts only with a POSITIVE CONTROL confirmed present in the target FIRST — by Read, not by assumption. A control drawn by eye from rendered prose is the high-risk case: line-wrapping breaks it, and a broken control's empty is shape-identical to a real one.
- Prose you author or RELAY about how code behaves is an unverified claim until you resolve it against the repo. A green suite says nothing about it. A sentence inherited from a spec, a brief, or the prose inside a diff becomes yours the moment you restate it.
- A doc sweep needs three steps, not one: token grep, then synonym expansion (how would someone state this idea WITHOUT my search term?), then a read of the touched sections. A retirement also strands the ratings and adjectives that depended on the claim but share none of its words.
- Never trust a piped pytest exit code. `pytest ... | tail` reports the PIPE's status (≈always 0). Redirect to a file, capture `$?` separately, and read the file for the RC and the pass/fail line.
- An exit code is not a presence test. `git ls-files <path>` exits 0 whether or not the path is tracked; test the OUTPUT (`[ -n "$(git ls-files <path>)" ]`), not the status. Read as one, it reported an untracked file as tracked (2026-08-06, operator-caught).
