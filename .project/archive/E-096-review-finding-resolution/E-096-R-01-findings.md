# E-096-R-01 Findings: Interactive Codex Review Conversation

## Environment

- **Codex CLI version**: 0.112.0
- **Model**: gpt-5.4 (inherited from global config)
- **Reasoning effort**: high (from `.codex/config.toml`)
- **Test date**: 2026-03-12
- **Runtime**: devcontainer (Linux, same environment as dispatch)

## Research Question Answers

### RQ-1: Can `codex exec --ephemeral` accept a scoped question with file context and return a useful answer?

**Yes.** The command `codex exec --ephemeral -s read-only -o <output-file> -` accepts a prompt via stdin and returns a text response. The `-` argument tells Codex to read the prompt from stdin. The `-o` flag writes the final agent message to a file for clean programmatic consumption. The `-s read-only` sandbox prevents Codex from modifying any files.

**Reproducible invocation:**

```bash
echo 'FINDING TRIAGE REQUEST

Finding: "Variable `d` should be renamed" in src/gamechanger/crawlers/scouting.py line 47.

Code context:
```python
async def crawl_opponent_schedule(self, public_id: str) -> list[dict]:
    d = await self.client.get(f"/public/teams/{public_id}/games")
    return d.json()
```

Project convention: "prefer descriptive names."

Question: Should this be MUST FIX, SHOULD FIX, or dismissed? The variable is used once in a 3-line function.' \
  | codex exec --ephemeral -s read-only -o /tmp/verdict.txt -
```

The output file `/tmp/verdict.txt` contains the clean response text (no session metadata, no token counts).

### RQ-2: Is the response quality sufficient for nuanced review discussions?

**Yes, with a caveat.** Codex (gpt-5.4) produces nuanced, context-aware triage verdicts. In testing:

- It correctly identified that a single-letter variable in a 3-line function is dismissable.
- When asked a follow-up about the same pattern appearing in 5 functions, it correctly upgraded the severity while explaining the reasoning.
- It proactively read the actual source file to check whether the finding was stale (it was -- the current code uses `games_data`, not `d`).
- With `--output-schema`, it produced valid structured JSON matching the provided schema (verdict + rationale).

**The caveat**: Codex has full repository access in `read-only` mode. When given a vague question, it will search the codebase to find context, which inflates token usage and latency. Questions that embed the relevant code snippet inline produce faster, cheaper, equally-good responses.

### RQ-3: What are the latency characteristics?

Latency varies significantly by question complexity and whether Codex decides to read files:

| Scenario | Latency | Tokens Used | Notes |
|----------|---------|-------------|-------|
| Minimal (1-word answer, no file reads) | 4.1 sec | 1,417 | Floor latency: CLI startup + API round-trip |
| Scoped question with embedded code | 34.0 sec | 16,634 | Codex read the actual file to verify |
| Non-ephemeral first turn (full context load) | 53.9 sec | 26,521 | Codex read CLAUDE.md + source file |
| Resume (multi-turn follow-up) | 7.2 sec | 26,872 | Session context already loaded; fast |
| Structured output (`--output-schema`) | 107.1 sec | 28,517 | Codex did extensive file searching |

**Assessment for dispatch loop**: For triaging 3-5 findings, the practical range is 7-35 seconds per finding after the first turn. The first turn pays a one-time setup cost of ~50 seconds if Codex loads project context. Using `codex exec resume --last` for subsequent findings in the same session brings per-question latency to ~7 seconds. A 5-finding triage session would take approximately 50 + (4 * 7) = 78 seconds total (~1.3 minutes).

### RQ-4: What are the cost implications compared to batch review?

**Token usage per interactive question**: 1,400-28,500 tokens depending on complexity and file access. A typical finding triage with embedded code context uses ~16,000 tokens.

**Comparison to batch review**: The existing `codex-review.sh` batch approach sends the entire diff once and gets all findings back. An interactive session sends multiple smaller prompts but each one loads project context (CLAUDE.md, AGENTS.md). Using `resume` for multi-turn avoids reloading context after the first turn.

**Estimated cost for a 5-finding triage session**: ~80,000 tokens (first turn ~27K + 4 resumed turns ~13K each). This is comparable to or less than a batch review (which loads the full diff + rubric + context in one prompt).

**Key cost-saving pattern**: Use `codex exec` (non-ephemeral) for the first finding, then `codex exec resume --last` for subsequent findings. This reuses the loaded context and avoids the ~27K token context-loading overhead on each turn.

### RQ-5: Multi-turn conversation support?

