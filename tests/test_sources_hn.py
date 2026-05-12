import httpx
import pytest
from pytest_httpx import HTTPXMock

from devskim.sources.hn import HN_BASE, _strip_html, fetch_hn_stories, fetch_hn_stories_by_ids, fetch_hn_top_ids


def test_strip_html_paragraph_tag():
    # <p> → \n\n but leading whitespace is stripped — check mid-string conversion
    assert "\n\n" in _strip_html("before<p>after")


def test_strip_html_removes_tags():
    assert _strip_html("<a href='x'>link</a>") == "link"


def test_strip_html_unescapes_entities():
    assert _strip_html("&amp;&lt;&gt;") == "&<>"


def test_strip_html_empty():
    assert _strip_html("") == ""


@pytest.mark.asyncio
async def test_fetch_hn_top_ids(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url=f"{HN_BASE}/topstories.json",
        json=[1, 2, 3],
    )
    async with httpx.AsyncClient() as client:
        ids = await fetch_hn_top_ids(client)
    assert ids == [1, 2, 3]


@pytest.mark.asyncio
async def test_fetch_hn_stories_by_ids_link_post(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url=f"{HN_BASE}/item/1.json",
        json={
            "id": 1,
            "type": "story",
            "title": "Test Story",
            "url": "https://example.com",
            "score": 100,
            "descendants": 42,
            "text": "",
            "time": 1700000000,
        },
    )
    async with httpx.AsyncClient() as client:
        stories = await fetch_hn_stories_by_ids([1], client)
    assert len(stories) == 1
    s = stories[0]
    assert s.title == "Test Story"
    assert s.score == 100
    assert s.comments == 42
    assert s.url == "https://example.com"
    assert s.body == ""
    assert s.created_at == 1700000000


@pytest.mark.asyncio
async def test_fetch_hn_stories_skips_non_story_types(httpx_mock: HTTPXMock):
    httpx_mock.add_response(url=f"{HN_BASE}/item/2.json", json={"id": 2, "type": "job"})
    async with httpx.AsyncClient() as client:
        stories = await fetch_hn_stories_by_ids([2], client)
    assert stories == []


@pytest.mark.asyncio
async def test_fetch_hn_stories_ask_hn_uses_item_url(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url=f"{HN_BASE}/item/3.json",
        json={
            "id": 3,
            "type": "story",
            "title": "Ask HN: something",
            "score": 50,
            "descendants": 5,
            "text": "<p>Body text here.",
        },
    )
    async with httpx.AsyncClient() as client:
        stories = await fetch_hn_stories_by_ids([3], client)
    s = stories[0]
    assert s.url == "https://news.ycombinator.com/item?id=3"
    assert "Body text here" in s.body


@pytest.mark.asyncio
async def test_fetch_hn_stories_http_error_returns_empty(httpx_mock: HTTPXMock):
    httpx_mock.add_response(url=f"{HN_BASE}/item/99.json", status_code=500)
    async with httpx.AsyncClient() as client:
        stories = await fetch_hn_stories_by_ids([99], client)
    assert stories == []


@pytest.mark.asyncio
async def test_fetch_hn_stories_multiple_ids_filtered(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url=f"{HN_BASE}/item/10.json",
        json={
            "id": 10,
            "type": "story",
            "title": "A",
            "url": "https://a.com",
            "score": 1,
            "descendants": 0,
        },
    )
    httpx_mock.add_response(url=f"{HN_BASE}/item/11.json", json={"id": 11, "type": "comment"})
    async with httpx.AsyncClient() as client:
        stories = await fetch_hn_stories_by_ids([10, 11], client)
    assert len(stories) == 1
    assert stories[0].id == 10


@pytest.mark.asyncio
async def test_fetch_hn_stories_by_ids_no_client(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url=f"{HN_BASE}/item/5.json",
        json={
            "id": 5,
            "type": "story",
            "title": "No Client Story",
            "url": "https://noclient.com",
            "score": 10,
            "descendants": 1,
        },
    )
    stories = await fetch_hn_stories_by_ids([5])
    assert len(stories) == 1
    assert stories[0].title == "No Client Story"


@pytest.mark.asyncio
async def test_fetch_hn_stories_convenience(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url=f"{HN_BASE}/topstories.json",
        json=[20, 21],
    )
    httpx_mock.add_response(
        url=f"{HN_BASE}/item/20.json",
        json={
            "id": 20,
            "type": "story",
            "title": "Story A",
            "url": "https://a.com",
            "score": 5,
            "descendants": 0,
        },
    )
    httpx_mock.add_response(
        url=f"{HN_BASE}/item/21.json",
        json={
            "id": 21,
            "type": "story",
            "title": "Story B",
            "url": "https://b.com",
            "score": 3,
            "descendants": 0,
        },
    )
    stories = await fetch_hn_stories(count=2)
    assert len(stories) == 2
    titles = {s.title for s in stories}
    assert "Story A" in titles
    assert "Story B" in titles


@pytest.mark.asyncio
async def test_fetch_hn_stories_with_client(httpx_mock: HTTPXMock):
    httpx_mock.add_response(url=f"{HN_BASE}/topstories.json", json=[30])
    httpx_mock.add_response(
        url=f"{HN_BASE}/item/30.json",
        json={
            "id": 30,
            "type": "story",
            "title": "With Client",
            "url": "https://wc.com",
            "score": 1,
            "descendants": 0,
        },
    )
    async with httpx.AsyncClient() as client:
        stories = await fetch_hn_stories(count=1, client=client)
    assert stories[0].title == "With Client"
