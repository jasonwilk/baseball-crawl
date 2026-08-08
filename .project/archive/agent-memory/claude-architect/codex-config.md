---
name: codex-config
description: Codex CLI configuration -- model, reasoning effort, scripts, and available models
type: reference
---

# Codex Configuration

- Codex CLI version: 0.142.4 (as of 2026-06-30; was 0.111.0 on 2026-03-07)
- Model: `gpt-5.4` with reasoning effort `xhigh` (configured in `~/.codex/config.toml`)
- Previous model: `gpt-5.3-codex` (auto-migrated to 5.4)
- Available models (from models cache): gpt-5.4, gpt-5.3-codex, gpt-5.2-codex, gpt-5.2, gpt-5.1-codex-max, gpt-5.1-codex, gpt-5.1-codex-mini, gpt-5.1, gpt-5-codex, gpt-5-codex-mini, gpt-5
- Reasoning effort levels: low, medium, high, xhigh (all models support the same set)
- Scripts (`codex-review.sh`, `codex-spec-review.sh`) do NOT pass `--model` -- they inherit from global config
- Config location: `~/.codex/config.toml` (not checked into repo -- per-environment)
- The `--model` flag is available on `codex exec` if per-invocation override is ever needed: `codex exec -m gpt-5.4 ...`

## Native `codex review` is NOT a substitute for our custom `codex exec` + rubric (verified v0.142.4, 2026-06-30)

Evaluated whether to switch `codex-review.sh`/`codex-spec-review.sh` from `codex exec --ephemeral -` (custom `.project/*.md` rubric piped as the prompt) to the native `codex review` subcommand. **Verdict: keep custom `codex exec` for BOTH spec and code review.** Two structural blockers, both empirically confirmed (not help-text inference):

1. **PROMPT is mutually exclusive with the diff-scope flags.** `codex review [PROMPT]` and `codex exec review [PROMPT]` both reject `--uncommitted`/`--base`/`--commit` when a PROMPT (custom instructions) is given: `error: the argument '--uncommitted' cannot be used with '[PROMPT]'`. The `--help` usage line lists `[PROMPT]` alongside the flags because clap enumerates the *conflict group*, NOT because they compose. HALLUCINATION TRAP: do not infer composition from `--help`; run it. So adopting native review for CODE review would silently swap our project rubric (perspective-provenance, SQL-param, status-lifecycle, schema-drift) for Codex's generic built-in review rubric — defeating the purpose.
2. **No native form targets a directory of files.** All three native forms (`codex review`, `codex exec review`, PROMPT-only) are diff-oriented. Native review structurally cannot ingest a markdown epic dir as a review target, so it's a non-starter for SPEC review — the only directory-aware path is `codex exec`.

The justification comments in `scripts/codex-review.sh:4-9` (mutual exclusivity) and `scripts/codex-spec-review.sh:5-9` (spec review is not diff-centric) are therefore CORRECT and current as of v0.142.4 — do not "modernize" them to native `codex review`.

Incidental (deferred to a separate idea/epic, NOT a workflow change): refresh both scripts' stale `v0.107.0` version headers to `0.142.4`; re-verify the `CODEX_SANDBOX_OFF`/`--sandbox danger-full-access` branch is still needed given the bundled-bubblewrap read-only fallback; adopt `codex exec`'s `-o/--output-last-message <FILE>` to persist the final message straight to the read-receipt `.txt` (would harden the [[codex-spec-review SKILL Step 4 read-receipt gate]]).
