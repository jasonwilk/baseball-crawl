# Ephemeral Data Directory

Safe landing zone for any data file that contains or might contain real data
from the GameChanger API. Everything in this directory is gitignored. Nothing
here is committed, backed up, or versioned.

## What Belongs Here

- Raw API responses (JSON, CSV) from GameChanger exploration
- Intermediate files from ETL development and debugging
- Any file produced by a real API call, regardless of format
- Credential dumps, session captures, or auth debugging output

## What Does NOT Belong Here

- **Test fixtures with synthetic data** -- those go in `tests/` with the
  `synthetic-test-data` marker in the first 5 lines
- **Processed output for the database** -- that goes in `data/`
- **Source code** -- that goes in `src/`

## Convention

Create a subdirectory named after your current epic:

```
ephemeral/E-005/     # files related to E-005 work
ephemeral/E-012/     # files related to E-012 work
```

Use `ephemeral/scratch/` for one-off experiments not tied to a specific epic.

## Warning

Files here are never backed up or versioned. If you need to share an
exploration artifact with another agent or teammate, describe the API call
that produced it -- do not share the file itself.
