import pytest
from unittest.mock import AsyncMock, patch

from utils.schemas import AnimeRanking, MangaRanking, Season
from tools.tools import register_tools, normalize_episode_window, anime_calendar_ical_url


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
        assert len(names) == 23

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