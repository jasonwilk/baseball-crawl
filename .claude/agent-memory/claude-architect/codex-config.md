---
name: codex-config
description: Codex CLI configuration -- model, reasoning effort, scripts, and available models
type: reference
---

# Codex Configuration

- Codex CLI version: 0.111.0 (as of 2026-03-07)
- Model: `gpt-5.4` with reasoning effort `xhigh` (configured in `~/.codex/config.toml`)
- Previous model: `gpt-5.3-codex` (auto-migrated to 5.4)
- Available models (from models cache): gpt-5.4, gpt-5.3-codex, gpt-5.2-codex, gpt-5.2, gpt-5.1-codex-max, gpt-5.1-codex, gpt-5.1-codex-mini, gpt-5.1, gpt-5-codex, gpt-5-codex-mini, gpt-5
- Reasoning effort levels: low, medium, high, xhigh (all models support the same set)
- Scripts (`codex-review.sh`, `codex-spec-review.sh`) do NOT pass `--model` -- they inherit from global config
- Config location: `~/.codex/config.toml` (not checked into repo -- per-environment)
- The `--model` flag is available on `codex exec` if per-invocation override is ever needed: `codex exec -m gpt-5.4 ...`
