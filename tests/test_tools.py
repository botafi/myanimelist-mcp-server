import pytest
from unittest.mock import AsyncMock, Mock, patch
from xml.etree.ElementTree import ParseError

from utils.schemas import AnimeRanking, AnimeStatus, AnimeStatusSort, MangaRanking, MangaStatus, MangaStatusSort, Season
from utils.mal_client import MALAPIError
from tools.tools import register_tools, normalize_episode_window, anime_calendar_ical_url, parse_mal_news_rss


class TestToolRegistration:
    def test_all_tools_register(self):
        from mcp.server.fastmcp import FastMCP

        mcp = FastMCP("test")
        with patch("tools.tools.MALClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value = mock_client
            register_tools(mcp)

        tools = mcp._tool_manager.list_tools()
        names = {t.name for t in tools}
        assert "get_anime" in names
        assert "get_anime_details" in names
        assert "get_anime_ranking" in names
        assert "get_seasonal_anime" in names
        assert "get_anime_list" in names
        assert "get_manga" in names
        assert "get_manga_details" in names
        assert "get_manga_ranking" in names
        assert "get_manga_list" in names
        assert "get_my_anime_list" in names
        assert "get_my_manga_list" in names
        assert "get_forum_boards" in names
        assert "get_forum_topic" in names
        assert "get_forum_topics" in names
        assert "mal_auth_status" in names
        assert "mal_auth_revoke" in names
        assert "mal_auth_login" in names
        assert "mal_auth_login_status" in names
        assert "get_suggested_anime" in names
        assert "get_user_profile" in names
        assert "delete_myanimelist_item" in names
        assert "delete_mymangalist_item" in names
        assert "update_myanimelist" in names
        assert "update_mymangalist" in names
        assert "get_upcoming_anime_episodes" in names
        assert "get_watch_queue" in names
        assert "get_mal_news" in names
        assert len(names) == 27

    def test_get_anime_list_status_is_optional_in_schema(self):
        from mcp.server.fastmcp import FastMCP

        mcp = FastMCP("test")
        with patch("tools.tools.MALClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value = mock_client
            register_tools(mcp)

        tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "get_anime_list")
        required = tool.parameters.get("required") or []
        assert "status" not in required

    def test_get_manga_list_status_is_optional_in_schema(self):
        from mcp.server.fastmcp import FastMCP

        mcp = FastMCP("test")
        with patch("tools.tools.MALClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value = mock_client
            register_tools(mcp)

        tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "get_manga_list")
        required = tool.parameters.get("required") or []
        assert "status" not in required

    def test_get_anime_list_omit_status_when_none(self):
        from mcp.server.fastmcp import FastMCP

        mcp = FastMCP("test")
        with patch("tools.tools.MALClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get_public = AsyncMock(return_value={"data": []})
            mock_client_cls.return_value = mock_client
            register_tools(mcp)

        import asyncio
        tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "get_anime_list")
        asyncio.run(tool.fn("testuser", None, None, 5, 0))

        call_args = mock_client.get_public.call_args
        assert call_args is not None
        params = call_args.kwargs["params"]
        assert "status" not in params
        assert params["limit"] == 5

    def test_get_manga_list_omit_status_when_none(self):
        from mcp.server.fastmcp import FastMCP

        mcp = FastMCP("test")
        with patch("tools.tools.MALClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get_public = AsyncMock(return_value={"data": []})
            mock_client_cls.return_value = mock_client
            register_tools(mcp)

        import asyncio
        tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "get_manga_list")
        asyncio.run(tool.fn("testuser", None, None, 5, 0))

        params = mock_client.get_public.call_args.kwargs["params"]
        assert "status" not in params
        assert params["limit"] == 5

    def test_get_anime_list_limit_clamped_to_1000(self):
        from mcp.server.fastmcp import FastMCP

        mcp = FastMCP("test")
        with patch("tools.tools.MALClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get_public = AsyncMock(return_value={"data": []})
            mock_client_cls.return_value = mock_client
            register_tools(mcp)

        import asyncio
        tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "get_anime_list")
        asyncio.run(tool.fn("testuser", None, None, 2000, 0))

        params = mock_client.get_public.call_args.kwargs["params"]
        assert params["limit"] == 1000

    def test_get_manga_list_limit_clamped_to_1000(self):
        from mcp.server.fastmcp import FastMCP

        mcp = FastMCP("test")
        with patch("tools.tools.MALClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get_public = AsyncMock(return_value={"data": []})
            mock_client_cls.return_value = mock_client
            register_tools(mcp)

        import asyncio
        tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "get_manga_list")
        asyncio.run(tool.fn("testuser", None, None, 2000, 0))

        params = mock_client.get_public.call_args.kwargs["params"]
        assert params["limit"] == 1000

    def test_get_anime_ranking_accepts_fields(self):
        from mcp.server.fastmcp import FastMCP

        mcp = FastMCP("test")
        with patch("tools.tools.MALClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get_public = AsyncMock(return_value={"data": []})
            mock_client_cls.return_value = mock_client
            register_tools(mcp)

        import asyncio
        tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "get_anime_ranking")
        asyncio.run(tool.fn(AnimeRanking.ALL, 10, 0, ["id", "title", "rank"]))

        call_args = mock_client.get_public.call_args
        assert call_args is not None
        assert "fields" in call_args.kwargs["params"]
        assert "rank" in call_args.kwargs["params"]["fields"]

    def test_get_seasonal_anime_accepts_fields(self):
        from mcp.server.fastmcp import FastMCP

        mcp = FastMCP("test")
        with patch("tools.tools.MALClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get_public = AsyncMock(return_value={"data": []})
            mock_client_cls.return_value = mock_client
            register_tools(mcp)

        import asyncio
        tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "get_seasonal_anime")
        asyncio.run(tool.fn(Season.SUMMER, 2024, None, 10, 0, ["id", "title"]))

        call_args = mock_client.get_public.call_args
        assert call_args is not None
        assert "fields" in call_args.kwargs["params"]

    def test_get_manga_ranking_accepts_fields(self):
        from mcp.server.fastmcp import FastMCP

        mcp = FastMCP("test")
        with patch("tools.tools.MALClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get_public = AsyncMock(return_value={"data": []})
            mock_client_cls.return_value = mock_client
            register_tools(mcp)

        import asyncio
        tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "get_manga_ranking")
        asyncio.run(tool.fn(MangaRanking.ALL, 100, 0, ["id", "title", "rank"]))

        call_args = mock_client.get_public.call_args
        assert call_args is not None
        assert "fields" in call_args.kwargs["params"]

    def test_get_forum_boards_calls_correct_endpoint(self):
        from mcp.server.fastmcp import FastMCP

        mcp = FastMCP("test")
        with patch("tools.tools.MALClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get_public = AsyncMock(return_value={"data": []})
            mock_client_cls.return_value = mock_client
            register_tools(mcp)

        import asyncio
        tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "get_forum_boards")
        asyncio.run(tool.fn())

        mock_client.get_public.assert_called_once_with("/forum/boards")

    def test_get_forum_topic_calls_correct_endpoint(self):
        from mcp.server.fastmcp import FastMCP

        mcp = FastMCP("test")
        with patch("tools.tools.MALClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get_public = AsyncMock(return_value={"data": []})
            mock_client_cls.return_value = mock_client
            register_tools(mcp)

        import asyncio
        tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "get_forum_topic")
        asyncio.run(tool.fn(481, 50, 0))

        call_args = mock_client.get_public.call_args
        assert call_args.args[0] == "/forum/topic/481"
        assert call_args.kwargs["params"]["limit"] == 50

    def test_get_forum_topics_calls_correct_endpoint(self):
        from mcp.server.fastmcp import FastMCP

        mcp = FastMCP("test")
        with patch("tools.tools.MALClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get_public = AsyncMock(return_value={"data": []})
            mock_client_cls.return_value = mock_client
            register_tools(mcp)

        import asyncio
        tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "get_forum_topics")
        asyncio.run(tool.fn(1, 2, 10, 0, "recent", "love", None, None))

        call_args = mock_client.get_public.call_args
        assert call_args.args[0] == "/forum/topics"
        params = call_args.kwargs["params"]
        assert params["board_id"] == 1
        assert params["subboard_id"] == 2
        assert params["q"] == "love"
        assert params["limit"] == 10

    def test_get_forum_topics_omits_optional_params_when_none(self):
        from mcp.server.fastmcp import FastMCP

        mcp = FastMCP("test")
        with patch("tools.tools.MALClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get_public = AsyncMock(return_value={"data": []})
            mock_client_cls.return_value = mock_client
            register_tools(mcp)

        import asyncio
        tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "get_forum_topics")
        asyncio.run(tool.fn(None, None, 100, 0, "recent", None, None, None))

        params = mock_client.get_public.call_args.kwargs["params"]
        assert "board_id" not in params
        assert "subboard_id" not in params
        assert "q" not in params
        assert "topic_user_name" not in params
        assert "user_name" not in params
        assert params["sort"] == "recent"
        assert params["limit"] == 100

    def test_ranking_fields_not_in_params_when_none(self):
        from mcp.server.fastmcp import FastMCP

        mcp = FastMCP("test")
        with patch("tools.tools.MALClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get_public = AsyncMock(return_value={"data": []})
            mock_client_cls.return_value = mock_client
            register_tools(mcp)

        import asyncio
        tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "get_anime_ranking")
        asyncio.run(tool.fn(AnimeRanking.ALL, 5, 0, None))

        params = mock_client.get_public.call_args.kwargs["params"]
        assert "fields" not in params

    def test_get_my_anime_list_endpoint_path(self):
        from mcp.server.fastmcp import FastMCP

        mcp = FastMCP("test")
        with patch("tools.tools.MALClient") as mock_client_cls, patch("tools.tools.get_mal_access_token", new=AsyncMock(return_value="test-token")):
            mock_client = AsyncMock()
            mock_client.get_authed = AsyncMock(return_value={"data": []})
            mock_client_cls.return_value = mock_client
            register_tools(mcp)

            import asyncio
            tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "get_my_anime_list")
            asyncio.run(tool.fn(None, None, 10, 0, None))

            mock_client.get_authed.assert_called_once()
            assert mock_client.get_authed.call_args.args[0] == "/users/@me/animelist"

    def test_get_my_manga_list_endpoint_path(self):
        from mcp.server.fastmcp import FastMCP

        mcp = FastMCP("test")
        with patch("tools.tools.MALClient") as mock_client_cls, patch("tools.tools.get_mal_access_token", new=AsyncMock(return_value="test-token")):
            mock_client = AsyncMock()
            mock_client.get_authed = AsyncMock(return_value={"data": []})
            mock_client_cls.return_value = mock_client
            register_tools(mcp)

            import asyncio
            tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "get_my_manga_list")
            asyncio.run(tool.fn(None, None, 10, 0, None))

            mock_client.get_authed.assert_called_once()
            assert mock_client.get_authed.call_args.args[0] == "/users/@me/mangalist"

    def test_get_my_anime_list_uses_authenticated_token(self):
        from mcp.server.fastmcp import FastMCP

        mcp = FastMCP("test")
        with patch("tools.tools.MALClient") as mock_client_cls, patch("tools.tools.get_mal_access_token", new=AsyncMock(return_value="test-token")):
            mock_client = AsyncMock()
            mock_client.get_authed = AsyncMock(return_value={"data": []})
            mock_client_cls.return_value = mock_client
            register_tools(mcp)

            import asyncio
            tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "get_my_anime_list")
            asyncio.run(tool.fn(None, None, 10, 0, None))

            assert mock_client.get_authed.call_args.args[1] == "test-token"

    def test_get_my_manga_list_uses_authenticated_token(self):
        from mcp.server.fastmcp import FastMCP

        mcp = FastMCP("test")
        with patch("tools.tools.MALClient") as mock_client_cls, patch("tools.tools.get_mal_access_token", new=AsyncMock(return_value="test-token")):
            mock_client = AsyncMock()
            mock_client.get_authed = AsyncMock(return_value={"data": []})
            mock_client_cls.return_value = mock_client
            register_tools(mcp)

            import asyncio
            tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "get_my_manga_list")
            asyncio.run(tool.fn(None, None, 10, 0, None))

            assert mock_client.get_authed.call_args.args[1] == "test-token"

    def test_get_my_anime_list_limit_clamped_to_1000(self):
        from mcp.server.fastmcp import FastMCP

        mcp = FastMCP("test")
        with patch("tools.tools.MALClient") as mock_client_cls, patch("tools.tools.get_mal_access_token", new=AsyncMock(return_value="test-token")):
            mock_client = AsyncMock()
            mock_client.get_authed = AsyncMock(return_value={"data": []})
            mock_client_cls.return_value = mock_client
            register_tools(mcp)

            import asyncio
            tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "get_my_anime_list")
            asyncio.run(tool.fn(None, None, 2000, 0, None))

            params = mock_client.get_authed.call_args.kwargs["params"]
            assert params["limit"] == 1000

    def test_get_my_manga_list_limit_clamped_to_1000(self):
        from mcp.server.fastmcp import FastMCP

        mcp = FastMCP("test")
        with patch("tools.tools.MALClient") as mock_client_cls, patch("tools.tools.get_mal_access_token", new=AsyncMock(return_value="test-token")):
            mock_client = AsyncMock()
            mock_client.get_authed = AsyncMock(return_value={"data": []})
            mock_client_cls.return_value = mock_client
            register_tools(mcp)

            import asyncio
            tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "get_my_manga_list")
            asyncio.run(tool.fn(None, None, 2000, 0, None))

            params = mock_client.get_authed.call_args.kwargs["params"]
            assert params["limit"] == 1000

    def test_get_my_anime_list_with_status_and_sort(self):
        from mcp.server.fastmcp import FastMCP

        mcp = FastMCP("test")
        with patch("tools.tools.MALClient") as mock_client_cls, patch("tools.tools.get_mal_access_token", new=AsyncMock(return_value="test-token")):
            mock_client = AsyncMock()
            mock_client.get_authed = AsyncMock(return_value={"data": []})
            mock_client_cls.return_value = mock_client
            register_tools(mcp)

            import asyncio
            tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "get_my_anime_list")
            asyncio.run(tool.fn(AnimeStatus.COMPLETED, AnimeStatusSort.ANIME_TITLE, 25, 10, None))

            params = mock_client.get_authed.call_args.kwargs["params"]
            assert params["status"] == "completed"
            assert params["sort"] == "anime_title"
            assert params["limit"] == 25
            assert params["offset"] == 10

    def test_get_my_manga_list_with_status_and_sort(self):
        from mcp.server.fastmcp import FastMCP

        mcp = FastMCP("test")
        with patch("tools.tools.MALClient") as mock_client_cls, patch("tools.tools.get_mal_access_token", new=AsyncMock(return_value="test-token")):
            mock_client = AsyncMock()
            mock_client.get_authed = AsyncMock(return_value={"data": []})
            mock_client_cls.return_value = mock_client
            register_tools(mcp)

            import asyncio
            tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "get_my_manga_list")
            asyncio.run(tool.fn(MangaStatus.READING, MangaStatusSort.LIST_SCORE, 50, 5, None))

            params = mock_client.get_authed.call_args.kwargs["params"]
            assert params["status"] == "reading"
            assert params["sort"] == "list_score"
            assert params["limit"] == 50
            assert params["offset"] == 5

    def test_get_my_anime_list_omit_status_sort_when_none(self):
        from mcp.server.fastmcp import FastMCP

        mcp = FastMCP("test")
        with patch("tools.tools.MALClient") as mock_client_cls, patch("tools.tools.get_mal_access_token", new=AsyncMock(return_value="test-token")):
            mock_client = AsyncMock()
            mock_client.get_authed = AsyncMock(return_value={"data": []})
            mock_client_cls.return_value = mock_client
            register_tools(mcp)

            import asyncio
            tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "get_my_anime_list")
            asyncio.run(tool.fn(None, None, 10, 0, None))

            params = mock_client.get_authed.call_args.kwargs["params"]
            assert "status" not in params
            assert "sort" not in params

    def test_get_my_manga_list_omit_status_sort_when_none(self):
        from mcp.server.fastmcp import FastMCP

        mcp = FastMCP("test")
        with patch("tools.tools.MALClient") as mock_client_cls, patch("tools.tools.get_mal_access_token", new=AsyncMock(return_value="test-token")):
            mock_client = AsyncMock()
            mock_client.get_authed = AsyncMock(return_value={"data": []})
            mock_client_cls.return_value = mock_client
            register_tools(mcp)

            import asyncio
            tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "get_my_manga_list")
            asyncio.run(tool.fn(None, None, 10, 0, None))

            params = mock_client.get_authed.call_args.kwargs["params"]
            assert "status" not in params
            assert "sort" not in params

    def test_get_my_anime_list_with_fields(self):
        from mcp.server.fastmcp import FastMCP

        mcp = FastMCP("test")
        with patch("tools.tools.MALClient") as mock_client_cls, patch("tools.tools.get_mal_access_token", new=AsyncMock(return_value="test-token")):
            mock_client = AsyncMock()
            mock_client.get_authed = AsyncMock(return_value={"data": []})
            mock_client_cls.return_value = mock_client
            register_tools(mcp)

            import asyncio
            tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "get_my_anime_list")
            asyncio.run(tool.fn(None, None, 10, 0, ["id", "title", "mean"]))

            params = mock_client.get_authed.call_args.kwargs["params"]
            assert "fields" in params
            assert "mean" in params["fields"]

    def test_get_my_manga_list_with_fields(self):
        from mcp.server.fastmcp import FastMCP

        mcp = FastMCP("test")
        with patch("tools.tools.MALClient") as mock_client_cls, patch("tools.tools.get_mal_access_token", new=AsyncMock(return_value="test-token")):
            mock_client = AsyncMock()
            mock_client.get_authed = AsyncMock(return_value={"data": []})
            mock_client_cls.return_value = mock_client
            register_tools(mcp)

            import asyncio
            tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "get_my_manga_list")
            asyncio.run(tool.fn(None, None, 10, 0, ["id", "title", "mean"]))

            params = mock_client.get_authed.call_args.kwargs["params"]
            assert "fields" in params
            assert "mean" in params["fields"]

    def test_get_my_anime_list_fields_not_in_params_when_none(self):
        from mcp.server.fastmcp import FastMCP

        mcp = FastMCP("test")
        with patch("tools.tools.MALClient") as mock_client_cls, patch("tools.tools.get_mal_access_token", new=AsyncMock(return_value="test-token")):
            mock_client = AsyncMock()
            mock_client.get_authed = AsyncMock(return_value={"data": []})
            mock_client_cls.return_value = mock_client
            register_tools(mcp)

            import asyncio
            tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "get_my_anime_list")
            asyncio.run(tool.fn(None, None, 10, 0, None))

            params = mock_client.get_authed.call_args.kwargs["params"]
            assert "fields" not in params

    def test_get_my_manga_list_fields_not_in_params_when_none(self):
        from mcp.server.fastmcp import FastMCP

        mcp = FastMCP("test")
        with patch("tools.tools.MALClient") as mock_client_cls, patch("tools.tools.get_mal_access_token", new=AsyncMock(return_value="test-token")):
            mock_client = AsyncMock()
            mock_client.get_authed = AsyncMock(return_value={"data": []})
            mock_client_cls.return_value = mock_client
            register_tools(mcp)

            import asyncio
            tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "get_my_manga_list")
            asyncio.run(tool.fn(None, None, 10, 0, None))

            params = mock_client.get_authed.call_args.kwargs["params"]
            assert "fields" not in params

    def test_get_my_anime_list_missing_token_error(self):
        from mcp.server.fastmcp import FastMCP

        mcp = FastMCP("test")
        with patch("tools.tools.MALClient") as mock_client_cls, patch("tools.tools.get_mal_access_token", new=AsyncMock(return_value=None)):
            mock_client = AsyncMock()
            mock_client_cls.return_value = mock_client
            register_tools(mcp)

            import asyncio
            tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "get_my_anime_list")
            result = asyncio.run(tool.fn(None, None, 10, 0, None))

            assert "error" in result
            mock_client.get_authed.assert_not_called()

    def test_get_my_manga_list_missing_token_error(self):
        from mcp.server.fastmcp import FastMCP

        mcp = FastMCP("test")
        with patch("tools.tools.MALClient") as mock_client_cls, patch("tools.tools.get_mal_access_token", new=AsyncMock(return_value=None)):
            mock_client = AsyncMock()
            mock_client_cls.return_value = mock_client
            register_tools(mcp)

            import asyncio
            tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "get_my_manga_list")
            result = asyncio.run(tool.fn(None, None, 10, 0, None))

            assert "error" in result
            mock_client.get_authed.assert_not_called()

    def test_get_my_anime_list_offset_clamped_to_zero(self):
        from mcp.server.fastmcp import FastMCP

        mcp = FastMCP("test")
        with patch("tools.tools.MALClient") as mock_client_cls, patch("tools.tools.get_mal_access_token", new=AsyncMock(return_value="test-token")):
            mock_client = AsyncMock()
            mock_client.get_authed = AsyncMock(return_value={"data": []})
            mock_client_cls.return_value = mock_client
            register_tools(mcp)

            import asyncio
            tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "get_my_anime_list")
            asyncio.run(tool.fn(None, None, 10, -5, None))

            params = mock_client.get_authed.call_args.kwargs["params"]
            assert params["offset"] == 0

    def test_get_my_anime_list_limit_clamped_to_one(self):
        from mcp.server.fastmcp import FastMCP

        mcp = FastMCP("test")
        with patch("tools.tools.MALClient") as mock_client_cls, patch("tools.tools.get_mal_access_token", new=AsyncMock(return_value="test-token")):
            mock_client = AsyncMock()
            mock_client.get_authed = AsyncMock(return_value={"data": []})
            mock_client_cls.return_value = mock_client
            register_tools(mcp)

            import asyncio
            tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "get_my_anime_list")
            asyncio.run(tool.fn(None, None, -5, 0, None))

            params = mock_client.get_authed.call_args.kwargs["params"]
            assert params["limit"] == 1


