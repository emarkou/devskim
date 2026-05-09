import base64

import pytest
from pytest_httpx import HTTPXMock

from grokfeed.sources.comments import (
    HN_ITEM,
    LOBSTERS_POST,
    REDDIT_COMMENTS,
    _flatten_reddit,
    _strip_html,
    fetch_comments,
    fetch_hn_comments,
    fetch_lobsters_comments,
    fetch_reddit_comments,
)
from grokfeed.sources.github import README_API

# ── _strip_html ─────────────────────────────────────────────────────────────────


def test_strip_html_paragraph():
    assert "\n\n" in _strip_html("before<p>after")


def test_strip_html_removes_tags():
    assert _strip_html("<b>bold</b>") == "bold"


def test_strip_html_unescapes_entities():
    assert _strip_html("&amp;&lt;&gt;") == "&<>"


def test_strip_html_empty():
    assert _strip_html("") == ""


# ── _flatten_reddit ─────────────────────────────────────────────────────────────


def _make_child(author: str, body: str, depth: int = 0, replies=None) -> dict:
    child: dict = {
        "kind": "t1",
        "data": {"author": author, "body": body, "score": 10},
    }
    if replies:
        child["data"]["replies"] = {"data": {"children": replies}}
    else:
        child["data"]["replies"] = ""
    return child


def test_flatten_reddit_single_comment():
    children = [_make_child("alice", "hello")]
    result = _flatten_reddit(children)
    assert len(result) == 1
    assert result[0].author == "alice"
    assert result[0].body == "hello"
    assert result[0].depth == 0


def test_flatten_reddit_skips_deleted():
    children = [
        _make_child("alice", "[deleted]"),
        _make_child("bob", "[removed]"),
        _make_child("carol", "valid"),
    ]
    result = _flatten_reddit(children)
    assert len(result) == 1
    assert result[0].author == "carol"


def test_flatten_reddit_skips_non_t1():
    children = [{"kind": "more", "data": {}}, _make_child("alice", "hi")]
    result = _flatten_reddit(children)
    assert len(result) == 1


def test_flatten_reddit_nested_replies():
    reply = _make_child("child", "reply body")
    parent = _make_child("parent", "parent body", replies=[reply])
    result = _flatten_reddit([parent])
    assert len(result) == 2
    assert result[0].depth == 0
    assert result[1].depth == 1


def test_flatten_reddit_max_depth():
    # Nest 5 deep — should stop at max_depth=2
    inner = _make_child("d3", "deep")
    mid = _make_child("d2", "mid", replies=[inner])
    outer = _make_child("d1", "outer", replies=[mid])
    result = _flatten_reddit([outer])
    # d1 (depth 0), d2 (depth 1), d3 (depth 2) — d3's children are not included
    assert len(result) == 3


# ── fetch_hn_comments ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fetch_hn_comments_basic(httpx_mock: HTTPXMock):
    story_url = HN_ITEM.format(100)
    comment_url = HN_ITEM.format(42)
    httpx_mock.add_response(url=story_url, json={"kids": [42], "type": "story"})
    httpx_mock.add_response(
        url=comment_url,
        json={"id": 42, "type": "comment", "by": "alice", "text": "hello world"},
    )
    comments = await fetch_hn_comments(100)
    assert len(comments) == 1
    assert comments[0].author == "alice"
    assert comments[0].body == "hello world"
    assert comments[0].score == 0  # HN API has no comment scores


@pytest.mark.asyncio
async def test_fetch_hn_comments_skips_deleted(httpx_mock: HTTPXMock):
    httpx_mock.add_response(url=HN_ITEM.format(100), json={"kids": [42], "type": "story"})
    httpx_mock.add_response(url=HN_ITEM.format(42), json={"deleted": True, "type": "comment"})
    comments = await fetch_hn_comments(100)
    assert comments == []


@pytest.mark.asyncio
async def test_fetch_hn_comments_skips_dead(httpx_mock: HTTPXMock):
    httpx_mock.add_response(url=HN_ITEM.format(100), json={"kids": [42], "type": "story"})
    httpx_mock.add_response(
        url=HN_ITEM.format(42), json={"dead": True, "type": "comment", "by": "x", "text": "y"}
    )
    comments = await fetch_hn_comments(100)
    assert comments == []


@pytest.mark.asyncio
async def test_fetch_hn_comments_no_kids(httpx_mock: HTTPXMock):
    httpx_mock.add_response(url=HN_ITEM.format(100), json={"type": "story"})
    comments = await fetch_hn_comments(100)
    assert comments == []


@pytest.mark.asyncio
async def test_fetch_hn_comments_http_error(httpx_mock: HTTPXMock):
    httpx_mock.add_response(url=HN_ITEM.format(100), json={"kids": [42], "type": "story"})
    httpx_mock.add_response(url=HN_ITEM.format(42), status_code=500)
    comments = await fetch_hn_comments(100)
    assert comments == []


@pytest.mark.asyncio
async def test_fetch_hn_comments_strips_html(httpx_mock: HTTPXMock):
    httpx_mock.add_response(url=HN_ITEM.format(1), json={"kids": [2], "type": "story"})
    httpx_mock.add_response(
        url=HN_ITEM.format(2),
        json={"id": 2, "type": "comment", "by": "bob", "text": "<p>hello &amp; world"},
    )
    comments = await fetch_hn_comments(1)
    assert "hello & world" in comments[0].body


