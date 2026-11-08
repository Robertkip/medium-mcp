"""Read public Medium posts from RSS feeds. Needs no token."""

from __future__ import annotations

import ssl
from typing import Any
from urllib.parse import quote, urlsplit

import httpx
import truststore
from defusedxml import ElementTree

FEED_BASE = "https://medium.com/feed"
CONTENT_NS = "{http://purl.org/rss/1.0/modules/content/}encoded"
DC_CREATOR = "{http://purl.org/dc/elements/1.1/}creator"


class MediumError(Exception):
    """Medium could not be reached or returned something unusable."""


class MediumFeedClient:
    def __init__(self, transport: httpx.AsyncBaseTransport | None = None):
        self._transport = transport

    async def list_posts(self, username: str, limit: int = 10) -> list[dict]:
        return (await self._fetch_feed(username))[:limit]

    async def get_post(self, username: str, post: str) -> dict:
        """Find a post in the feed by its id or URL."""
        wanted = post_id_from(post)
        for item in await self._fetch_feed(username):
            if item["id"] == wanted:
                return item
        raise MediumError(
            f"Post '{post}' is not in @{clean_username(username)}'s feed. The feed "
            "only carries recent public posts."
        )

    async def _fetch_feed(self, username: str) -> list[dict]:
        url = f"{FEED_BASE}/@{quote(clean_username(username), safe='')}"
        try:
            # The OS trust store also works behind HTTPS-scanning antivirus.
            verify = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            async with httpx.AsyncClient(
                transport=self._transport,
                verify=verify,
                timeout=30,
                follow_redirects=True,
                headers={"User-Agent": "medium-mcp/0.2"},
            ) as http:
                response = await http.get(url)
        except httpx.HTTPError as exc:
            raise MediumError(f"Could not reach Medium: {exc}") from exc
        if response.status_code == 404:
            raise MediumError(f"No Medium feed found for @{clean_username(username)}.")
        if response.is_error:
            raise MediumError(f"Medium feed returned {response.status_code}.")
        try:
            root = ElementTree.fromstring(response.content)
        except Exception as exc:
            raise MediumError("Medium feed could not be parsed.") from exc
        return [_feed_item(item) for item in root.iter("item")]


def clean_username(username: str) -> str:
    return username.strip().lstrip("@")


def post_id_from(value: str) -> str:
    """Return the post id from a bare id or a Medium URL or guid."""
    path = urlsplit(value.strip()).path.rstrip("/")
    return path.rsplit("/", 1)[-1].rsplit("-", 1)[-1]


def _feed_item(item: Any) -> dict:
    return {
        "id": post_id_from(item.findtext("guid") or item.findtext("link") or ""),
        "title": item.findtext("title"),
        "url": item.findtext("link"),
        "author": item.findtext(DC_CREATOR),
        "publishedAt": item.findtext("pubDate"),
        "tags": [c.text for c in item.findall("category") if c.text],
        "content": item.findtext(CONTENT_NS),
    }
