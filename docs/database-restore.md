# Database Backup and Restore

## Backup

Create a timestamped copy of the SQLite database:

```bash
python scripts/backup_db.py
```

This copies `./data/app.db` to `./data/backups/app-<timestamp>.db`. The backups
directory is created automatically and is git-ignored.

Override the database path if needed:

```bash
python scripts/backup_db.py --db-path /path/to/other.db
```

## Restore

To restore from a backup, stop the stack, copy the backup into place, and restart:

```bash
# 1. Stop the application
docker compose down

# 2. Replace the database with the backup
cp ./data/backups/app-2026-03-02T140000.db ./data/app.db

# 3. Restart the application
docker compose up -d
```

## Verify a Restore

After restoring, confirm the database is healthy:

```bash
sqlite3 ./data/app.db "PRAGMA integrity_check; PRAGMA journal_mode;"
```

A healthy database returns `ok` and `wal`.

## Development Database Reset

For local development, use the reset script to drop and recreate the database
with seed data:

```bash
python scripts/reset_dev_db.py
```

See `python scripts/reset_dev_db.py --help` for options.
