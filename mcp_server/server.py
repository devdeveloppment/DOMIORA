"""DOMIORA remote MCP server using the official Streamable HTTP transport."""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from urllib.parse import urlparse

from anthropic import AsyncAnthropic
from mcp.server import MCPServer
from mcp.server.auth.settings import AuthSettings
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import AnyHttpUrl
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from .security import RateLimitMiddleware, RequestLoggingMiddleware, StaticBearerTokenVerifier

logger = logging.getLogger("domiora_mcp")


@dataclass(frozen=True)
class Settings:
    anthropic_api_key: str
    mcp_access_tokens: frozenset[str]
    public_url: str
    issuer_url: str
    default_model: str
    anthropic_timeout: float
    max_prompt_chars: int
    max_context_chars: int
    max_tokens: int
    rate_limit: int
    rate_window_seconds: int

    @classmethod
    def from_env(cls) -> "Settings":
        tokens = frozenset(
            value.strip()
            for value in os.getenv("MCP_ACCESS_TOKEN", "").split(",")
            if value.strip()
        )
        return cls(
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", "").strip(),
            mcp_access_tokens=tokens,
            public_url=os.getenv("MCP_PUBLIC_URL", "http://127.0.0.1:8000/mcp").rstrip("/"),
            issuer_url=os.getenv("MCP_ISSUER_URL", "https://tokens.example.invalid").rstrip("/"),
            default_model=os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514"),
            anthropic_timeout=float(os.getenv("ANTHROPIC_TIMEOUT_SECONDS", "60")),
            max_prompt_chars=int(os.getenv("MCP_MAX_PROMPT_CHARS", "12000")),
            max_context_chars=int(os.getenv("MCP_MAX_CONTEXT_CHARS", "30000")),
            max_tokens=int(os.getenv("MCP_MAX_TOKENS", "4096")),
            rate_limit=int(os.getenv("MCP_RATE_LIMIT", "30")),
            rate_window_seconds=int(os.getenv("MCP_RATE_WINDOW_SECONDS", "60")),
        )


settings = Settings.from_env()


def _allowed_hosts(public_url: str) -> list[str]:
    parsed = urlparse(public_url)
    if not parsed.hostname:
        raise ValueError("MCP_PUBLIC_URL must contain a hostname")
    return [parsed.hostname, f"{parsed.hostname}:*"]


resource_url = settings.public_url
verifier = StaticBearerTokenVerifier(set(settings.mcp_access_tokens), resource_url)

mcp = MCPServer(
    "DOMIORA Claude Cloud",
    token_verifier=verifier,
    auth=AuthSettings(
        issuer_url=AnyHttpUrl(settings.issuer_url),
        resource_server_url=AnyHttpUrl(resource_url),
        required_scopes=["claude:ask"],
        validate_token_resource=True,
    ),
    log_level="INFO",
)


@mcp.tool()
async def ask_claude(
    prompt: str,
    context: str = "",
    model: str = "",
    max_tokens: int = 0,
) -> str:
    """Ask Claude to analyze an explicitly supplied prompt and optional context."""
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("prompt must be a non-empty string")
    if len(prompt) > settings.max_prompt_chars:
        raise ValueError("prompt exceeds the configured size limit")
    if not isinstance(context, str):
        raise ValueError("context must be a string")
    if len(context) > settings.max_context_chars:
        raise ValueError("context exceeds the configured size limit")

    selected_model = model.strip() or settings.default_model
    if len(selected_model) > 120 or not all(char.isalnum() or char in "-_." for char in selected_model):
        raise ValueError("model contains invalid characters")
    selected_max_tokens = max_tokens or min(1024, settings.max_tokens)
    if selected_max_tokens < 1 or selected_max_tokens > settings.max_tokens:
        raise ValueError("max_tokens is outside the configured limit")
    if not settings.anthropic_api_key:
        logger.error("Anthropic API key is not configured")
        raise RuntimeError("Claude provider is not configured")

    user_content = prompt.strip()
    if context.strip():
        user_content += "\n\nExplicit context from the calling agent:\n" + context.strip()

    started = time.perf_counter()
    client = AsyncAnthropic(
        api_key=settings.anthropic_api_key,
        timeout=settings.anthropic_timeout,
        max_retries=0,
    )
    try:
        response = await client.messages.create(
            model=selected_model,
            max_tokens=selected_max_tokens,
            messages=[{"role": "user", "content": user_content}],
        )
        text = "\n".join(
            block.text for block in response.content if getattr(block, "type", None) == "text"
        ).strip()
        logger.info(
            "claude_request_complete model=%s duration_ms=%d input_chars=%d output_chars=%d",
            selected_model,
            (time.perf_counter() - started) * 1000,
            len(user_content),
            len(text),
        )
        return text or "Claude returned no textual content."
    except Exception as exc:
        logger.error(
            "claude_request_failed error_type=%s duration_ms=%d",
            type(exc).__name__,
            (time.perf_counter() - started) * 1000,
        )
        raise RuntimeError("Claude request failed; check server logs for the request id.") from None
    finally:
        await client.close()


@mcp.custom_route("/health", methods=["GET"])
async def health(_: Request) -> Response:
    """Public liveness endpoint; it intentionally reveals no secret or token state."""
    return JSONResponse({"status": "ok", "service": "mcp-server"})


@mcp.custom_route("/", methods=["GET"])
async def root(_: Request) -> Response:
    return JSONResponse({"service": "domiora-mcp", "mcp_endpoint": "/mcp"})


_transport_security = TransportSecuritySettings(
    allowed_hosts=_allowed_hosts(resource_url),
    allowed_origins=[],
)

app = RequestLoggingMiddleware(
    RateLimitMiddleware(
        mcp.streamable_http_app(
            transport_security=_transport_security,
            max_request_body_size=1024 * 1024,
        ),
        limit=settings.rate_limit,
        window_seconds=settings.rate_window_seconds,
    ),
)


if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        streamable_http_path="/mcp",
        max_request_body_size=1024 * 1024,
    )
