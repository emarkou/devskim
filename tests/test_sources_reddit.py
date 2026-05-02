import pytest
from pytest_httpx import HTTPXMock
from urllib.parse import urlparse

from grokfeed.sources.reddit import REDDIT_HOT, REDDIT_HOT_AFTER, fetch_reddit_posts


def _child(
    *,
    post_id: str = "abc",
    title: str = "Test Post",
    url: str = "https://example.com",
    score: int = 500,
    num_comments: int = 100,
    subreddit: str = "python",
    is_self: bool = False,
    selftext: str = "",
) -> dict:
    return {
        "data": {
            "id": post_id,
            "title": title,
            "url": url,
            "score": score,
            "num_comments": num_comments,
            "subreddit": subreddit,
            "permalink": f"/r/{subreddit}/comments/{post_id}/test/",
            "is_self": is_self,
            "selftext": selftext,
        }
    }


@pytest.mark.asyncio
async def test_fetch_reddit_posts_link_post(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url=REDDIT_HOT.format(subreddit="python", limit=5),
        json={"data": {"after": "t3_next", "children": [_child()]}},
    )
    posts, after = await fetch_reddit_posts(["python"], count=5)
    assert len(posts) == 1
    p = posts[0]
    assert p.title == "Test Post"
    assert p.score == 500
    assert p.source == "r/python"
    assert p.url == "https://example.com"
    assert after == {"python": "t3_next"}


@pytest.mark.asyncio
async def test_fetch_reddit_posts_self_post_uses_permalink(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url=REDDIT_HOT.format(subreddit="python", limit=5),
        json={"data": {"after": None, "children": [_child(is_self=True, selftext="body text")]}},
    )
    posts, after = await fetch_reddit_posts(["python"], count=5)
    assert posts[0].body == "body text"
    parsed = urlparse(posts[0].url)
    host = parsed.hostname or ""
    assert host == "reddit.com" or host.endswith(".reddit.com")
    assert after == {}


@pytest.mark.asyncio
async def test_fetch_reddit_posts_deleted_selftext_cleared(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url=REDDIT_HOT.format(subreddit="python", limit=5),
        json={"data": {"after": None, "children": [_child(is_self=True, selftext="[deleted]")]}},
    )
    posts, _ = await fetch_reddit_posts(["python"], count=5)
    assert posts[0].body == ""


@pytest.mark.asyncio
async def test_fetch_reddit_posts_multiple_subreddits(httpx_mock: HTTPXMock):
    for sub in ["python", "rust"]:
        httpx_mock.add_response(
            url=REDDIT_HOT.format(subreddit=sub, limit=3),
            json={"data": {"after": None, "children": [_child(subreddit=sub)]}},
        )
    posts, _ = await fetch_reddit_posts(["python", "rust"], count=3)
    assert len(posts) == 2
    sources = {p.source for p in posts}
    assert sources == {"r/python", "r/rust"}


@pytest.mark.asyncio
async def test_fetch_reddit_posts_with_after_cursor(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url=REDDIT_HOT_AFTER.format(subreddit="python", limit=5, after="t3_abc"),
        json={"data": {"after": "t3_def", "children": []}},
    )
    posts, after = await fetch_reddit_posts(["python"], count=5, after={"python": "t3_abc"})
    assert posts == []
    assert after == {"python": "t3_def"}


@pytest.mark.asyncio
async def test_fetch_reddit_posts_http_error_returns_empty(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url=REDDIT_HOT.format(subreddit="python", limit=5),
        status_code=429,
    )
    posts, after = await fetch_reddit_posts(["python"], count=5)
    assert posts == []
    assert after == {}