_VALID_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/">
  <channel>
    <title>News - MyAnimeList</title>
    <item>
      <title>Article One</title>
      <link>https://myanimelist.net/news/111?_location=rss</link>
      <description>First article description.</description>
      <pubDate>Mon, 01 Jan 2024 12:00:00 -0000</pubDate>
      <media:thumbnail url="https://example.com/thumb1.jpg"/>
    </item>
    <item>
      <title>Article Two</title>
      <link>https://myanimelist.net/news/222?_location=rss</link>
      <description>Second article description.</description>
      <pubDate>Tue, 02 Jan 2024 12:00:00 -0000</pubDate>
      <media:thumbnail url="https://example.com/thumb2.jpg"/>
    </item>
    <item>
      <title>Article Three</title>
      <link>https://myanimelist.net/news/333</link>
      <description>Third article description.</description>
      <pubDate>Wed, 03 Jan 2024 12:00:00 -0000</pubDate>
      <media:thumbnail url="https://example.com/thumb3.jpg"/>
    </item>
  </channel>
</rss>"""


class TestParseMalNewsRss:
    def test_parses_all_articles(self):
        result = parse_mal_news_rss(_VALID_RSS, 10)
        assert len(result["articles"]) == 3
        assert result["articles"][0]["title"] == "Article One"
        assert result["articles"][0]["url"] == "https://myanimelist.net/news/111"
        assert result["articles"][0]["description"] == "First article description."
        assert result["articles"][0]["published"] == "Mon, 01 Jan 2024 12:00:00 -0000"
        assert result["articles"][0]["thumbnail"] == "https://example.com/thumb1.jpg"

    def test_respects_limit(self):
        result = parse_mal_news_rss(_VALID_RSS, 1)
        assert len(result["articles"]) == 1
        assert result["articles"][0]["title"] == "Article One"

    def test_strips_tracking_query_from_url(self):
        result = parse_mal_news_rss(_VALID_RSS, 1)
        assert "?_location=rss" not in result["articles"][0]["url"]

    def test_handles_empty_feed(self):
        rss = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>News</title></channel></rss>"""
        result = parse_mal_news_rss(rss, 10)
        assert result["articles"] == []

    def test_handles_missing_channel(self):
        rss = '<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"></rss>'
        result = parse_mal_news_rss(rss, 10)
        assert "error" in result

    def test_raises_on_malformed_xml(self):
        with pytest.raises(ParseError):
            parse_mal_news_rss("not valid xml", 10)

    def test_skips_items_without_title_and_url(self):
        rss = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><item><description>No title or link</description></item></channel></rss>"""
        result = parse_mal_news_rss(rss, 10)
        assert result["articles"] == []

    def test_item_with_only_title(self):
        rss = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><item><title>Title Only</title></item></channel></rss>"""
        result = parse_mal_news_rss(rss, 10)
        assert len(result["articles"]) == 1
        assert result["articles"][0]["title"] == "Title Only"
        assert result["articles"][0]["url"] is None
        assert result["articles"][0]["description"] is None
        assert result["articles"][0]["published"] is None
        assert result["articles"][0]["thumbnail"] is None

    def test_item_with_missing_thumbnail(self):
        rss = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><item><title>T</title><link>https://a.b</link></item></channel></rss>"""
        result = parse_mal_news_rss(rss, 10)
        assert result["articles"][0]["thumbnail"] is None


