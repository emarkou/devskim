import pytest
from pytest_httpx import HTTPXMock

from grokfeed.sources.lobsters import LOBSTERS_URL, fetch_lobsters_posts


def _item(
    *,
    short_id: str = "abc",
    title: str = "Test",
    url: str = "https://example.com",
    score: int = 10,
    comment_count: int = 5,
    description: str = "",
    created_at: str = "2023-11-14T22:13:20.000Z",
) -> dict:
    return {
        "short_id": short_id,
        "title": title,
        "url": url,
        "score": score,
        "comment_count": comment_count,
        "description": description,
        "comments_url": f"https://lobste.rs/s/{short_id}",
        "created_at": created_at,
    }


@pytest.mark.asyncio
async def test_fetch_lobsters_posts_basic(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url=LOBSTERS_URL,
        json=[_item(title="Rust is great", score=25, comment_count=8)],
    )
    posts = await fetch_lobsters_posts(count=5)
    assert len(posts) == 1
    p = posts[0]
    assert p.title == "Rust is great"
    assert p.score == 25
    assert p.comments == 8
    assert p.source == "lobste.rs"
    assert p.url == "https://example.com"
    assert p.created_at == 1700000000  # 2023-11-14T22:13:20Z


@pytest.mark.asyncio
async def test_fetch_lobsters_posts_respects_count(httpx_mock: HTTPXMock):
    items = [_item(short_id=str(i), title=f"Post {i}") for i in range(10)]
    httpx_mock.add_response(url=LOBSTERS_URL, json=items)
    posts = await fetch_lobsters_posts(count=3)
    assert len(posts) == 3


@pytest.mark.asyncio
async def test_fetch_lobsters_posts_no_url_falls_back_to_comments(httpx_mock: HTTPXMock):
    httpx_mock.add_response(url=LOBSTERS_URL, json=[_item(url="")])
    posts = await fetch_lobsters_posts(count=5)
    assert posts[0].url == "https://lobste.rs/s/abc"


@pytest.mark.asyncio
async def test_fetch_lobsters_posts_http_error_returns_empty(httpx_mock: HTTPXMock):
    httpx_mock.add_response(url=LOBSTERS_URL, status_code=500)
    posts = await fetch_lobsters_posts(count=5)
    assert posts == []


@pytest.mark.asyncio
async def test_fetch_lobsters_posts_description_stripped(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url=LOBSTERS_URL,
        json=[_item(description="<p>Discussion text here.")],
    )
    posts = await fetch_lobsters_posts(count=5)
    assert "Discussion text here" in posts[0].body
    assert "<p>" not in posts[0].body
