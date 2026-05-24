import sqlite3
import re
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = Path("data/cache.db")
LOGS_DIR = Path("logs")

NEW_PATTERN = re.compile(
    r'^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} UTC)\] \[NEW\] (.+?) \((\d+)\) in '
)
DELETE_PATTERN = re.compile(
    r'^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} UTC\] \[(?:DELETE|DELETE-MISSED|BULK-DELETE)\] (.+?) \((\d+)\) in '
)


def main() -> None:
    db = sqlite3.connect(DB_PATH)

    counts: dict[int, dict] = {}

    log_files = sorted(
        f for f in LOGS_DIR.rglob("*.log")
        if f.name not in ("discord.log",) and not f.name.startswith("discord.log.")
    )
    print(f"Scanning {len(log_files)} log files…")

    for log_file in log_files:
        try:
            with open(log_file, encoding="utf-8", errors="replace") as f:
                for line in f:
                    m = NEW_PATTERN.match(line)
                    if m:
                        ts_str, author, author_id_str = m.group(1), m.group(2), m.group(3)
                        author_id = int(author_id_str)
                        dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S UTC").replace(
                            tzinfo=timezone.utc
                        )
                        ts_iso = dt.isoformat()
                        if author_id not in counts:
                            counts[author_id] = {
                                "author": author,
                                "count": 0,
                                "deleted_count": 0,
                                "first_seen": ts_iso,
                            }
                        counts[author_id]["count"] += 1
                        if ts_iso < counts[author_id]["first_seen"]:
                            counts[author_id]["first_seen"] = ts_iso
                        counts[author_id]["author"] = author
                        continue

                    d = DELETE_PATTERN.match(line)
                    if d:
                        author, author_id_str = d.group(1), d.group(2)
                        author_id = int(author_id_str)
                        if author_id not in counts:
                            counts[author_id] = {
                                "author": author,
                                "count": 0,
                                "deleted_count": 0,
                                "first_seen": datetime.now(timezone.utc).isoformat(),
                            }
                        counts[author_id]["deleted_count"] += 1
                        counts[author_id]["author"] = author
        except Exception as e:
            print(f"  Error reading {log_file}: {e}")

    db.execute("DELETE FROM message_counts")
    for author_id, data in counts.items():
        db.execute(
            "INSERT INTO message_counts (author_id, author, count, deleted_count, first_seen) VALUES (?, ?, ?, ?, ?)",
            (author_id, data["author"], data["count"], data["deleted_count"], data["first_seen"]),
        )
    db.commit()

    total = sum(d["count"] for d in counts.values())
    total_deleted = sum(d["deleted_count"] for d in counts.values())
    print(f"Done — {len(counts)} users, {total:,} messages, {total_deleted:,} deleted")
    db.close()


if __name__ == "__main__":
    main()
