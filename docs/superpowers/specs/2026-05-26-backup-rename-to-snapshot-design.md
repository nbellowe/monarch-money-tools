# Design: Rename `backup` command to `snapshot`

**Date:** 2026-05-26  
**Status:** Approved

## Problem

`monarch backup` implies downloading cloud data to a local backup — consistent with how "backup" is used in tools like `pg_dump` or `rclone`. The actual command takes a point-in-time snapshot of local `data/` and `reports/` directories before destructive operations. This mismatch confuses new users.

`monarch pull` already handles fetching data from Monarch, so there is no gap to fill — only a naming problem to fix.

## Decision

Rename `backup` → `snapshot` throughout. No backwards-compat shim; this is a local CLI with no external consumers.

## Changes

### `backup.py` → `snapshot.py`

- Rename file
- Rename `create_pre_cleanup_backup()` → `create_pre_op_snapshot()`
- Rename `verify_pre_cleanup_backup()` → `verify_pre_op_snapshot()`
- Change backup directory prefix from `pre-cleanup-{timestamp}` → `pre-op-{timestamp}` (the command is used before rules, review, and cleanup — not just cleanup)

### `cli.py`

- Update import: `from .snapshot import create_pre_op_snapshot, verify_pre_op_snapshot`
- Rename `backup_command()` → `snapshot_command()`
- Update docstring: `"Snapshot current data/ and reports/ before destructive operations."`
- Update `@app.command("backup")` → `@app.command("snapshot")`
- Update grouped alias registration: `data_app.command("snapshot")(snapshot_command)`

### `docs/commands.md`

- Update `monarch data backup` → `monarch data snapshot` in the Data commands table

### Tests

- Update any references to `backup_command`, `create_pre_cleanup_backup`, or `verify_pre_cleanup_backup`

## Out of Scope

- No new "pull from Monarch" backup feature — `monarch pull` already covers that use case
- No `monarch backup` group or subcommands
