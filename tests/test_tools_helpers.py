from tools.tools import normalize_episode_window, anime_calendar_ical_url


def test_anime_calendar_ical_url_encodes_username():
    assert anime_calendar_ical_url("bot afi/日本") == "https://api.anime-calendar.com/v3/ical/myanimelist/bot%20afi%2F%E6%97%A5%E6%9C%AC"


def test_normalize_episode_window_clamps_to_positive_reasonable_range():
    assert normalize_episode_window(-5) == 1
    assert normalize_episode_window(0) == 1
    assert normalize_episode_window(36) == 36
    assert normalize_episode_window(24 * 30) == 24 * 14
