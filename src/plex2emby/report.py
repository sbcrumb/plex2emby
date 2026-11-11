"""The CSV written after every Migration Run."""

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from plex2emby.models import WatchState

WOULD_CHANGE = "would-change"
CHANGED = "changed"
UNMATCHED = "unmatched"
FAILED = "failed"

STATE_FIELDS = ("played", "play_count", "last_played", "resume_ticks")
COLUMNS = (
    "status",
    "library",
    "title",
    "change",
    "emby_id",
    *(f"old_{f}" for f in STATE_FIELDS),
    *(f"new_{f}" for f in STATE_FIELDS),
    "reason",
)


@dataclass(frozen=True)
class ReportRow:
    status: str
    library: str
    title: str
    emby_id: str = ""
    old: WatchState | None = None
    new: WatchState | None = None
    reason: str = ""


def _cells(prefix: str, state: WatchState | None) -> dict[str, object]:
    if state is None:
        return {}
    date = state.last_played.isoformat() if state.last_played else ""
    return {
        f"{prefix}_played": state.played,
        f"{prefix}_play_count": state.play_count,
        f"{prefix}_last_played": date,
        f"{prefix}_resume_ticks": state.resume_ticks,
    }


TICKS_PER_MINUTE = 600_000_000
_ORDER = {UNMATCHED: 0, FAILED: 0}


def describe_change(row: ReportRow) -> str:
    """A plain-English summary of what the row changes, for people reading the CSV."""
    if row.status in (UNMATCHED, FAILED) or row.new is None:
        return row.reason
    old = row.old or WatchState()
    parts = []
    if old.played != row.new.played:
        parts.append("marked played" if row.new.played else "marked unplayed")
    if old.play_count != row.new.play_count:
        parts.append(f"plays {old.play_count} -> {row.new.play_count}")
    if row.new.last_played and old.last_played != row.new.last_played:
        parts.append(f"last played {row.new.last_played:%Y-%m-%d}")
    if old.resume_ticks != row.new.resume_ticks:
        parts.append(
            f"resume {old.resume_ticks // TICKS_PER_MINUTE} -> "
            f"{row.new.resume_ticks // TICKS_PER_MINUTE} min"
        )
    return "; ".join(parts)


def write_report(rows: list[ReportRow], directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"migration-{datetime.now():%Y%m%d-%H%M%S}.csv"
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        for row in sorted(rows, key=lambda r: (_ORDER.get(r.status, 1), r.library, r.title)):
            writer.writerow(
                {
                    "status": row.status,
                    "library": row.library,
                    "title": row.title,
                    "change": describe_change(row),
                    "emby_id": row.emby_id,
                    "reason": row.reason,
                    **_cells("old", row.old),
                    **_cells("new", row.new),
                }
            )
    return path
