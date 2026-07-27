# MyAnimeList MCP Server

MCP server for interacting with the MyAnimeList API from Hermes, Claude Desktop, and other MCP clients. This fork focuses on safer unattended usage for anime-list maintenance and episode-release digests.

## What this fork adds

- Persistent OAuth token storage with private file permissions (`0600`).
- Refresh-token persistence so unattended jobs do not need to re-auth every run.
- Safer error messages that avoid returning raw API response bodies or bearer tokens.
- Small MyAnimeList API client wrapper with request timeout and basic request pacing.
- Auth helper tools: `mal_auth_login`, `mal_auth_login_status`, `mal_auth_status`, `mal_auth_revoke`.
- Episode schedule helper: `get_upcoming_anime_episodes`, backed by `https://api.anime-calendar.com/v3/ical/myanimelist/<username>`.
- Watch queue helper: `get_watch_queue`, combines authenticated `watching` list with Anime Calendar iCal data to show per-anime watched vs latest released counts.
- News RSS helper: `get_mal_news`, backed by `https://myanimelist.net/rss/news.xml`.
- Tests for token storage, API helper behavior, iCal episode parsing, and RSS news parsing.

## Requirements

- Python `>=3.12`
- [`uv`](https://docs.astral.sh/uv/)
- A MyAnimeList API client from <https://myanimelist.net/apiconfig>

Use app type **web** and redirect URL:

```text
http://localhost:8080/callback
```

## Configuration

Create `.env` or set environment variables:

```bash
MAL_CLIENT_ID=your_client_id
MAL_CLIENT_SECRET=your_client_secret
# Optional; defaults shown:
MAL_REDIRECT_URI=http://localhost:8080/callback
MAL_CALLBACK_HOST=127.0.0.1
MAL_CALLBACK_PORT=8080
MAL_CALLBACK_TIMEOUT_SECONDS=300
MAL_PKCE_METHOD=plain
MAL_RATE_LIMIT_DELAY=0.35
# Optional token path. Default: $HERMES_HOME/secrets/mal_tokens.json, or ~/.hermes/secrets/mal_tokens.json
MAL_TOKEN_STORAGE_PATH=/opt/data/.hermes/secrets/mal_tokens.json
```

Secrets must stay local. Do not commit `.env` or token files.

## Running manually

```bash
uv run main.py
```

Run the `mal_auth_login` tool to start a one-shot callback server and receive a MyAnimeList OAuth URL. Open that URL in a browser you can access, approve the app, then run `mal_auth_login_status` until it reports `authenticated`. After authorization, tokens are stored locally and refreshed automatically.

MyAnimeList OAuth uses PKCE. This server defaults `MAL_PKCE_METHOD` to `plain`, which matches MyAnimeList compatibility. Set it to `S256` only if your MyAnimeList app/API behavior explicitly supports it.

`MAL_CALLBACK_HOST` defaults to `127.0.0.1` for safety. If the MCP server runs inside Docker and the callback must be reached through a published Docker/Tailscale port, set `MAL_CALLBACK_HOST=0.0.0.0` and make sure `MAL_REDIRECT_URI` exactly matches a redirect URL registered in the MyAnimeList app settings.

## Hermes MCP setup

From the Hermes runtime/container:

```bash
hermes mcp add myanimelist --command "uv --directory /opt/data/projects/myanimelist-mcp-server run main.py"
hermes mcp test myanimelist
```

If Hermes is managed via Docker, persist this repository and the token path as mounted volumes. The token file should remain private to the container/user running Hermes.

## Available tools

### Anime

- `get_anime`: search anime.
- `get_anime_details`: fetch anime details by MAL ID.
- `get_anime_ranking`: fetch anime rankings.
- `get_seasonal_anime`: fetch anime by year/season.
- `get_anime_list`: fetch a user's public anime list (status filter optional).
- `get_my_anime_list`: **auth required**; fetch the authenticated user's anime list.
- `get_suggested_anime`: **auth required**; fetch recommendations for the authenticated user.
- `update_myanimelist`: **auth required**; update an anime list entry.
- `delete_myanimelist_item`: **auth required**; delete an anime list entry.

### Manga

- `get_manga`: search manga.
- `get_manga_details`: fetch manga details by MAL ID.
- `get_manga_ranking`: fetch manga rankings.
- `get_manga_list`: fetch a user's public manga list (status filter optional).
- `get_my_manga_list`: **auth required**; fetch the authenticated user's manga list.
- `update_mymangalist`: **auth required**; update a manga list entry.
- `delete_mymangalist_item`: **auth required**; delete a manga list entry.

### Forum

- `get_forum_boards`: fetch all MAL forum boards.
- `get_forum_topic`: fetch a forum topic by ID.
- `get_forum_topics`: fetch forum topics with optional filters (board_id, subboard_id, search, user).

### User/auth

- `get_user_profile`: **auth required**; fetch current user profile.
- `mal_auth_login`: start OAuth and return an authorization URL for headless/server setups.
- `mal_auth_login_status`: check whether the OAuth callback completed and tokens were stored.
- `mal_auth_status`: inspect local OAuth token status without exposing token values.
- `mal_auth_revoke`: delete locally stored OAuth tokens.

### Episode schedule / watch queue

- `get_upcoming_anime_episodes`: fetch upcoming episodes for a MAL username from Anime Calendar iCal and return a digest.
- `get_watch_queue`: **auth required**; combines the authenticated user's `watching` anime list with Anime Calendar iCal data to return per-title watched episodes versus latest released episodes, plus aggregate counts. Latest released is determined from calendar events (highest past episode or next upcoming minus one) and falls back to `num_episodes` for finished shows. Unknown when neither source is available.

### News

- `get_mal_news`: fetch recent anime/manga news articles from the MyAnimeList RSS feed.

## Tests

```bash
uv run --with pytest pytest -q
```

## Useful resources

- <https://myanimelist.net/apiconfig/references/authorization>
- <https://myanimelist.net/apiconfig/references/api/v2>
- <https://github.com/DerFrZocker/anime-calendar-server>