class TestGetMalNews:
    def test_get_mal_news_fetches_rss_url(self):
        from mcp.server.fastmcp import FastMCP

        rss_response = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <title>News</title>
  <item><title>T</title><link>https://a.b</link><description>D</description><pubDate>Mon, 01 Jan 2024 00:00:00 -0000</pubDate></item>
</channel></rss>"""

        mcp = FastMCP("test")
        with patch("tools.tools.MALClient") as mock_client_cls, \
             patch("tools.tools.httpx.AsyncClient") as mock_async_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value = mock_client

            mock_response = AsyncMock()
            mock_response.raise_for_status = Mock()
            mock_response.text = rss_response
            mock_http = AsyncMock()
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_http.get = AsyncMock(return_value=mock_response)
            mock_async_client_cls.return_value = mock_http

            register_tools(mcp)

            import asyncio
            tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "get_mal_news")
            result = asyncio.run(tool.fn(5))

            mock_http.get.assert_called_once_with("https://myanimelist.net/rss/news.xml")
            assert len(result["articles"]) == 1

    def test_get_mal_news_limit_is_clamped(self):
        from mcp.server.fastmcp import FastMCP

        rss_empty = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>News</title></channel></rss>"""

        mcp = FastMCP("test")
        with patch("tools.tools.MALClient") as mock_client_cls, \
             patch("tools.tools.httpx.AsyncClient") as mock_async_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value = mock_client

            mock_response = AsyncMock()
            mock_response.raise_for_status = Mock()
            mock_response.text = rss_empty
            mock_http = AsyncMock()
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_http.get = AsyncMock(return_value=mock_response)
            mock_async_client_cls.return_value = mock_http

            register_tools(mcp)

            import asyncio
            tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "get_mal_news")
            asyncio.run(tool.fn(100))

            mock_http.get.assert_called_once()

    def test_get_mal_news_http_error(self):
        from mcp.server.fastmcp import FastMCP

        mcp = FastMCP("test")
        with patch("tools.tools.MALClient") as mock_client_cls, \
             patch("tools.tools.httpx.AsyncClient") as mock_async_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value = mock_client

            mock_http = AsyncMock()
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            error_response = AsyncMock()
            error_response.status_code = 503
            error_response.reason_phrase = "Service Unavailable"
            import httpx
            mock_http.get = AsyncMock(side_effect=httpx.HTTPStatusError(
                "error", request=AsyncMock(), response=error_response
            ))
            mock_async_client_cls.return_value = mock_http

            register_tools(mcp)

            import asyncio
            tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "get_mal_news")
            result = asyncio.run(tool.fn(10))

            assert "error" in result
            assert "503" in result["error"]


