# IDEA-001: Local Development Environment Mimicking Cloudflare (Containerized)

## Status
`DISCARDED`

## Summary
A local container environment that reproduces the Cloudflare runtime -- D1 (SQLite), Workers, and Pages -- so dashboard and API changes can be developed and tested without deploying to Cloudflare.

## Why It Matters
Right now, testing any Workers or Pages code requires a real Cloudflare deployment. This creates friction: every mockup or dashboard iteration requires a push, credentials, and a live environment. A local container with Miniflare (or similar) would make the feedback loop instant -- write code, run container, see result. This matters most during the E-004 dashboard phase when the coaching staff UI will be iterated on heavily. It also reduces risk of pushing broken code to a shared environment.

## Rough Timing
Before the E-004 (Coaching Dashboard) epic goes into active development. We will feel the pain of deploy-to-test when E-004 stories start. That is the natural trigger to promote this idea.

A secondary trigger: if we start needing to test Workers ETL jobs (E-002) and deploying for each test becomes annoying.

## Dependencies & Blockers
- [ ] E-002 (Data Ingestion) must reach at least ACTIVE -- otherwise we have nothing to run locally
- [ ] E-003 (Data Model) migrations must be stable -- the container needs a schema to initialize against
- [ ] Need to evaluate Miniflare vs. wrangler dev vs. a custom Docker Compose setup -- a research spike would be appropriate here before writing stories
- [ ] Cloudflare's local dev tooling evolves fast; worth checking current state of `wrangler dev` before committing to any approach

## Open Questions
- Does `wrangler dev` now cover enough of the runtime that a separate container is unnecessary?
- Can we seed D1 locally with a snapshot of production data for realistic testing?
- How do we handle Cloudflare secrets (env vars) in a local container safely?
- Should this be a Docker Compose setup, or a shell script wrapping wrangler?

## Notes
Prior art / inspiration:
- LocalStack (https://github.com/localstack/localstack) -- the AWS equivalent. Same concept: run cloud services locally in a container. This is exactly the model to follow for Cloudflare.

Relevant tooling to evaluate when this gets promoted:
- Miniflare: https://miniflare.dev (Cloudflare's own local simulator)
- `wrangler dev` with `--local` flag -- may already do most of what we need
- Docker Compose with a seeded SQLite file for D1 simulation

This is the kind of investment that pays off across all dashboard work. Low urgency now; high value before E-004 begins in earnest.

---
Created: 2026-02-28
Last reviewed: 2026-02-28
Review by: 2026-05-29

## Discard Reason
Superseded by E-009 (Tech Stack Redesign -- Portable, Docker-First, Agent-Browsable).
E-009 takes a more fundamental approach: instead of simulating Cloudflare locally, the
project is moving away from Cloudflare Workers/Pages entirely in favor of a Docker-first
stack (FastAPI + SQLite + Docker Compose) that runs identically local and in production.
The Miniflare/wrangler-dev approach that IDEA-001 was scoping is no longer relevant.
Discarded 2026-02-28.
