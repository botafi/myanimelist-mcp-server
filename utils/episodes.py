from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass(frozen=True)
class CalendarEpisodeEvent:
    title: str
    episode: int | None
    starts_at: datetime
    mal_id: int | None
    stream_type: str | None = None


@dataclass(frozen=True)
class WatchQueueEntry:
    title: str
    mal_id: int
    watched_count: int
    latest_released_count: int | None
    unwatched_count: int | None
    status: str


_DT_FORMATS = ("%Y%m%dT%H%M%SZ", "%Y%m%dT%H%M%S")
_SUMMARY_RE = re.compile(r"^(?:\[(?P<stream>[^\]]+)\]\s*)?(?P<title>.*?)(?:\s*\((?P<episode>\d+)\))?$")
_MAL_RE = re.compile(r"myanimelist\.net/anime/(?P<id>\d+)")


def _parse_dt(value: str) -> datetime:
    value = value.strip()
    for fmt in _DT_FORMATS:
        try:
            dt = datetime.strptime(value, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    raise ValueError(f"Unsupported iCal DTSTART format: {value}")


def _unescape(value: str) -> str:
    return value.replace("\\n", "\n").replace("\\,", ",").replace("\\;", ";").strip()


def _events(raw_ical: str) -> list[dict[str, str]]:
    lines = raw_ical.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    unfolded: list[str] = []
    for line in lines:
        if line.startswith((" ", "\t")) and unfolded:
            unfolded[-1] += line[1:]
        else:
            unfolded.append(line)

    out: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for line in unfolded:
        if line == "BEGIN:VEVENT":
            current = {}
            continue
        if line == "END:VEVENT":
            if current:
                out.append(current)
            current = None
            continue
        if current is None or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.split(";", 1)[0]
        current[key] = _unescape(value)
    return out


def parse_anime_calendar_events(raw_ical: str) -> list[CalendarEpisodeEvent]:
    parsed: list[CalendarEpisodeEvent] = []
    for event in _events(raw_ical):
        if "DTSTART" not in event or "SUMMARY" not in event:
            continue
        match = _SUMMARY_RE.match(event["SUMMARY"])
        if not match:
            continue
        desc = event.get("DESCRIPTION", "")
        mal_match = _MAL_RE.search(desc)
        episode = match.group("episode")
        parsed.append(
            CalendarEpisodeEvent(
                title=match.group("title").strip(),
                episode=int(episode) if episode else None,
                starts_at=_parse_dt(event["DTSTART"]),
                mal_id=int(mal_match.group("id")) if mal_match else None,
                stream_type=match.group("stream"),
            )
        )
    return sorted(parsed, key=lambda item: item.starts_at)


def upcoming_events_digest(raw_ical: str, *, now_iso: str | None = None, hours: int = 36) -> str:
    now = datetime.now(timezone.utc) if now_iso is None else datetime.fromisoformat(now_iso)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    end = now + timedelta(hours=hours)
    events = [event for event in parse_anime_calendar_events(raw_ical) if now <= event.starts_at <= end]
    if not events:
        return f"No scheduled anime episodes in the next {hours} hours."

    lines = [f"Scheduled anime episodes in the next {hours} hours:"]
    for event in events:
        ep = f" ep {event.episode}" if event.episode is not None else ""
        stream = f" [{event.stream_type}]" if event.stream_type else ""
        mal = f" — MAL {event.mal_id}" if event.mal_id is not None else ""
        lines.append(f"- {event.title}{ep}{stream} at {event.starts_at.isoformat().replace('+00:00', 'Z')}{mal}")
    return "\n".join(lines)


def _resolve_latest_episode(
    node: dict,
    calendar_by_mal_id: dict[int, list[CalendarEpisodeEvent]],
    now: datetime,
) -> int | None:
    status = node.get("status", "") or ""
    num_episodes = node.get("num_episodes", 0) or 0
    mal_id = node.get("id")

    if status == "finished_airing" and num_episodes > 0:
        return num_episodes

    if status == "not_yet_aired":
        return 0

    if mal_id and mal_id in calendar_by_mal_id:
        events = calendar_by_mal_id[mal_id]
        past_events = [e for e in events if e.episode is not None and e.starts_at <= now]
        if past_events:
            return max(e.episode for e in past_events)

        upcoming = sorted(
            [e.episode for e in events if e.episode is not None and e.starts_at > now]
        )
        if upcoming:
            min_ep = upcoming[0]
            return 0 if min_ep <= 1 else min_ep - 1

    return None


def build_watch_queue(
    anime_list_data: list[dict],
    calendar_events: list[CalendarEpisodeEvent],
    *,
    now: datetime | None = None,
) -> dict:
    if now is None:
        now = datetime.now(timezone.utc)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    calendar_by_mal_id: dict[int, list[CalendarEpisodeEvent]] = {}
    for event in calendar_events:
        if event.mal_id is not None:
            calendar_by_mal_id.setdefault(event.mal_id, []).append(event)

    entries: list[WatchQueueEntry] = []
    total_watched = 0
    total_unwatched_calculable = 0
    unknown_latest_count = 0

    for item in anime_list_data:
        node = item.get("node", {})
        list_status = item.get("list_status", {})

        mal_id = node.get("id", 0) or 0
        title = node.get("title", "Unknown") or "Unknown"
        status = node.get("status", "") or ""
        watched = list_status.get("num_episodes_watched", 0) or 0
        total_watched += watched

        latest = _resolve_latest_episode(node, calendar_by_mal_id, now)

        if latest is None:
            unwatched = None
            unknown_latest_count += 1
        else:
            unwatched = max(0, latest - watched)
            total_unwatched_calculable += unwatched

        entries.append(WatchQueueEntry(
            title=title,
            mal_id=mal_id,
            watched_count=watched,
            latest_released_count=latest,
            unwatched_count=unwatched,
            status=status,
        ))

    entries.sort(key=lambda e: (
        0 if e.unwatched_count is not None else 1,
        -(e.unwatched_count or 0),
        e.title.lower(),
    ))

    return {
        "entries": [
            {
                "title": entry.title,
                "mal_id": entry.mal_id,
                "watched_count": entry.watched_count,
                "latest_released_count": entry.latest_released_count,
                "unwatched_count": entry.unwatched_count,
                "status": entry.status,
            }
            for entry in entries
        ],
        "aggregate": {
            "total_watching": len(entries),
            "total_watched_episodes": total_watched,
            "total_unwatched_calculable": total_unwatched_calculable,
            "total_unknown_latest_count": unknown_latest_count,
        },
    }
