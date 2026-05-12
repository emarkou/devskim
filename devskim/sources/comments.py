from __future__ import annotations

import asyncio
import html as _html
import re as _re
from dataclasses import dataclass

import httpx

USER_AGENT = "devskim:v0.1.0 (terminal feed reader)"
HN_ITEM = "https://hacker-news.firebaseio.com/v0/item/{}.json"
REDDIT_COMMENTS = "https://www.reddit.com/r/{subreddit}/comments/{post_id}.json?limit=50&depth=3"
LOBSTERS_POST = "https://lobste.rs/s/{short_id}.json"


@dataclass
class Comment:
    """A single comment with author, score, plain-text body, and nesting depth."""

    author: str
    score: int
    body: str
    depth: int = 0


def _strip_html(raw: str) -> str:
    text = _re.sub(r"<p>", "\n\n", raw)
    text = _re.sub(r"<[^>]+>", "", text)
    return _html.unescape(text).strip()


# ── HN ────────────────────────────────────────────────────────────────────────


async def _fetch_hn_comment(
    client: httpx.AsyncClient, sem: asyncio.Semaphore, cid: int
) -> Comment | None:
    async with sem:
        try:
            r = await client.get(HN_ITEM.format(cid), timeout=10)
            r.raise_for_status()
            d = r.json()
            if not d or d.get("deleted") or d.get("dead") or d.get("type") != "comment":
                return None
            raw = d.get("text", "")
            return Comment(
                author=d.get("by", "[deleted]"),
                score=0,  # HN comments have no score in API
                body=_strip_html(raw) if raw else "",
                depth=0,
            )
        except Exception:
            return None


async def fetch_hn_comments(story_id: int, limit: int = 30) -> list[Comment]:
    """Fetch top-level comments for a HN story."""
    sem = asyncio.Semaphore(10)
    async with httpx.AsyncClient() as client:
        r = await client.get(HN_ITEM.format(story_id), timeout=10)
        r.raise_for_status()
        d = r.json()
        kids = (d.get("kids") or [])[:limit]
        tasks = [_fetch_hn_comment(client, sem, kid) for kid in kids]
        results = await asyncio.gather(*tasks)
    return [c for c in results if c is not None]


# ── Reddit ─────────────────────────────────────────────────────────────────────


def _flatten_reddit(children: list, depth: int = 0, max_depth: int = 2) -> list[Comment]:
    out: list[Comment] = []
    for child in children:
        if child.get("kind") != "t1":
            continue
        d = child.get("data", {})
        body = d.get("body", "")
        if body in ("[deleted]", "[removed]", ""):
            continue
        out.append(
            Comment(
                author=d.get("author", "[deleted]"),
                score=d.get("score", 0),
                body=body,
                depth=depth,
            )
        )
        if depth < max_depth:
            replies = d.get("replies", "")
            if isinstance(replies, dict):
                reply_children = replies.get("data", {}).get("children", [])
                out.extend(_flatten_reddit(reply_children, depth + 1, max_depth))
    return out


async def fetch_reddit_comments(subreddit: str, post_id: str) -> list[Comment]:
    """Fetch and flatten threaded comments for a Reddit post (depth ≤ 3)."""
    headers = {"User-Agent": USER_AGENT}
    url = REDDIT_COMMENTS.format(subreddit=subreddit, post_id=post_id)
    async with httpx.AsyncClient(headers=headers) as client:
        try:
            r = await client.get(url, timeout=15)
            r.raise_for_status()
            data = r.json()
        except Exception:
            return []
    # data is [post_listing, comments_listing]
    if not isinstance(data, list) or len(data) < 2:
        return []
    children = data[1].get("data", {}).get("children", [])
    return _flatten_reddit(children)


# ── lobste.rs ──────────────────────────────────────────────────────────────────


async def fetch_lobsters_comments(short_id: str) -> list[Comment]:
    """Fetch comments for a lobste.rs post."""
    headers = {"User-Agent": USER_AGENT}
    url = LOBSTERS_POST.format(short_id=short_id)
    async with httpx.AsyncClient(headers=headers) as client:
        try:
            r = await client.get(url, timeout=15)
            r.raise_for_status()
            data = r.json()
        except Exception:
            return []
    out: list[Comment] = []
    for c in data.get("comments", []):
        raw = c.get("comment", "")
        body = _strip_html(raw) if raw else ""
        if not body:
            continue
        raw_user = c.get("commenting_user", "?")
        author = raw_user if isinstance(raw_user, str) else raw_user.get("username", "?")
        out.append(
            Comment(
                author=author,
                score=c.get("score", 0),
                body=body,
                depth=c.get("indent_level", 0),
            )
        )
    return out


# ── Dispatcher ─────────────────────────────────────────────────────────────────


async def fetch_comments(item: dict) -> list[Comment]:
    """Dispatch to the correct comment fetcher based on item source."""
    source = item.get("source", "")
    if source == "HN":
        return await fetch_hn_comments(int(item["post_id"]))
    elif source.startswith("r/"):
        return await fetch_reddit_comments(item["subreddit"], item["post_id"])
    elif source == "lobste.rs":
        return await fetch_lobsters_comments(item["post_id"])
    elif source == "GitHub":
        from .github import fetch_github_readme

        readme = await fetch_github_readme(item["post_id"])
        if readme:
            return [Comment(author="README.md", score=0, body=readme, depth=0)]
        return []
    return []