**Yes, via session resume.** Codex supports two patterns:

1. **Non-ephemeral sessions** (`codex exec` without `--ephemeral`): Codex persists session state to `$CODEX_HOME/sessions/`. Subsequent turns use `codex exec resume --last -` to continue the same conversation with full context.

2. **Named sessions** (`codex exec resume <SESSION_ID> -`): If the session ID is known, it can be resumed explicitly rather than using `--last`.

**What works:**
- `codex exec resume --last -o /tmp/out.txt -` reads follow-up from stdin, writes response to file.
- Context from prior turns is preserved (the model remembers what was discussed).
- Latency drops significantly on resumed turns (~7 sec vs ~50 sec for first turn).

**What does NOT work:**
- `codex exec resume` does not support the `-s` (sandbox) flag. The sandbox from the original session is inherited. This means the first invocation must set `-s read-only` if sandboxing is desired.
- There is no way to inject new file content mid-session without a fresh prompt that references the file path (Codex reads it via its repository access).

**Practical multi-turn pattern:**

```bash
# Turn 1: establish session with sandbox and context
echo 'Finding 1 details...' | codex exec -s read-only -o /tmp/turn1.txt -

# Turn 2+: resume with follow-up
echo 'Finding 2 details...' | codex exec resume --last -o /tmp/turn2.txt -

# Turn 3+: continue
echo 'Finding 3 details...' | codex exec resume --last -o /tmp/turn3.txt -
```

## Additional Discoveries

### Structured Output (`--output-schema`)

Codex supports `--output-schema <file>` which accepts a JSON Schema file and constrains the final response to match. This enables programmatic parsing of verdicts:

```bash
# Schema: {"type":"object","properties":{"verdict":{"type":"string","enum":["MUST_FIX","SHOULD_FIX","DISMISS"]},"rationale":{"type":"string"}},"required":["verdict","rationale"]}
echo 'Triage this finding...' | codex exec --ephemeral --output-schema schema.json -o /tmp/out.json -s read-only -
# /tmp/out.json contains: {"verdict":"DISMISS","rationale":"..."}
```

**Trade-off**: Structured output produced correct JSON in testing, but latency was 3x higher (107 sec vs 34 sec) because Codex did more extensive file searching before committing to a verdict. For dispatch-loop usage, plain text responses parsed by the main session are likely more practical than structured output.

### Output File (`-o` flag)

The `-o` / `--output-last-message` flag writes only the final agent message to a file, stripping all session metadata and token counts. This is the cleanest way to capture Codex output for programmatic use.

### Sandbox Inheritance on Resume

When resuming a session, the sandbox policy from the original session is inherited. The `-s` flag is not accepted on `codex exec resume`. This is important: the first turn MUST set the correct sandbox policy.

## Recommendation

**Verdict: DEFER**

### Rationale

Interactive Codex review is technically feasible and produces good results. The multi-turn `resume` pattern provides acceptable latency (7-35 sec per finding after setup). However, integrating it into the dispatch loop introduces complexity that is not justified by the current pain level:

1. **The dispatch loop does not currently triage SHOULD FIX findings.** Per the current dispatch pattern, SHOULD FIX findings are recorded in epic History during closure -- they are not sent to implementers. The main session's job is binary: route MUST FIX to implementers, log SHOULD FIX. There is no triage decision point where Codex consultation would fire.

2. **The resolution-first model (E-096-01/02) changes this.** If the epic's main stories introduce a resolution-first pattern where the main session must decide whether to escalate ambiguous findings, Codex consultation becomes valuable. But the integration point depends on how E-096-01/02 are implemented.

3. **Shell-based integration is fragile.** The multi-turn pattern (non-ephemeral first turn + resume) requires managing session lifecycle, sandbox inheritance, and output file paths. This is manageable in a script but awkward to integrate into a Claude Code agent's reasoning loop (the agent would need to issue multiple sequential Bash calls and parse output files).

### Re-evaluation Trigger

Re-evaluate when **both** conditions are met:
- E-096-01/02 are implemented and the resolution-first model is in production.
- The main session encounters at least 3 real cases where SHOULD FIX triage would have benefited from a second opinion (track this in epic History entries).

### If Integration Proceeds Later

The recommended integration point is a standalone script (similar to `codex-review.sh`) that the main session invokes during the review loop:

```bash
# codex-triage.sh <finding-text> [--context <file-path>]
# Returns: MUST_FIX, SHOULD_FIX, or DISMISS with rationale
```

This keeps the Codex interaction shell-based (where it works well) and avoids embedding multi-turn session management into agent reasoning.
