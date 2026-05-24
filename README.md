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

### Voice & member stats
- **Voice session tracking** — every VC join and leave is recorded with timestamps and duration in `data/cache.db`
- **Member profile caching** — on VC join the bot fetches each member's Discord profile (display name, avatar, bio) and caches it; refreshed every 7 days
- **Daily VC summary** — at midnight UTC a summary of the day's voice activity (with display names and bios) is posted to the log channel
- **Commands** — usable by any account in the server:

| Command | Description |
|---|---|
| `!vc-stats` | All-time voice leaderboard |
| `!vc-today` | Today's voice activity |
| `!vc-channel <name>` | Leaderboard for a specific voice channel |
| `!vc-history <name or ID>` | Last 15 sessions for a user |
| `!member <name or ID>` | Profile, VC rank, avg/longest session, messages per day |
| `!top-posters` | Most messages sent; shows deleted count per user where non-zero |
| `!stats` | Server-wide summary: messages, VC hours, profiles cached |
| `!sync-order` | Re-sync mirror channel ordering |
| `!help` | Lists all commands |

### General
- **Multi-account** — multiple user tokens can be provided; each claims guilds and shares one DB
- **Log poster token** — offloads log channel posts and all command replies to a dedicated account, keeping the main token's activity pattern cleaner. Two options (can be set together):
  - `LOG_POSTER_BOT_TOKEN` — a legitimate Discord bot token (recommended); connects via REST only, no WebSocket. Used for all command replies and log channel posts when set.
  - `LOG_POSTER_TOKEN` — a secondary user account token. When set alongside `LOG_POSTER_BOT_TOKEN`, stays connected for guild presence and command handling in guilds the bot token can't see. When set alone, also handles posting.

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
# Optional: legitimate Discord bot token for posting to LOG_CHANNEL_ID (recommended)
# The bot only needs Send Messages + Attach Files in the log channel.
# Takes priority over LOG_POSTER_TOKEN if both are set.
LOG_POSTER_BOT_TOKEN=
# Optional: secondary user account token for posting to LOG_CHANNEL_ID
# Used only when LOG_POSTER_BOT_TOKEN is not set.
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
