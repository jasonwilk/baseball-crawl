# E-079-03: Update CLAUDE.md proxy documentation

## Epic
[E-079: Fix Bright Data Proxy Routing](epic.md)

## Status
`TODO`

## Description
After this story is complete, CLAUDE.md accurately documents both proxy systems (mitmproxy for traffic capture, Bright Data for IP anonymization), the `bb proxy check` command, and the environment variables that control Bright Data proxy routing. The current "Proxy Boundary" section only covers mitmproxy -- it needs restructuring to distinguish the two proxy systems.

## Context
E-046 added Bright Data proxy support but the CLAUDE.md documentation was not updated to distinguish it from the mitmproxy traffic capture system. With E-079-01 fixing the routing and E-079-02 adding `bb proxy check`, the documentation needs to accurately reflect the full proxy landscape.

## Acceptance Criteria
- [ ] **AC-1**: The CLAUDE.md "Proxy Boundary" section is restructured into two clearly labeled subsections: one for mitmproxy (traffic capture, Mac host only) and one for Bright Data (IP anonymization, env var controlled, used by GameChangerClient).
- [ ] **AC-2**: The Bright Data subsection documents the three env vars (`PROXY_ENABLED`, `PROXY_URL_WEB`, `PROXY_URL_MOBILE`) with brief descriptions of each. Notes that `PROXY_URL_*` values contain embedded credentials (username:password) and are treated as secrets (same handling as tokens -- never log, commit, or display).
- [ ] **AC-3**: The Bright Data subsection notes that SSL verification is automatically disabled when proxy is configured, with the reason (Bright Data uses a self-signed certificate in the CONNECT tunnel), so agents do not treat `verify=False` as a generic pattern.
- [ ] **AC-4**: The CLAUDE.md Commands section includes `bb proxy check` with a brief description consistent with the existing command entry format.
- [ ] **AC-5**: The existing mitmproxy documentation in the Proxy Boundary section remains accurate and complete -- only the structure changes, not the mitmproxy content.
- [ ] **AC-6**: No other CLAUDE.md sections are modified beyond Proxy Boundary and Commands.

## Technical Approach
This is a documentation restructuring task. The existing "Proxy Boundary (Host vs. Container)" section content about mitmproxy is preserved but moved under a clear "mitmproxy (Traffic Capture)" subheading. A new "Bright Data (IP Anonymization)" subheading is added alongside it. The Commands section gets one new entry.

Relevant context:
- `/workspaces/baseball-crawl/CLAUDE.md` -- current Proxy Boundary section (mitmproxy only), Commands section
- `/workspaces/baseball-crawl/epics/E-079-fix-proxy-routing/epic.md` -- Technical Notes, Context-Layer Updates subsection

## Dependencies
- **Blocked by**: E-079-01 (documents the fixed behavior), E-079-02 (documents the new command)
- **Blocks**: None

## Files to Create or Modify
- `CLAUDE.md` -- restructure Proxy Boundary section, add bb proxy check to Commands

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] CLAUDE.md changes are clear, accurate, and consistent with existing section formatting

## Notes
- The `src/cli/proxy.py` module docstring update is handled in E-079-02 (AC-9), not this story.
