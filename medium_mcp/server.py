"""MCP tools for Medium, served over stdio or streamable HTTP."""

from __future__ import annotations

import argparse
import hmac
import os
from typing import Any, Literal

import markdown as markdown_lib
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from medium_mcp.client import MediumError, MediumFeedClient

load_dotenv()

API_KEY_HEADER = b"x-mcp-key"
LOCAL_HOSTS = ["127.0.0.1", "127.0.0.1:*", "localhost", "localhost:*"]
MAX_TAGS = 5
NEW_STORY_URL = "https://medium.com/new-story"
IMPORT_URL = "https://medium.com/p/import"


def _allowed_hosts() -> list[str]:
    extra = os.environ.get("MCP_ALLOWED_HOSTS", "")
    return LOCAL_HOSTS + [h.strip() for h in extra.split(",") if h.strip()]


mcp = FastMCP(
    "medium",
    stateless_http=True,
    host=os.environ.get("MCP_HOST", "127.0.0.1"),
    port=int(os.environ.get("MCP_PORT", "8000")),
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=_allowed_hosts(),
    ),
)


def _username(username: str | None) -> str:
    name = username or os.environ.get("MEDIUM_USERNAME")
    if not name:
        raise MediumError("Pass a username or set MEDIUM_USERNAME.")
    return name


@mcp.tool()
async def medium_list_posts(
    username: str | None = None, limit: int = 10
) -> list[dict[str, Any]]:
    """List a Medium user's recent public posts from their RSS feed.

    Drafts, unlisted posts and older posts are not available. username defaults
    to MEDIUM_USERNAME.
    """
    return await MediumFeedClient().list_posts(_username(username), max(1, limit))


@mcp.tool()
async def medium_get_post(post: str, username: str | None = None) -> dict[str, Any]:
    """Get a recent public post, including its HTML content, by id or URL."""
    return await MediumFeedClient().get_post(_username(username), post)


@mcp.tool()
def medium_prepare_post(
    title: str,
    content: str,
    content_format: Literal["markdown", "html"] = "markdown",
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """Prepare a post for manual publishing. This does NOT publish anything.

    Returns paste-ready HTML, cleaned tags, warnings and the steps to follow,
    because Medium no longer offers an API for publishing.
    """
    if not title.strip() or not content.strip():
        raise MediumError("Title and content must not be empty.")
    body = (
        markdown_lib.markdown(content, extensions=["fenced_code"])
        if content_format == "markdown"
        else content
    )
    cleaned = list(dict.fromkeys(t.strip() for t in (tags or []) if t.strip()))
    warnings = []
    if len(cleaned) > MAX_TAGS:
        warnings.append(f"Medium allows {MAX_TAGS} tags; dropped: {cleaned[MAX_TAGS:]}")
    if "<table" in body:
        warnings.append("Medium's editor does not support tables; use an image.")
    return {
        "published": False,
        "title": title.strip(),
        "html": body,
        "tags": cleaned[:MAX_TAGS],
        "warnings": warnings,
        "next_steps": [
            f"Open {NEW_STORY_URL}, enter the title, and paste the rendered text.",
            f"Or, if the post is already on a public URL, use {IMPORT_URL}.",
            "Add the tags in Medium's publish dialog.",
        ],
    }


class ApiKeyMiddleware:
    """Reject HTTP requests that lack the shared key in the X-MCP-Key header."""

    def __init__(self, app: Any, api_key: str):
        self.app = app
        self.api_key = api_key.encode()

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope["type"] == "http":
            supplied = dict(scope["headers"]).get(API_KEY_HEADER, b"")
            if not hmac.compare_digest(supplied, self.api_key):
                await send(
                    {
                        "type": "http.response.start",
                        "status": 401,
                        "headers": [(b"content-type", b"text/plain")],
                    }
                )
                await send({"type": "http.response.body", "body": b"Unauthorized"})
                return
        await self.app(scope, receive, send)


def http_app() -> Any:
    app = mcp.streamable_http_app()
    api_key = os.environ.get("MCP_API_KEY")
    return ApiKeyMiddleware(app, api_key) if api_key else app


def main() -> None:
    parser = argparse.ArgumentParser(description="Medium MCP server")
    parser.add_argument("--transport", choices=["stdio", "http"], default="http")
    args = parser.parse_args()
    if args.transport == "stdio":
        mcp.run("stdio")
        return
    import uvicorn

    uvicorn.run(http_app(), host=mcp.settings.host, port=mcp.settings.port)


if __name__ == "__main__":
    main()
