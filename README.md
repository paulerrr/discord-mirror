# discord-mirror

A Discord self-bot with two independent features: **message logging** and **server/channel mirroring**. You can use either or both — logging works with no mirror configuration, and mirroring works without a log channel.

## Features

### Message logging
Logging is always active for watched guilds. No extra configuration beyond a token is required.

- **Message logging** — every new message, edit, and delete is written to dated flat files under `logs/<guild>/<channel>_YYYY-MM-DD.log`
- **SQLite cache** — message content and metadata stored in `data/cache.db` so deleted messages can be logged with their original content
- **Media saving** — attachments and stickers downloaded locally to `media/`
- **Log channel** — optionally post edit/delete summaries to a Discord channel in real time with attachment previews (`LOG_CHANNEL_ID`)
- **Missed delete detection** — on reconnect, recent history is fetched per channel and any messages deleted while offline are logged retroactively

### Mirroring
Mirroring is opt-in and configured separately from logging. Set `MIRROR_CHANNELS` or `MIRROR_SERVERS` (or both) to enable it.

- **Channel mirroring** — relay specific channels to webhook URLs, including edits, deletes, and reply threading (`MIRROR_CHANNELS`)
- **Server mirroring** — replicate an entire guild's channel structure to a destination guild; channels probe for readability, unreadable ones are grouped separately, and the structure stays in sync via a periodic archive worker (`MIRROR_SERVERS`)
- **Thread mirroring** — threads created in mirrored text channels are automatically created in the destination and kept in sync
- **Channel ordering** — destination guild channel and category order is kept in sync with the source; the correct order is cached in the DB and restored automatically if it drifts

### General
- **Multi-account** — multiple user tokens can be provided; each claims guilds and shares one DB
- **Log poster token** — `LOG_POSTER_TOKEN` offloads log channel posts and dest guild edits to a separate account, keeping the main token's activity pattern cleaner

## Setup

### Requirements

- Docker + Docker Compose

### Configuration

Copy `.env.example` to `.env` (or create `.env` from scratch) and fill in the variables:

```env
# Required: one or more user tokens, comma-separated
DISCORD_TOKENS=token1,token2

# Optional: restrict logging to specific guild IDs (comma-separated)
WATCHED_GUILDS=

# Optional: post edit/delete summaries to this channel
LOG_CHANNEL_ID=
# Optional: use a separate token for log channel posts and dest guild edits
LOG_POSTER_TOKEN=

# Optional: mirror individual channels to webhook URLs
# Format: channel_id:webhook_url,channel_id:webhook_url
MIRROR_CHANNELS=

# Optional: mirror entire guilds
# Format: src_guild_id:dst_guild_id,src_guild_id:dst_guild_id
MIRROR_SERVERS=
```

### Run

```bash
docker compose up -d
```

Logs, media, and the database are mounted from the host:

```
logs/    — flat text logs, organised by guild and channel
media/   — downloaded attachments and stickers
data/    — SQLite database (cache.db)
```

## Server mirroring details

On first run, the bot:
1. Clears the destination guild
2. Recreates the full channel/category structure from the source
3. Probes each channel for readability, creates a `MessageMirror` webhook in each readable channel
4. Moves unreadable channels to a `🔒 Unreadable` category
5. Syncs channel and category order to match the source

On subsequent restarts, if channels are already mapped in the DB the rebuild is skipped entirely.

Every 30 minutes an archive sync worker re-checks for channels that have disappeared (moved to `📁 Archived`) or become newly readable (webhook provisioned, moved to proper category).

New channels and threads created after initial setup are picked up automatically via `on_guild_channel_create` and `on_thread_create`.

### Channel ordering

The correct order is derived from the source guild and cached in `data/cache.db`. On startup and once daily the bot:

1. Re-reads the source guild's current order and updates the cache if anything changed
2. Compares the cache to the actual dest guild state
3. If both match — nothing happens, no API calls are made
4. If the dest has drifted from the cache — it is restored
5. If the source changed — the cache is updated and the dest is brought in line

Send `!sync-order` as the main account to trigger this immediately on demand.

`🔒 Unreadable` and `📁 Archived` categories are always kept at the bottom regardless of source ordering.
