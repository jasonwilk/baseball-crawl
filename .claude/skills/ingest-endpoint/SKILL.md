# Skill: ingest-endpoint

**Category**: Workflow Automation
**Adapted for**: baseball-crawl

---

## Activation Triggers

Load this skill when the user says any of:

- "ingest endpoint", "ingest the endpoint", "ingest-endpoint"
- "I put a curl in the secrets file", "new curl ready", "curl is updated"
- "document this endpoint", "new endpoint to analyze"
- Any request that implies a fresh GameChanger API curl command is waiting in `secrets/gamechanger-curl.txt`

---

## Purpose

Automate the two-phase workflow for ingesting a GameChanger API endpoint from a browser traffic capture. The user captures a curl command from browser DevTools, saves it to `secrets/gamechanger-curl.txt`, and invokes this skill. The skill orchestrates api-scout (time-sensitive endpoint execution and documentation) followed by claude-architect (context layer integration).

This replaces a manual multi-step process that was performed for the season-stats and game-summaries endpoints.

---

## Prerequisites

Before executing this workflow, verify:

1. **`secrets/gamechanger-curl.txt` exists and is non-empty.** Read the file to confirm. If missing or empty, ask the user to provide the curl command.
2. **The curl command contains a valid URL.** Parse the URL to identify the endpoint path. Do NOT display or echo the `gc-token` or `gc-device-id` header values -- these are sensitive credentials.
3. **Credentials are time-sensitive.** GameChanger tokens expire within approximately 1 hour. Phase 1 (api-scout) must execute the curl promptly. Do not delay with extensive planning.

---

## Phase 1: API Scout -- Endpoint Execution and Documentation

**Agent**: api-scout (direct-routing exception -- no PM intermediation needed)
**Time-sensitive**: Yes -- credentials expire within ~1 hour

Spawn api-scout with the following instructions. Include the full curl file path and the endpoint URL (redacted) in the prompt.

### Instructions for api-scout

```
Read the curl command from `secrets/gamechanger-curl.txt`. This contains a live GameChanger API
call captured from browser traffic. Credentials are short-lived (~1 hour), so execute promptly.

SECURITY: NEVER display, log, or include gc-token or gc-device-id values in any output or file.

Execute the following steps in order:

1. PARSE the curl command:
   - Identify the endpoint URL, HTTP method, all headers, and any query parameters.
   - Note the endpoint path (e.g., /teams/{team_id}/season-stats).
   - Identify the Accept header value and gc-user-action value.
   - REDACT all credential values (gc-token, gc-device-id) in any notes or output.

2. EXECUTE the curl command:
   - Run it via Bash.
   - If the response is an HTTP error (401, 403), report that credentials have likely expired
     and stop -- ask the user to refresh the curl capture.
   - If successful, save the response body to `data/raw/` with a descriptive filename based
     on the endpoint (e.g., `season-stats-sample.json`, `game-summaries-sample.json`).
     If a file with that name already exists, overwrite it with the fresh data.

3. VERIFY credential safety:
   - Inspect the saved response file to confirm no gc-token or gc-device-id values leaked
     into the response body.
   - If credentials appear in the response, strip them immediately and re-save.

4. DOCUMENT the endpoint in `docs/gamechanger-api.md`:

   a. CHECK if this endpoint is already documented in the API spec.

   b. If ALREADY DOCUMENTED:
      - Compare the fresh response against the existing schema documentation.
      - Extend the schema with any new fields not previously documented.
      - Correct any fields whose types or descriptions do not match the fresh response.
      - Update the discovery/verification date.
      - Add a changelog entry noting what was validated or updated.

   c. If NEW endpoint:
      - Add a complete endpoint section following the existing format in the spec:
        URL pattern, HTTP method, required headers (with {PLACEHOLDER} for credentials),
        query parameters, response schema with types and descriptions, example response
        (redacted), known limitations, discovery date.
      - Add the endpoint to the Table of Contents.
      - Add a Response Schema section if the response is complex.

   d. For ALL endpoints (new or existing):
      - Document any URL query parameters observed in the curl command.
      - Update the Accept headers table (Header Quick Reference section) if a new
        Accept header value is observed.
      - Update the gc-user-action table if a new action value is observed.
      - Document pagination behavior if pagination headers are present
        (x-pagination request header, x-next-page response header).

5. CHECK research spike relevance:
   - Read `epics/E-002-data-ingestion/E-002-R-01.md` (if it exists).
   - If this endpoint discovery answers any open research questions or unblocks any
     stories mentioned in the findings, note the specific impact.

6. SUMMARIZE findings:
   - Endpoint path and HTTP method
   - Whether this was a new or existing endpoint
   - Key fields and their types (high-level, not exhaustive)
   - Any coaching-relevant stats or data discovered
   - Any research questions answered or stories unblocked
   - Any follow-up explorations suggested by the response
```

### What to do with api-scout results

When api-scout completes, review the summary. If api-scout reports expired credentials (401/403), relay this to the user and stop the workflow -- do not proceed to Phase 2.

