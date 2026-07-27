from __future__ import annotations

import re
from typing import Annotated, List, Optional
from urllib.parse import quote
from xml.etree import ElementTree

import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from pydantic import Field, ValidationError

from utils.auth import get_auth_status, get_mal_access_token, login_initiate, login_status, revoke_auth
from utils.episodes import build_watch_queue, parse_anime_calendar_events, upcoming_events_digest
from utils.mal_client import MALClient, api_error_payload, build_fields, clamp_limit
from utils.schemas import *

load_dotenv()

_MAL_NEWS_RSS_URL = "https://myanimelist.net/rss/news.xml"
_MAL_NEWS_LIMIT = 20
_TRACKING_QUERY_RE = re.compile(r"[?&]_location=rss\b")
_MEDIA_NS = "http://search.yahoo.com/mrss/"


def anime_calendar_ical_url(username: str) -> str:
    encoded_username = quote(username.strip(), safe="")
    return f"https://api.anime-calendar.com/v3/ical/myanimelist/{encoded_username}"


def normalize_episode_window(hours: int) -> int:
    return max(1, min(int(hours), 24 * 14))


def _clean_news_url(url: str | None) -> str | None:
    if url is None:
        return None
    return _TRACKING_QUERY_RE.sub("", url)


def parse_mal_news_rss(xml_text: str, limit: int) -> dict:
    root = ElementTree.fromstring(xml_text)

    channel = root.find("channel")
    if channel is None:
        return {"error": "RSS feed missing channel element"}

    articles: list[dict[str, str | None]] = []
    for item in channel.findall("item"):
        if len(articles) >= limit:
            break

        title_el = item.find("title")
        link_el = item.find("link")
        desc_el = item.find("description")
        pub_el = item.find("pubDate")
        thumb_el = item.find(f"{{{_MEDIA_NS}}}thumbnail")

        title = title_el.text if title_el is not None and title_el.text else None
        url = _clean_news_url(link_el.text) if link_el is not None else None
        description = desc_el.text if desc_el is not None and desc_el.text else None
        published = pub_el.text if pub_el is not None and pub_el.text else None
        thumbnail = thumb_el.get("url") if thumb_el is not None else None

        if title is None and url is None:
            continue

        articles.append({
            "title": title,
            "url": url,
            "description": description,
            "published": published,
            "thumbnail": thumbnail,
        })

    return {"articles": articles}


