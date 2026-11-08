import asyncio

import httpx
import pytest

from medium_mcp import server
from medium_mcp.client import MediumError, MediumFeedClient, post_id_from

RSS = b"""<rss xmlns:content="http://purl.org/rss/1.0/modules/content/"><channel>
<item><title>Hello</title><link>https://medium.com/@alice/hello-abc123?source=rss</link>
<guid>https://medium.com/p/abc123</guid><category>python</category>
<content:encoded>&lt;p&gt;Hi&lt;/p&gt;</content:encoded></item>
</channel></rss>"""


def client(status=200):
    def handler(request):
        assert request.url.path == "/feed/@alice"
        return httpx.Response(status, content=RSS)

    return MediumFeedClient(transport=httpx.MockTransport(handler))


def test_list_posts_parses_feed():
    post = asyncio.run(client().list_posts("@alice"))[0]
    assert post["id"] == "abc123"
    assert post["title"] == "Hello"
    assert post["tags"] == ["python"]
    assert post["content"] == "<p>Hi</p>"


@pytest.mark.parametrize(
    "value",
    ["abc123", "https://medium.com/p/abc123", "https://medium.com/@alice/hello-abc123?x=1"],
)
def test_post_id_forms(value):
    assert post_id_from(value) == "abc123"


def test_get_post_missing():
    with pytest.raises(MediumError, match="not in"):
        asyncio.run(client().get_post("alice", "zzz"))


def test_unknown_user():
    with pytest.raises(MediumError, match="No Medium feed"):
        asyncio.run(client(404).list_posts("alice"))


def test_username_cannot_change_path():
    seen = {}

    def handler(request):
        seen["raw"] = request.url.raw_path
        return httpx.Response(200, content=RSS)

    asyncio.run(MediumFeedClient(httpx.MockTransport(handler)).list_posts("../x"))
    assert seen["raw"] == b"/feed/@..%2Fx"


def test_prepare_renders_markdown_and_trims_tags():
    result = server.medium_prepare_post(
        "T", "# Head", tags=["a", "a", "b", "c", "d", "e", "f"]
    )
    assert result["published"] is False
    assert "<h1>Head</h1>" in result["html"]
    assert result["tags"] == ["a", "b", "c", "d", "e"]
    assert result["warnings"]


def test_prepare_rejects_empty():
    with pytest.raises(MediumError):
        server.medium_prepare_post(" ", "x")


def run_middleware(headers):
    sent, called = [], []

    async def app(scope, receive, send):
        called.append(True)

    async def send(message):
        sent.append(message)

    middleware = server.ApiKeyMiddleware(app, "secret")
    asyncio.run(middleware({"type": "http", "headers": headers}, None, send))
    return sent, called


def test_middleware_blocks_wrong_key():
    sent, called = run_middleware([(b"x-mcp-key", b"nope")])
    assert sent[0]["status"] == 401 and not called


def test_middleware_allows_right_key():
    sent, called = run_middleware([(b"x-mcp-key", b"secret")])
    assert called and not sent
