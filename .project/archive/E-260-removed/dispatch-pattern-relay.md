# Removed text snapshot — .claude/rules/dispatch-pattern.md

- **Source:** `.claude/rules/dispatch-pattern.md`
- **Story:** E-260-01 (Remove the verbatim-relay mandate apparatus)
- **Date:** 2026-07-11
- **Original line ranges (pre-edit):** 19, 21

Two paragraphs deleted. The following "Concurrency under load (advisory)" paragraph (original :23) is retained verbatim.

---

## :19 — substantive-content-relay default (deleted)

During planning, consultation, and multi-agent coordination, **main-session relay is the default channel for substantive content** (expert input, review findings, story handoffs); peer-to-peer SendMessage is reserved for lightweight acknowledgments only. Peer DM delivery has been observed to drop messages silently in prior epics, and main-session relay is the recovery path.

---

## :21 — relay-integrity read-receipt paragraph (deleted)

**Relay integrity (no relay of unread content).** Before relaying review findings -- or any tool-derived claim -- the relayer MUST have read the persisted source to completion; content composed from empty, truncated, or garbled output (the failure taxonomy in `.claude/rules/tool-output-integrity.md`) MUST NOT be relayed. This is peer-checkable: a teammate receiving a relay of findings MAY require the relayer to confirm the read -- e.g., the persisted-file path plus its line count -- before acting on the relayed content. Because the relay actor is the main-session orchestrator (structurally barred from file operations and not hook-gateable on relays), this is a discipline aid plus peer-checkable convention, NOT a deterministic gate -- the same honesty framing as the review skills' read-receipt gate. It is the relay-surface form of the clean-reread-before-defect discipline (`.claude/agent-memory/product-manager/feedback_clean_reread_before_defect.md`).