class TestSeasonalAnimeErrorHandling:
    def test_get_seasonal_anime_empty_error_from_mal_api(self):
        from mcp.server.fastmcp import FastMCP

        mcp = FastMCP("test")
        with patch("tools.tools.MALClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get_public = AsyncMock(
                side_effect=MALAPIError("MAL API returned an empty error", payload={"error": ""})
            )
            mock_client_cls.return_value = mock_client
            register_tools(mcp)

            import asyncio
            tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "get_seasonal_anime")
            result = asyncio.run(tool.fn(Season.SUMMER, 2026, None, 10, 0, None))

            assert "error" in result
            assert result["error"] == "MAL API returned an empty error"
            assert result["status_code"] == 200

    def test_get_seasonal_anime_mal_api_error_with_message(self):
        from mcp.server.fastmcp import FastMCP

        mcp = FastMCP("test")
        with patch("tools.tools.MALClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get_public = AsyncMock(
                side_effect=MALAPIError("MAL API returned an error: invalid season", payload={"error": "invalid season"})
            )
            mock_client_cls.return_value = mock_client
            register_tools(mcp)

            import asyncio
            tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "get_seasonal_anime")
            result = asyncio.run(tool.fn(Season.SUMMER, 2026, None, 10, 0, None))

            assert "error" in result
            assert "invalid season" in result["error"]
            assert result["status_code"] == 200

    def test_get_seasonal_anime_generic_exception_empty_string(self):
        from mcp.server.fastmcp import FastMCP

        mcp = FastMCP("test")
        with patch("tools.tools.MALClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get_public = AsyncMock(side_effect=Exception(""))
            mock_client_cls.return_value = mock_client
            register_tools(mcp)

            import asyncio
            tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "get_seasonal_anime")
            result = asyncio.run(tool.fn(Season.SUMMER, 2026, None, 10, 0, None))

            assert "error" in result
            assert result["error"] == "Exception"

    def test_get_seasonal_anime_http_error_converted_to_payload(self):
        from mcp.server.fastmcp import FastMCP
        import httpx

        mcp = FastMCP("test")
        with patch("tools.tools.MALClient") as mock_client_cls:
            mock_client = AsyncMock()
            req = Mock()
            resp = Mock()
            resp.status_code = 503
            resp.reason_phrase = "Service Unavailable"
            mock_client.get_public = AsyncMock(
                side_effect=httpx.HTTPStatusError("error", request=req, response=resp)
            )
            mock_client_cls.return_value = mock_client
            register_tools(mcp)

            import asyncio
            tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "get_seasonal_anime")
            result = asyncio.run(tool.fn(Season.SUMMER, 2026, None, 10, 0, None))

            assert "error" in result
            assert "503" in result["error"]
            assert result["status_code"] == 503