---

## Phase 2: Claude Architect -- Context Layer Integration

**Agent**: claude-architect (direct-routing exception -- no PM intermediation needed)
**Time-sensitive**: No -- this phase can proceed after api-scout regardless of credential expiry

Spawn claude-architect with the api-scout findings summary and the following instructions.

### Instructions for claude-architect

```
The api-scout just completed an endpoint ingestion. Review the findings and determine whether
any context-layer updates are needed.

[Include the api-scout findings summary here]

Check each of the following areas and update if the findings warrant it:

1. AGENT MEMORY -- Check whether any agent memory files need updates:
   - `.claude/agent-memory/api-scout/MEMORY.md` -- new endpoint in exploration status table,
     key facts, areas not yet explored
   - `.claude/agent-memory/data-engineer/MEMORY.md` -- if new schema-relevant fields discovered
   - `.claude/agent-memory/general-dev/MEMORY.md` -- if new implementation-relevant details
   - `.claude/agent-memory/baseball-coach/MEMORY.md` -- if new coaching-relevant stats discovered

2. AGENT DEFINITIONS -- Check whether any agent definition files need updates:
   - Only if the discovery changes an agent's responsibilities or adds a new reference document

3. CLAUDE.md -- Check whether any sections need updates:
   - Key Metrics We Track -- if new stat categories are discovered
   - GameChanger API section -- if credential or API behavior patterns change

4. RULES -- Check whether any rule files need updates:
   - Only if the discovery reveals a new workflow pattern or constraint

5. STAT GLOSSARY -- If new stat abbreviations appear that are not in
   `docs/gamechanger-stat-glossary.md`, flag them for the user (the glossary is sourced
   from the GC UI, so new abbreviations need UI verification before being added).

For each area: if no update is needed, skip it silently. Only report areas where you
made changes or identified items requiring user action.
```

---

## Workflow Summary

```
User saves curl to secrets/gamechanger-curl.txt
  |
  v
Team lead reads this skill
  |
  v
Phase 1: Spawn api-scout
  - Execute curl (TIME-SENSITIVE)
  - Save raw response to data/raw/
  - Verify no credential leaks
  - Document endpoint in docs/gamechanger-api.md
  - Check E-002-R-01 research impact
  - Return findings summary
  |
  v
[If 401/403: stop, ask user to refresh curl]
  |
  v
Phase 2: Spawn claude-architect
  - Review findings
  - Update agent memory files as needed
  - Update agent definitions if needed
  - Update CLAUDE.md if needed
  - Flag new stat abbreviations
  - Return changes summary
  |
  v
Team lead presents combined summary to user
```

---

## Security Invariants

These apply throughout the entire workflow -- both phases, all agents:

- **NEVER** display, log, echo, or include `gc-token` or `gc-device-id` values in any output, file, or conversation
- `secrets/` directory is gitignored -- curl files with credentials live there and must never leave
- Raw responses go to `data/raw/` (also gitignored) -- strip any auth headers before saving
- In `docs/gamechanger-api.md`, credential values are always `{AUTH_TOKEN}`, `{DEVICE_ID}`, or similar placeholders
- The PII pre-commit hook provides a safety net, but do not rely on it -- prevent leaks at the source

---

## Edge Cases

### Credential Expiration Mid-Workflow
If api-scout gets a 401 or 403, the workflow stops. The user must recapture the curl from the browser. Do not retry with the same credentials -- they are expired.

### Endpoint Already Fully Documented
This is normal and expected. The workflow still adds value: it re-verifies the endpoint against live data, catches any API changes since the last verification, and updates the verification date. api-scout should note "validated existing documentation" rather than "no changes needed."

### Multiple Endpoints in One Curl File
The curl file should contain exactly one curl command. If the user has pasted multiple commands, ask them to put one command at a time in the file and run the workflow once per endpoint.

### Response Too Large for data/raw/
GameChanger responses are typically under 100KB. If a response is unusually large (>1MB), save it anyway but note the size in the api-scout summary -- it may indicate a pagination issue or an unexpectedly rich endpoint.

### E-002-R-01 Does Not Exist or Is Archived
If the research spike file has been archived or deleted, skip the research relevance check. The E-002 research questions may have been fully answered by prior ingestions.

---

## Anti-Patterns

1. **Do not delay Phase 1.** Credentials expire quickly. Do not spend time planning, reading extensive context, or consulting other agents before executing the curl. Parse, execute, save, then document.
2. **Do not run both phases in parallel.** Phase 2 depends on Phase 1's findings summary. Wait for api-scout to complete before spawning claude-architect.
3. **Do not skip Phase 2.** Even if the endpoint was already documented, the context layer integration check ensures agent memory stays current with the latest verification dates and any schema changes.
4. **Do not modify the curl file.** The file in `secrets/gamechanger-curl.txt` is the user's input. Read it; do not edit it.
5. **Do not make the api-scout execute additional API calls beyond the provided curl.** This workflow ingests one endpoint per invocation. Follow-up exploration is a separate workflow.
