from utils.episodes import parse_anime_calendar_events, upcoming_events_digest


def test_parse_anime_calendar_events_extracts_episode_metadata():
    ical = """BEGIN:VCALENDAR\r
BEGIN:VEVENT\r
DTSTART:20260525T133000Z\r
SUMMARY:[org] Isekai Nonbiri Nouka 2 (8)\r
DESCRIPTION:Link: https://myanimelist.net/anime/62146\r
UID:abc@anime-calendar.com\r
END:VEVENT\r
END:VCALENDAR\r
"""

    events = parse_anime_calendar_events(ical)

    assert len(events) == 1
    assert events[0].title == "Isekai Nonbiri Nouka 2"
    assert events[0].episode == 8
    assert events[0].mal_id == 62146
    assert events[0].stream_type == "org"


def test_upcoming_events_digest_filters_to_window():
    ical = """BEGIN:VCALENDAR\nBEGIN:VEVENT\nDTSTART:20260525T133000Z\nSUMMARY:[sub] Show A (1)\nDESCRIPTION:Link: https://myanimelist.net/anime/1\nEND:VEVENT\nBEGIN:VEVENT\nDTSTART:20260725T133000Z\nSUMMARY:[sub] Show B (9)\nDESCRIPTION:Link: https://myanimelist.net/anime/2\nEND:VEVENT\nEND:VCALENDAR\n"""

    digest = upcoming_events_digest(ical, now_iso="2026-05-24T00:00:00+00:00", hours=72)

    assert "Show A ep 1" in digest
    assert "Show B" not in digest