class TestGetWatchQueue:
    def test_get_watch_queue_auth_required(self):
        from mcp.server.fastmcp import FastMCP

        mcp = FastMCP("test")
        with patch("tools.tools.MALClient") as mock_client_cls, \
             patch("tools.tools.get_mal_access_token", new=AsyncMock(return_value="test-token")), \
             patch("tools.tools.httpx.AsyncClient") as mock_async_client_cls:

            mock_client = AsyncMock()
            mock_client.get_authed = AsyncMock(return_value={"data": []})
            mock_client_cls.return_value = mock_client

            cal_text = "BEGIN:VCALENDAR\nEND:VCALENDAR\n"
            mock_response = AsyncMock()
            mock_response.raise_for_status = Mock()
            mock_response.text = cal_text
            mock_http = AsyncMock()
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_http.get = AsyncMock(return_value=mock_response)
            mock_async_client_cls.return_value = mock_http

            register_tools(mcp)

            import asyncio
            tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "get_watch_queue")
            asyncio.run(tool.fn("testuser"))

            mock_client.get_authed.assert_called_once()
            assert mock_client.get_authed.call_args.args[0] == "/users/@me/animelist"
            assert mock_client.get_authed.call_args.args[1] == "test-token"
            cal_params = mock_client.get_authed.call_args.kwargs["params"]
            assert cal_params["status"] == "watching"
            assert cal_params["fields"] == "list_status{num_episodes_watched},anime{id,title,num_episodes,status}"

    def test_get_watch_queue_missing_token_error(self):
        from mcp.server.fastmcp import FastMCP

        mcp = FastMCP("test")
        with patch("tools.tools.MALClient") as mock_client_cls, \
             patch("tools.tools.get_mal_access_token", new=AsyncMock(return_value=None)):
            mock_client = AsyncMock()
            mock_client_cls.return_value = mock_client
            register_tools(mcp)

            import asyncio
            tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "get_watch_queue")
            result = asyncio.run(tool.fn())

            assert "error" in result
            mock_client.get_authed.assert_not_called()

    def test_get_watch_queue_fetches_calendar_url(self):
        from mcp.server.fastmcp import FastMCP
        from urllib.parse import quote

        mcp = FastMCP("test")
        with patch("tools.tools.MALClient") as mock_client_cls, \
             patch("tools.tools.get_mal_access_token", new=AsyncMock(return_value="test-token")), \
             patch("tools.tools.httpx.AsyncClient") as mock_async_client_cls:

            mock_client = AsyncMock()
            mock_client.get_authed = AsyncMock(return_value={"data": []})
            mock_client_cls.return_value = mock_client

            cal_text = "BEGIN:VCALENDAR\nEND:VCALENDAR\n"
            mock_response = AsyncMock()
            mock_response.raise_for_status = Mock()
            mock_response.text = cal_text
            mock_http = AsyncMock()
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_http.get = AsyncMock(return_value=mock_response)
            mock_async_client_cls.return_value = mock_http

            register_tools(mcp)

            import asyncio
            tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "get_watch_queue")
            asyncio.run(tool.fn("test user"))

            expected = f"https://api.anime-calendar.com/v3/ical/myanimelist/{quote('test user', safe='')}"
            mock_http.get.assert_called_once_with(expected)

    def test_get_watch_queue_calendar_error_returns_safe_payload(self):
        from mcp.server.fastmcp import FastMCP
        import httpx as httpx_lib

        mcp = FastMCP("test")
        with patch("tools.tools.MALClient") as mock_client_cls, \
             patch("tools.tools.get_mal_access_token", new=AsyncMock(return_value="test-token")), \
             patch("tools.tools.httpx.AsyncClient") as mock_async_client_cls:

            mock_client = AsyncMock()
            mock_client.get_authed = AsyncMock(return_value={"data": []})
            mock_client_cls.return_value = mock_client

            mock_http = AsyncMock()
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            error_response = AsyncMock()
            error_response.status_code = 503
            error_response.reason_phrase = "Service Unavailable"
            mock_http.get = AsyncMock(side_effect=httpx_lib.HTTPStatusError(
                "error", request=AsyncMock(), response=error_response
            ))
            mock_async_client_cls.return_value = mock_http

            register_tools(mcp)

            import asyncio
            tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "get_watch_queue")
            result = asyncio.run(tool.fn())

            assert "error" in result
            assert "503" in result["error"]

    def test_get_watch_queue_with_data_returns_structured_result(self):
        from mcp.server.fastmcp import FastMCP

        mcp = FastMCP("test")
        with patch("tools.tools.MALClient") as mock_client_cls, \
             patch("tools.tools.get_mal_access_token", new=AsyncMock(return_value="test-token")), \
             patch("tools.tools.httpx.AsyncClient") as mock_async_client_cls:

            mock_client = AsyncMock()
            mock_client.get_authed = AsyncMock(return_value={
                "data": [
                    {"node": {"id": 1, "title": "Show A", "num_episodes": 12, "status": "finished_airing"},
                     "list_status": {"num_episodes_watched": 5}},
                ]
            })
            mock_client_cls.return_value = mock_client

            cal_text = "BEGIN:VCALENDAR\nEND:VCALENDAR\n"
            mock_response = AsyncMock()
            mock_response.raise_for_status = Mock()
            mock_response.text = cal_text
            mock_http = AsyncMock()
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_http.get = AsyncMock(return_value=mock_response)
            mock_async_client_cls.return_value = mock_http

            register_tools(mcp)

            import asyncio
            tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "get_watch_queue")
            result = asyncio.run(tool.fn("testuser"))

            assert "entries" in result
            assert "aggregate" in result
            assert len(result["entries"]) == 1
            assert result["aggregate"]["total_watching"] == 1