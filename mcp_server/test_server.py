import os
from types import SimpleNamespace

import httpx
import pytest
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

os.environ.setdefault("MCP_PUBLIC_URL", "http://127.0.0.1:8000/mcp")
os.environ.setdefault("MCP_ACCESS_TOKEN", "test-token")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-anthropic-key")

from mcp_server import server


class FakeMessages:
    async def create(self, **kwargs):
        assert kwargs["messages"][0]["content"].startswith("Explain")
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text="Mocked Claude response")]
        )


class FakeAnthropic:
    def __init__(self, **kwargs):
        assert kwargs["api_key"] == "test-anthropic-key"
        self.messages = FakeMessages()

    async def close(self):
        return None


@pytest.mark.asyncio
async def test_mcp_discovers_and_calls_ask_claude(monkeypatch):
    monkeypatch.setattr(server, "AsyncAnthropic", FakeAnthropic)
    async with Client(server.mcp) as client:
        tools = await client.list_tools()
        assert [tool.name for tool in tools.tools] == ["ask_claude"]
        result = await client.call_tool(
            "ask_claude",
            {"prompt": "Explain this", "context": "small context"},
        )
        assert result.structured_content == {"result": "Mocked Claude response"}


@pytest.mark.asyncio
async def test_health_is_public_and_does_not_expose_secrets():
    transport = httpx.ASGITransport(app=server.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:8000") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "mcp-server"}
    assert "test-anthropic-key" not in response.text


@pytest.mark.asyncio
async def test_mcp_http_requires_bearer_token():
    transport = httpx.ASGITransport(app=server.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:8000") as client:
        response = await client.get("/mcp")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_official_client_discovers_tools_over_authenticated_http():
    async with server.mcp.session_manager.run():
        transport = httpx.ASGITransport(app=server.app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://127.0.0.1:8000",
            headers={"Authorization": "Bearer test-token"},
        ) as http_client:
            async with Client(
                streamable_http_client("http://127.0.0.1:8000/mcp", http_client=http_client)
            ) as client:
                tools = await client.list_tools()
        assert [tool.name for tool in tools.tools] == ["ask_claude"]


@pytest.mark.asyncio
async def test_invalid_bearer_token_is_rejected():
    assert await server.verifier.verify_token("wrong-token") is None
    assert await server.verifier.verify_token("test-token") is not None


@pytest.mark.asyncio
async def test_oversized_prompt_is_rejected():
    with pytest.raises(ValueError, match="size limit"):
        await server.ask_claude("x" * (server.settings.max_prompt_chars + 1))