def register_tools(mcp: FastMCP):
    mal_client = MALClient()

    def client() -> MALClient:
        return mal_client

    async def token() -> str:
        access_token = await get_mal_access_token()
        if not access_token:
            raise ValueError("No valid MyAnimeList access token available")
        return access_token

    # Anime
    @mcp.tool()
    async def get_anime(q: str, limit: int = 10, offset: int = 0) -> dict:
        """Search anime on MyAnimeList."""
        try:
            return await client().get_public("/anime", params={"q": q, "limit": clamp_limit(limit, 100), "offset": max(0, offset)})
        except Exception as e:
            return api_error_payload(e)

    @mcp.tool()
    async def get_anime_details(anime_id: int, fields: Optional[List[str]] = None) -> dict:
        """Fetch anime details by MAL ID."""
        try:
            fields_param = build_fields(fields, ["id", "title", "main_picture"])
            return await client().get_public(f"/anime/{anime_id}", params={"fields": fields_param})
        except Exception as e:
            return api_error_payload(e)

    @mcp.tool()
    async def get_anime_ranking(ranking_type: AnimeRanking = AnimeRanking.ALL, limit: int = 10, offset: int = 0, fields: Optional[List[str]] = None) -> dict:
        """Fetch anime rankings from MyAnimeList."""
        try:
            params: dict[str, object] = {"limit": clamp_limit(limit, 500), "offset": max(0, offset)}
            if fields:
                params["fields"] = build_fields(fields, ["id", "title", "main_picture"])
            return await client().get_public(f"/anime/ranking/{ranking_type.value}", params=params)
        except Exception as e:
            return api_error_payload(e)

    @mcp.tool()
    async def get_seasonal_anime(season: Season, year: int, sort: Optional[SeasonSort] = None, limit: int = 10, offset: int = 0, fields: Optional[List[str]] = None) -> dict:
        """Fetch seasonal anime from MyAnimeList."""
        try:
            params: dict[str, object] = {"limit": clamp_limit(limit, 500), "offset": max(0, offset)}
            if sort:
                params["sort"] = sort.value
            if fields:
                params["fields"] = build_fields(fields, ["id", "title", "main_picture"])
            return await client().get_public(f"/anime/season/{year}/{season.value}", params=params)
        except Exception as e:
            return api_error_payload(e)

    @mcp.tool()
    async def get_anime_list(username: str, status: Optional[AnimeStatus] = None, sort: Optional[AnimeStatusSort] = None, limit: int = 10, offset: int = 0) -> dict:
        """Fetch a public MyAnimeList anime list for a user."""
        try:
            params: dict[str, object] = {"limit": clamp_limit(limit, 1000), "offset": max(0, offset)}
            if status:
                params["status"] = status.value
            if sort:
                params["sort"] = sort.value
            return await client().get_public(f"/users/{username}/animelist", params=params)
        except Exception as e:
            return api_error_payload(e)

    # Manga
    @mcp.tool()
    async def get_manga(q: str, limit: int = 10, offset: int = 0) -> dict:
        """Search manga on MyAnimeList."""
        try:
            return await client().get_public("/manga", params={"q": q, "limit": clamp_limit(limit, 100), "offset": max(0, offset)})
        except Exception as e:
            return api_error_payload(e)

    @mcp.tool()
    async def get_manga_details(manga_id: int, fields: Optional[List[str]] = None) -> dict:
        """Fetch manga details by MAL ID."""
        try:
            fields_param = build_fields(fields, ["id", "title", "main_picture"])
            return await client().get_public(f"/manga/{manga_id}", params={"fields": fields_param})
        except Exception as e:
            return api_error_payload(e)

    @mcp.tool()
    async def get_manga_ranking(ranking_type: MangaRanking, limit: int = 100, offset: int = 0, fields: Optional[List[str]] = None) -> dict:
        """Fetch manga rankings from MyAnimeList."""
        try:
            params: dict[str, object] = {"limit": clamp_limit(limit, 500), "offset": max(0, offset)}
            if fields:
                params["fields"] = build_fields(fields, ["id", "title", "main_picture"])
            return await client().get_public(f"/manga/ranking/{ranking_type.value}", params=params)
        except Exception as e:
            return api_error_payload(e)

    @mcp.tool()
    async def get_manga_list(username: str, status: Optional[MangaStatus] = None, sort: Optional[MangaStatusSort] = None, limit: int = 10, offset: int = 0) -> dict:
        """Fetch a public MyAnimeList manga list for a user."""
        try:
            params: dict[str, object] = {"limit": clamp_limit(limit, 1000), "offset": max(0, offset)}
            if status:
                params["status"] = status.value
            if sort:
                params["sort"] = sort.value
            return await client().get_public(f"/users/{username}/mangalist", params=params)
        except Exception as e:
            return api_error_payload(e)

    @mcp.tool()
    async def get_my_anime_list(status: Optional[AnimeStatus] = None, sort: Optional[AnimeStatusSort] = None, limit: int = 10, offset: int = 0, fields: Optional[List[str]] = None) -> dict:
        """Fetch the authenticated user's MyAnimeList anime list."""
        try:
            params: dict[str, object] = {"limit": clamp_limit(limit, 1000), "offset": max(0, offset)}
            if status:
                params["status"] = status.value
            if sort:
                params["sort"] = sort.value
            if fields:
                params["fields"] = build_fields(fields, ["id", "title", "main_picture"])
            return await client().get_authed("/users/@me/animelist", await token(), params=params)
        except Exception as e:
            return api_error_payload(e)

    @mcp.tool()
    async def get_my_manga_list(status: Optional[MangaStatus] = None, sort: Optional[MangaStatusSort] = None, limit: int = 10, offset: int = 0, fields: Optional[List[str]] = None) -> dict:
        """Fetch the authenticated user's MyAnimeList manga list."""
        try:
            params: dict[str, object] = {"limit": clamp_limit(limit, 1000), "offset": max(0, offset)}
            if status:
                params["status"] = status.value
            if sort:
                params["sort"] = sort.value
            if fields:
                params["fields"] = build_fields(fields, ["id", "title", "main_picture"])
            return await client().get_authed("/users/@me/mangalist", await token(), params=params)
        except Exception as e:
            return api_error_payload(e)

    # Forum
    @mcp.tool()
    async def get_forum_boards() -> dict:
        """Fetch MyAnimeList forum boards."""
        try:
            return await client().get_public("/forum/boards")
        except Exception as e:
            return api_error_payload(e)

    @mcp.tool()
    async def get_forum_topic(topic_id: int, limit: int = 100, offset: int = 0) -> dict:
        """Fetch a MyAnimeList forum topic by ID."""
        try:
            return await client().get_public(
                f"/forum/topic/{topic_id}",
                params={"limit": clamp_limit(limit, 100), "offset": max(0, offset)},
            )
        except Exception as e:
            return api_error_payload(e)

    @mcp.tool()
    async def get_forum_topics(
        board_id: Optional[int] = None,
        subboard_id: Optional[int] = None,
        limit: int = 100,
        offset: int = 0,
        sort: str = "recent",
        q: Optional[str] = None,
        topic_user_name: Optional[str] = None,
        user_name: Optional[str] = None,
    ) -> dict:
        """Fetch MyAnimeList forum topics with optional filters."""
        try:
            params: dict[str, object] = {"limit": clamp_limit(limit, 100), "offset": max(0, offset), "sort": sort}
            if board_id is not None:
                params["board_id"] = board_id
            if subboard_id is not None:
                params["subboard_id"] = subboard_id
            if q:
                params["q"] = q
            if topic_user_name:
                params["topic_user_name"] = topic_user_name
            if user_name:
                params["user_name"] = user_name
            return await client().get_public("/forum/topics", params=params)
        except Exception as e:
            return api_error_payload(e)

    # Auth/account helpers
    @mcp.tool()
    async def mal_auth_status() -> dict:
        """Check whether this MCP has stored MyAnimeList OAuth tokens."""
        return await get_auth_status()

    @mcp.tool()
    async def mal_auth_revoke() -> dict:
        """Clear locally stored MyAnimeList OAuth tokens."""
        return revoke_auth()

    @mcp.tool()
    async def mal_auth_login() -> dict:
        """Start a non-blocking MyAnimeList OAuth login and return the authorization URL."""
        return login_initiate()

    @mcp.tool()
    async def mal_auth_login_status() -> dict:
        """Check whether a MyAnimeList OAuth login is pending, completed, or not authenticated."""
        return await login_status()

    @mcp.tool()
    async def get_suggested_anime(limit: int = 10, offset: int = 0) -> dict:
        """Fetch suggested anime for the authenticated user."""
        try:
            return await client().get_authed("/anime/suggestions", await token(), params={"limit": clamp_limit(limit, 100), "offset": max(0, offset)})
        except Exception as e:
            return api_error_payload(e)

    @mcp.tool()
    async def get_user_profile(fields: Optional[str] = None) -> dict:
        """Fetch the authenticated user's MyAnimeList profile. Use fields=anime_statistics to get stats."""
        try:
            params = {"fields": fields} if fields else None
            return await client().get_authed("/users/@me", await token(), params=params)
        except Exception as e:
            return api_error_payload(e)

    @mcp.tool()
    async def delete_myanimelist_item(anime_id: int) -> dict:
        """Delete an anime from the authenticated user's MyAnimeList."""
        try:
            await client().delete_authed(f"/anime/{anime_id}/my_list_status", await token())
            return {"message": f"Anime ID {anime_id} deleted successfully"}
        except Exception as e:
            return api_error_payload(e)

    @mcp.tool()
    async def delete_mymangalist_item(manga_id: int) -> dict:
        """Delete a manga from the authenticated user's MyAnimeList."""
        try:
            await client().delete_authed(f"/manga/{manga_id}/my_list_status", await token())
            return {"message": f"Manga ID {manga_id} deleted successfully"}
        except Exception as e:
            return api_error_payload(e)

    @mcp.tool()
    async def update_myanimelist(
        anime_id: Annotated[int, Field(description="ID of the anime to update", ge=1)],
        status: Annotated[Optional[str], Field(description="Anime list status", pattern="^(watching|completed|on_hold|dropped|plan_to_watch)$")] = None,
        score: Annotated[Optional[int], Field(description="Score for the anime (0-10)", ge=0, le=10)] = None,
        num_watched_episodes: Annotated[Optional[int], Field(description="Number of episodes watched", ge=0)] = None,
        is_rewatching: Annotated[Optional[bool], Field(description="Whether the anime is being rewatched")] = None,
        priority: Annotated[Optional[int], Field(description="Priority (0-2)", ge=0, le=2)] = None,
        num_times_rewatched: Annotated[Optional[int], Field(description="Number of times rewatched", ge=0)] = None,
        rewatch_value: Annotated[Optional[int], Field(description="Rewatch value (0-5)", ge=0, le=5)] = None,
        tags: Annotated[Optional[str], Field(description="Comma-separated tags")] = None,
        comments: Annotated[Optional[str], Field(description="Comments about the anime", max_length=1000)] = None,
    ) -> dict:
        """Update an anime's status in the authenticated user's MyAnimeList."""
        try:
            fields = {
                "status": status,
                "score": score,
                "num_watched_episodes": num_watched_episodes,
                "is_rewatching": is_rewatching,
                "priority": priority,
                "num_times_rewatched": num_times_rewatched,
                "rewatch_value": rewatch_value,
                "tags": tags,
                "comments": comments,
            }
            fields = {k: v for k, v in fields.items() if v is not None}
            if not fields:
                return {"error": "At least one field must be provided to update the anime"}
            return await client().put_authed(f"/anime/{anime_id}/my_list_status", await token(), data=fields)
        except ValidationError as e:
            return {"error": f"Invalid input: {e}"}
        except Exception as e:
            return api_error_payload(e)

    @mcp.tool()
    async def update_mymangalist(
        manga_id: Annotated[int, Field(description="ID of the manga to update", ge=1)],
        status: Annotated[Optional[str], Field(description="Manga list status", pattern="^(reading|completed|on_hold|dropped|plan_to_read)$")] = None,
        is_rereading: Annotated[Optional[bool], Field(description="Whether the manga is being reread")] = None,
        score: Annotated[Optional[int], Field(description="Score for the manga (0-10)", ge=0, le=10)] = None,
        num_volumes_read: Annotated[Optional[int], Field(description="Number of volumes read", ge=0)] = None,
        num_chapters_read: Annotated[Optional[int], Field(description="Number of chapters read", ge=0)] = None,
        priority: Annotated[Optional[int], Field(description="Priority (0-2)", ge=0, le=2)] = None,
        num_times_reread: Annotated[Optional[int], Field(description="Number of times reread", ge=0)] = None,
        reread_value: Annotated[Optional[int], Field(description="Reread value (0-5)", ge=0, le=5)] = None,
        tags: Annotated[Optional[str], Field(description="Comma-separated tags")] = None,
        comments: Annotated[Optional[str], Field(description="Comments about the manga", max_length=1000)] = None,
    ) -> dict:
        """Update a manga's status in the authenticated user's MyAnimeList."""
        try:
            fields = {
                "status": status,
                "is_rereading": is_rereading,
                "score": score,
                "num_volumes_read": num_volumes_read,
                "num_chapters_read": num_chapters_read,
                "priority": priority,
                "num_times_reread": num_times_reread,
                "reread_value": reread_value,
                "tags": tags,
                "comments": comments,
            }
            fields = {k: v for k, v in fields.items() if v is not None}
            if not fields:
                return {"error": "At least one field must be provided to update the manga"}
            return await client().put_authed(f"/manga/{manga_id}/my_list_status", await token(), data=fields)
        except ValidationError as e:
            return {"error": f"Invalid input: {e}"}
        except Exception as e:
            return api_error_payload(e)

    @mcp.tool()
    async def get_upcoming_anime_episodes(username: str = "botafi", hours: int = 36) -> dict:
        """Fetch upcoming episode releases from anime-calendar.com iCal for a MAL username."""
        try:
            hours = normalize_episode_window(hours)
            url = anime_calendar_ical_url(username)
            async with httpx.AsyncClient(timeout=30) as calendar_client:
                response = await calendar_client.get(url)
                response.raise_for_status()
            return {"username": username, "hours": hours, "digest": upcoming_events_digest(response.text, hours=hours)}
        except Exception as e:
            return api_error_payload(e)

    @mcp.tool()
    async def get_watch_queue(username: str = "botafi") -> dict:
        """Build a watch queue digest from the authenticated user's 'watching' anime list and Anime Calendar iCal data.

        Returns per-anime watched episode counts against latest released episodes (from calendar or total episode metadata)
        plus aggregate totals. Latest released is unknown for titles that are neither finished nor found in the calendar feed."""
        try:
            access_token = await token()
            list_fields = "list_status{num_episodes_watched},anime{id,title,num_episodes,status}"
            list_params = {"status": "watching", "limit": 1000, "offset": 0, "fields": list_fields}
            list_response = await client().get_authed("/users/@me/animelist", access_token, params=list_params)

            url = anime_calendar_ical_url(username)
            async with httpx.AsyncClient(timeout=30) as calendar_client:
                cal_response = await calendar_client.get(url)
                cal_response.raise_for_status()
            calendar_events = parse_anime_calendar_events(cal_response.text)

            raw_data = list_response.get("data", []) if isinstance(list_response, dict) else []
            return build_watch_queue(raw_data, calendar_events)
        except Exception as e:
            return api_error_payload(e)

    @mcp.tool()
    async def get_mal_news(limit: int = 10) -> dict:
        """Fetch recent anime/manga news articles from MyAnimeList RSS feed."""
        try:
            limit = clamp_limit(limit, _MAL_NEWS_LIMIT)
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(_MAL_NEWS_RSS_URL)
                response.raise_for_status()
            return parse_mal_news_rss(response.text, limit)
        except Exception as e:
            return api_error_payload(e)
