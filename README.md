# MyAnimeList MCP Server

MCP server for interacting with the MyAnimeList API from Hermes, Claude Desktop, and other MCP clients. This fork focuses on safer unattended usage for anime-list maintenance and episode-release digests.

## What this fork adds

- Persistent OAuth token storage with private file permissions (`0600`).
- Refresh-token persistence so unattended jobs do not need to re-auth every run.
- Safer error messages that avoid returning raw API response bodies or bearer tokens.
- Small MyAnimeList API client wrapper with request timeout and basic request pacing.
- Auth helper tools: `mal_auth_status`, `mal_auth_revoke`.
- Episode schedule helper: `get_upcoming_anime_episodes`, backed by `https://api.anime-calendar.com/v3/ical/myanimelist/<username>`.
- Tests for token storage, API helper behavior, and iCal episode parsing.

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
MAL_RATE_LIMIT_DELAY=0.35
# Optional token path. Default: $HERMES_HOME/secrets/mal_tokens.json, or ~/.hermes/secrets/mal_tokens.json
MAL_TOKEN_STORAGE_PATH=/opt/data/.hermes/secrets/mal_tokens.json
```

Secrets must stay local. Do not commit `.env` or token files.

## Running manually

```bash
uv run main.py
```

The first authenticated tool call opens the MAL OAuth URL and starts a one-shot callback server on `localhost:8080`. After authorization, tokens are stored locally and refreshed automatically.

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
- `get_anime_list`: fetch a user's public anime list.
- `get_suggested_anime`: **auth required**; fetch recommendations for the authenticated user.
- `update_myanimelist`: **auth required**; update an anime list entry.
- `delete_myanimelist_item`: **auth required**; delete an anime list entry.

### Manga

- `get_manga`: search manga.
- `get_manga_details`: fetch manga details by MAL ID.
- `get_manga_ranking`: fetch manga rankings.
- `get_manga_list`: fetch a user's public manga list.
- `update_mymangalist`: **auth required**; update a manga list entry.
- `delete_mymangalist_item`: **auth required**; delete a manga list entry.

### User/auth

- `get_user_profile`: **auth required**; fetch current user profile.
- `mal_auth_status`: inspect local OAuth token status without exposing token values.
- `mal_auth_revoke`: delete locally stored OAuth tokens.

### Episode schedule

- `get_upcoming_anime_episodes`: fetch upcoming episodes for a MAL username from Anime Calendar iCal and return a digest.

## Tests

```bash
uv run --with pytest pytest -q
```

## Useful resources

- <https://myanimelist.net/apiconfig/references/authorization>
- <https://myanimelist.net/apiconfig/references/api/v2>
- <https://github.com/DerFrZocker/anime-calendar-server>
