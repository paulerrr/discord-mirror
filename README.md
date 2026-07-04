# discord-mirror

A Discord self-bot with two independent features: **message logging** and **server/channel mirroring**. You can use either or both — logging works with no mirror configuration, and mirroring works without a log channel.

## Features

### Message logging
Logging is always active for watched guilds. No extra configuration beyond a token is required.

- **Message logging** — every new message, edit, and delete is written to dated flat files under `logs/<guild>/<channel>_YYYY-MM-DD.log`
- **SQLite cache** — message content and metadata stored in `data/cache.db` so deleted messages can be logged with their original content
- **Media saving** — attachments and stickers downloaded locally to `media/`; over-long attachment filenames are truncated to fit filesystem limits so a save never fails on the name
- **Log channel** — optionally post edit/delete summaries to a Discord channel in real time with attachment previews (`LOG_CHANNEL_ID`); per-guild overrides route individual servers to their own channels (`LOG_CHANNELS`). Posts go through a queue with retries and per-send timeouts, so one failed or hung send can't stall the rest
- **Missed delete detection** — on reconnect, recent history is fetched per channel and any messages deleted while offline are logged retroactively

### Mirroring
Mirroring is opt-in and configured separately from logging. Set `MIRROR_CHANNELS` or `MIRROR_SERVERS` (or both) to enable it.

- **Channel mirroring** — relay specific channels to webhook URLs, including edits, deletes, and reply threading (`MIRROR_CHANNELS`)
- **Server mirroring** — replicate an entire guild's channel structure to a destination guild; channels probe for readability, unreadable ones are grouped separately, and the structure stays in sync via a periodic archive worker (`MIRROR_SERVERS`)
- **Thread mirroring** — threads created in mirrored text channels are automatically created in the destination and kept in sync
- **Channel renames** — renaming a channel, voice channel, or forum in the source updates the destination channel's name in real time
- **Channel ordering** — destination guild channel and category order is kept in sync with the source; the correct order is cached in the DB and restored automatically if it drifts
- **Historical backfill** — on-demand `!backfill` command caches a mirror source guild's full message history into the delete-recovery cache (DB only, nothing relayed or downloaded); `!backfill-with-attachments` additionally downloads attachments and stickers to `media/`, and can be run after a plain `!backfill` to fetch attachments later (`MIRROR_SERVERS`)

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
| `!sync` | Full mirror re-sync: archive state, channel names, then ordering |
| `!sync-order` | Re-sync mirror channel ordering |
| `!backfill` | Cache a mirror source guild's full message history into the delete-recovery cache (metadata only, no downloads); run from the destination guild |
| `!backfill-with-attachments` | Same as `!backfill` but also downloads attachments and stickers to `media/`; can be run afterwards to fetch attachments for an already-cached guild; run from the destination guild |
| `!backfill-status` | Check backfill progress for a mirror's source guild; run from the destination guild |
| `!help` | Lists all commands |

### General
- **Multi-account** — multiple user tokens can be provided; each claims guilds and shares one DB
- **Log poster tokens** — offload log channel posts and all command replies to dedicated accounts, keeping the main token's activity pattern cleaner. Two kinds, each accepting a comma-separated list (can be set together):
  - `LOG_POSTER_BOT_TOKENS` — one or more legitimate Discord bot tokens (recommended); connect via REST only, no WebSocket. For a given log channel, the first bot that can see it posts there.
  - `LOG_POSTER_TOKENS` — one or more secondary user account tokens. These stay connected for guild presence and command handling in guilds the bot tokens can't see.
  - Posting is resolved **per log channel**: bot posters are tried first, then user posters, then any main account that can see the channel — so you can log servers that no single account is a member of by spreading membership across several poster tokens. The singular `LOG_POSTER_BOT_TOKEN` / `LOG_POSTER_TOKEN` names still work and are merged into the lists.

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

# Optional: default channel to post edit/delete summaries to
LOG_CHANNEL_ID=
# Optional: per-guild log channel overrides (guild_id:channel_id, comma-separated)
# Listed guilds post to their own channel; everything else uses LOG_CHANNEL_ID.
LOG_CHANNELS=
# Optional: legitimate Discord bot token(s) for posting to the log channels
# (recommended, comma-separated). Each needs Send Messages + Attach Files.
# The singular LOG_POSTER_BOT_TOKEN is still accepted and merged in.
LOG_POSTER_BOT_TOKENS=
# Optional: secondary user account token(s) for posting (comma-separated).
# Posting is resolved per channel: bot posters, then user posters, then any
# main account that can see it. The singular LOG_POSTER_TOKEN still works.
LOG_POSTER_TOKENS=

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

