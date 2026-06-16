# Roadmap

Planned improvements for discord-mirror, ordered by impact. Checkboxes track status.

## High impact

### 1. Add database indexes
The schema currently has **zero indexes** and `cache.db` is already ~46 MB. Every stats
command does a full table scan.

- [ ] `message_counts(author_id)` / `(guild, author_id)` — `!top-posters`, `!stats`
- [ ] `voice_sessions(user_id)` and `voice_sessions(channel)` — `!vc-stats`, `!vc-history`, `!member`
- [ ] Review `messages` filters (`author_id`, `channel`) and index where scanned
- [ ] Add as `CREATE INDEX IF NOT EXISTS` alongside the `CREATE TABLE`s in `main()`

### 2. Prune the `messages` cache — WILL NOT IMPLEMENT
Decided against. The full message cache is kept intentionally.

<details>
<summary>Original proposal</summary>

`messages` is only deleted from on an actual Discord delete event (`logger.py:1759`), so
messages that are never deleted stay forever — the main driver of DB growth. The cache only
needs a rolling window to recover deleted/edited content; flat `.log` files remain the
permanent record.

- Periodic prune worker: `DELETE FROM messages WHERE created_at < ?` (e.g. 30–90 day window)
- Occasional `VACUUM` to reclaim space
- Make the retention window configurable via `.env`
</details>

### 3. Move blocking file I/O off the event loop
`_write` (`logger.py:119`) and `_write_guild_name` use synchronous `open().write()` /
`write_text()` inside async handlers like `on_message`, blocking the whole event loop (all
accounts + mirroring) on disk during busy periods.

- [ ] Route log-file writes through a dedicated write queue/task (mirror the existing post/mirror worker pattern), `run_in_executor`, or `aiofiles`

## Medium impact

### 4. Tame the broad `except Exception` handlers
There are ~76 broad `except Exception` blocks; several catch-and-`pass` or catch-and-log,
hiding real bugs (cf. `ebdf87e Fix silent archive sync worker crashes`).

- [ ] Catch specific Discord exceptions where expected (`discord.Forbidden`, `discord.HTTPException`, `discord.NotFound`)
- [ ] Let unexpected exceptions surface with a traceback

### 5. Split the 3,166-line `logger.py` into modules
- [ ] Break into `logging_`, `mirror`, `voice`, `commands`, `db` modules (behavior-preserving)
- [ ] Precondition for easier exception cleanup and testing

### 6. Add a test suite (currently none)
- [ ] Unit tests for pure helpers: `_fmt_duration`, `_log_path`, env parsing, `_overflow_index`, ordering logic
- [ ] DB-layer tests against in-memory SQLite, especially sync/ordering code

## Lower / nice-to-have

- [ ] Bound the `on_ready` per-channel history fetch for missed-delete detection on large guilds
- [ ] Add config validation with clear error messages (currently raises at import, `logger.py:24`)
- [ ] Pin dependency versions in `requirements.txt` (esp. `discord.py-self`, which tracks Discord internals)