# ── fetch_reddit_comments ───────────────────────────────────────────────────────


def _reddit_response(children: list) -> list:
    return [
        {"data": {}},
        {"data": {"children": children}},
    ]


@pytest.mark.asyncio
async def test_fetch_reddit_comments_basic(httpx_mock: HTTPXMock):
    url = REDDIT_COMMENTS.format(subreddit="python", post_id="abc123")
    httpx_mock.add_response(
        url=url,
        json=_reddit_response([_make_child("alice", "great post")]),
    )
    comments = await fetch_reddit_comments("python", "abc123")
    assert len(comments) == 1
    assert comments[0].author == "alice"
    assert comments[0].body == "great post"


@pytest.mark.asyncio
async def test_fetch_reddit_comments_http_error(httpx_mock: HTTPXMock):
    url = REDDIT_COMMENTS.format(subreddit="python", post_id="bad")
    httpx_mock.add_response(url=url, status_code=403)
    comments = await fetch_reddit_comments("python", "bad")
    assert comments == []


@pytest.mark.asyncio
async def test_fetch_reddit_comments_malformed_response(httpx_mock: HTTPXMock):
    url = REDDIT_COMMENTS.format(subreddit="python", post_id="xyz")
    httpx_mock.add_response(url=url, json={"not": "a list"})
    comments = await fetch_reddit_comments("python", "xyz")
    assert comments == []


# ── fetch_lobsters_comments ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fetch_lobsters_comments_basic(httpx_mock: HTTPXMock):
    url = LOBSTERS_POST.format(short_id="abcd")
    httpx_mock.add_response(
        url=url,
        json={
            "comments": [
                {
                    "comment": "<p>nice post",
                    "commenting_user": "alice",
                    "score": 5,
                    "indent_level": 0,
                }
            ]
        },
    )
    comments = await fetch_lobsters_comments("abcd")
    assert len(comments) == 1
    assert comments[0].author == "alice"
    assert comments[0].score == 5
    assert "nice post" in comments[0].body


@pytest.mark.asyncio
async def test_fetch_lobsters_comments_dict_user(httpx_mock: HTTPXMock):
    url = LOBSTERS_POST.format(short_id="xyz1")
    httpx_mock.add_response(
        url=url,
        json={
            "comments": [
                {
                    "comment": "hello",
                    "commenting_user": {"username": "bob"},
                    "score": 2,
                    "indent_level": 1,
                }
            ]
        },
    )
    comments = await fetch_lobsters_comments("xyz1")
    assert comments[0].author == "bob"
    assert comments[0].depth == 1


@pytest.mark.asyncio
async def test_fetch_lobsters_comments_skips_empty_body(httpx_mock: HTTPXMock):
    url = LOBSTERS_POST.format(short_id="emp1")
    httpx_mock.add_response(
        url=url,
        json={
            "comments": [{"comment": "", "commenting_user": "alice", "score": 0, "indent_level": 0}]
        },
    )
    comments = await fetch_lobsters_comments("emp1")
    assert comments == []


@pytest.mark.asyncio
async def test_fetch_lobsters_comments_http_error(httpx_mock: HTTPXMock):
    url = LOBSTERS_POST.format(short_id="err1")
    httpx_mock.add_response(url=url, status_code=500)
    comments = await fetch_lobsters_comments("err1")
    assert comments == []


# ── fetch_comments dispatcher ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fetch_comments_dispatches_hn(httpx_mock: HTTPXMock):
    httpx_mock.add_response(url=HN_ITEM.format(42), json={"kids": [], "type": "story"})
    result = await fetch_comments({"source": "HN", "post_id": "42"})
    assert result == []


@pytest.mark.asyncio
async def test_fetch_comments_dispatches_reddit(httpx_mock: HTTPXMock):
    url = REDDIT_COMMENTS.format(subreddit="python", post_id="abc")
    httpx_mock.add_response(url=url, json=_reddit_response([]))
    result = await fetch_comments({"source": "r/python", "subreddit": "python", "post_id": "abc"})
    assert result == []


@pytest.mark.asyncio
async def test_fetch_comments_dispatches_lobsters(httpx_mock: HTTPXMock):
    url = LOBSTERS_POST.format(short_id="xyz")
    httpx_mock.add_response(url=url, json={"comments": []})
    result = await fetch_comments({"source": "lobste.rs", "post_id": "xyz"})
    assert result == []


@pytest.mark.asyncio
async def test_fetch_comments_dispatches_github_readme(httpx_mock: HTTPXMock):
    readme_content = base64.b64encode(b"# My Project\nAwesome repo.").decode()
    httpx_mock.add_response(
        url=README_API.format(repo="owner/repo"),
        json={"encoding": "base64", "content": readme_content},
    )
    result = await fetch_comments({"source": "GitHub", "post_id": "owner/repo"})
    assert len(result) == 1
    assert result[0].author == "README.md"
    assert "My Project" in result[0].body


@pytest.mark.asyncio
async def test_fetch_comments_dispatches_github_no_readme(httpx_mock: HTTPXMock):
    httpx_mock.add_response(url=README_API.format(repo="owner/empty"), status_code=404)
    result = await fetch_comments({"source": "GitHub", "post_id": "owner/empty"})
    assert result == []


@pytest.mark.asyncio
async def test_fetch_comments_unknown_source():
    result = await fetch_comments({"source": "unknown", "post_id": "1"})
    assert result == []