Every 30 minutes an archive sync worker re-checks for channels that have disappeared (moved to `📁 Archived`) or become newly readable (webhook provisioned, moved to proper category), and reconciles any channel names that drifted while the bot was disconnected.

New channels and threads created after initial setup are picked up automatically via `on_guild_channel_create` and `on_thread_create`, and renames are propagated via `on_guild_channel_update`.

Send `!sync` as the main account to force a full reconciliation on demand — it runs the archive check, syncs any drifted channel names, then re-syncs ordering.

### Channel ordering

The correct order is derived from the source guild and cached in `data/cache.db`. On startup and once daily the bot:

1. Re-reads the source guild's current order and updates the cache if anything changed
2. Compares the cache to the actual dest guild state
3. If both match — nothing happens, no API calls are made
4. If the dest has drifted from the cache — it is restored
5. If the source changed — the cache is updated and the dest is brought in line

Send `!sync-order` as the main account to trigger this immediately on demand.

`🔒 Unreadable` and `📁 Archived` categories are always kept at the bottom regardless of source ordering.

### Historical backfill

Messages older than when the bot started logging aren't in `data/cache.db`, so if one of them is later deleted, the log shows `Content: <unknown>` instead of the original text. `!backfill` fixes this retroactively for a mirrored guild.

Send `!backfill` as any account **in the destination guild** (the bot resolves which source guild to backfill via `MIRROR_SERVERS`). The bot then walks that source guild's full message history — text channels and voice-channel text chats — oldest message first, and caches it into `data/cache.db` — it does not relay anything to the destination guild and does not download attachments, it only stores enough metadata to recover a message's content if it's ever deleted.

To also save the actual files, send `!backfill-with-attachments`. It does everything `!backfill` does and additionally downloads each message's attachments and stickers to `media/` (using the fresh CDN URLs it gets straight from history). Two ways to use it:

- **Fresh guild — run it alone.** It's a superset of `!backfill`: it caches the metadata *and* downloads the files in a single pass, and marks the guild fully backfilled on both counts. You don't need to run plain `!backfill` first.
- **Already ran `!backfill` — run it afterwards to fetch attachments later.** The two are independently tracked, so a completed metadata backfill doesn't stop this pass. It walks the history again (Discord's CDN URLs are signed and expire in ~24h, so the URLs cached earlier are usually dead — re-walking gets fresh ones), re-caches the metadata harmlessly, and downloads the files.

Its start message tells you which case applies — whether it's caching the full history or the history is already cached and it's mainly downloading attachments. Only one backfill (of either kind) runs at a time per source guild, and only attachments for messages still present in the source when it runs can be fetched.

When a cached message that was never relayed (i.e. a backfilled one) is later deleted, the delete notification posted to the mirror includes the recovered content, attachment filenames, and sticker names — since there's no mirror copy to jump to. If the attachments were downloaded, the saved files are attached to the notification too. Deletes of live-mirrored messages keep the compact "jump to mirror" link instead.

This is deliberately slow: small pages, multi-second delays between pages and between channels, one channel at a time (the attachment pass adds the downloads on top, so it's slower still). A guild with a lot of history can take a long time to fully backfill — that's intentional, to keep the request pattern conservative on a self-bot account. Progress posts to the log channel (or to the channel the command was run in, if no `LOG_CHANNEL_ID` is set) every 5 minutes, plus a summary when the whole guild is done.

Use `!backfill-status` to check progress on demand. It reports channel counts against the source guild's actual text- and voice-channel total (done / in progress / not started), the total messages cached, how many channels have had their attachments downloaded, and — for the channel currently being walked — how long ago its last checkpoint was written, so you can tell at a glance whether the walker is still advancing even if progress posts have gone quiet.

It's safe to run once and forget — channels that finish are skipped on any future run of the same pass, and if the bot restarts mid-backfill it resumes from its last checkpoint instead of starting over. The content pass and the attachment pass track their progress independently, so finishing `!backfill` doesn't stop `!backfill-with-attachments` from later walking the same channels for files. Note that a restart does **not** auto-resume the walk: send the command again after the bot comes back up.
