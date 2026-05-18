# discord-mirror

A Discord self-bot that logs messages to disk and mirrors channels or entire servers to a destination guild via webhooks.

## Features

- **Message logging** — every new message, edit, and delete is written to dated flat files under `logs/<guild>/<channel>_YYYY-MM-DD.log`
- **SQLite cache** — message content and metadata stored in `data/cache.db` so deleted messages can be logged with their original content
- **Media saving** — attachments and stickers downloaded locally to `media/`
- **Log channel** — edits and deletes posted to a Discord channel in real time with attachment previews
- **Channel mirroring** — relay specific channels to webhook URLs, including edits, deletes, and reply threading
- **Server mirroring** — replicate an entire guild's channel structure to a destination guild; channels probe for readability, unreadable ones are grouped separately, and the structure stays in sync via a periodic archive worker
- **Thread mirroring** — threads created in mirrored text channels are automatically created in the destination and kept in sync
- **Missed delete detection** — on reconnect, recent history is fetched per channel and any messages deleted while offline are logged retroactively
- **Multi-account** — multiple user tokens can be provided; each claims guilds and shares one DB

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
# Optional: use a separate token for log channel posts
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

On subsequent restarts, if channels are already mapped in the DB the rebuild is skipped entirely.

Every 30 minutes an archive sync worker re-checks for channels that have disappeared (moved to `📁 Archived`) or become newly readable (webhook provisioned, moved to proper category).

New channels and threads created after initial setup are picked up automatically via `on_guild_channel_create` and `on_thread_create`.
