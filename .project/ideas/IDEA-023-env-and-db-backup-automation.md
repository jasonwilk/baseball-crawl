# IDEA-023: Automated .env and app.db Backup

## Status
`CANDIDATE`

## Summary
Automated periodic backup of `.env` (credentials) and `data/app.db` (SQLite database) -- the only two pieces of precious state without a recovery path. A host rebuild or disk failure loses both, and re-crawling data takes hours while credential recapture is manual and painful.

## Why It Matters
The infrastructure review (PM, SE, CA -- 2026-03-13) identified `.env` + `app.db` as the single biggest operational risk. Everything else is either in git or reproducible from a container rebuild. These two files are precious and currently have no automated backup. `scripts/backup_db.py` exists but is manual (`bb db backup`). `.env` has no backup mechanism at all.

## Rough Timing
Before the season is in full swing and the database has significant accumulated data. The pain increases linearly with crawled data volume.

Trigger: operator has run `bb data sync` more than 5 times, or season starts -- whichever comes first.

## Dependencies & Blockers
- [ ] None -- can be implemented at any time

## Open Questions
- Backup destination: local second directory? Encrypted cloud storage? Both?
- Encryption: `.env` contains credentials -- must be encrypted at rest. `gpg --symmetric` or age?
- Frequency: daily cron? On every `bb data sync`? Both?
- Retention: how many backup copies to keep?
- Should this be a host-level cron job or a devcontainer script?
- Should `bb db backup` be enhanced to also back up `.env`, or keep them separate?

## Notes
- `scripts/backup_db.py` already exists and handles SQLite backup safely (copy while in WAL mode). Could be extended or wrapped.
- The simplest version: a bash script that `gpg --symmetric` both files to a `~/.backups/baseball-crawl/` directory, run via cron daily.
- Related to IDEA-012 (Crawl Orchestration) -- if orchestration adds scheduling, backup could hook into the same schedule.

---
Created: 2026-03-13
Last reviewed: 2026-03-13
Review by: 2026-06-13
