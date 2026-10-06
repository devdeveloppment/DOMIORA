"""Authentication and small-process rate limiting for the MCP service."""

from __future__ import annotations

import hashlib
import hmac
import logging
import time
import uuid
from collections import defaultdict, deque

from mcp.server.auth.provider import AccessToken, TokenVerifier

logger = logging.getLogger("domiora_mcp")


class StaticBearerTokenVerifier(TokenVerifier):
    """Verify one or more operator-managed bearer tokens without logging them."""

    def __init__(self, tokens: set[str], resource: str) -> None:
        self._token_hashes = {
            hashlib.sha256(token.encode("utf-8")).digest() for token in tokens if token
        }
        self._resource = resource

    async def verify_token(self, token: str) -> AccessToken | None:
        candidate = hashlib.sha256(token.encode("utf-8")).digest()
        if not any(hmac.compare_digest(candidate, known) for known in self._token_hashes):
            return None
        return AccessToken(
            token=token,
            client_id="domiora-mcp-client",
            scopes=["claude:ask"],
            resource=self._resource,
        )


class RateLimitMiddleware:
    """Bound requests per client IP in one process; use a shared gateway for fleets."""

    def __init__(self, app, limit: int, window_seconds: int) -> None:
        self.app = app
        self.limit = limit
        self.window_seconds = window_seconds
        self._requests: defaultdict[str, deque[float]] = defaultdict(deque)

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http" or scope.get("path") in {"/health", "/"}:
            await self.app(scope, receive, send)
            return

        now = time.monotonic()
        client = scope.get("client")
        client_key = client[0] if client else "unknown"
        bucket = self._requests[client_key]
        while bucket and now - bucket[0] >= self.window_seconds:
            bucket.popleft()
        if len(bucket) >= self.limit:
            from starlette.responses import JSONResponse

            response = JSONResponse(
                {"error": "rate_limit_exceeded", "message": "Too many requests."},
                status_code=429,
                headers={"Retry-After": str(self.window_seconds)},
            )
            await response(scope, receive, send)
            return
        bucket.append(now)
        await self.app(scope, receive, send)


class RequestLoggingMiddleware:
    """Log request metadata and duration without recording prompts or credentials."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = str(uuid.uuid4())
        started = time.perf_counter()

        async def send_with_metadata(message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", request_id.encode("ascii")))
                message = {**message, "headers": headers}
                logger.info(
                    "request_complete request_id=%s method=%s path=%s status=%s duration_ms=%d",
                    request_id,
                    scope.get("method", ""),
                    scope.get("path", ""),
                    message["status"],
                    (time.perf_counter() - started) * 1000,
                )
            await send(message)

        await self.app(scope, receive, send_with_metadata)
