from __future__ import annotations

import asyncio
import html as _html
import re as _re
from dataclasses import dataclass

import httpx

HN_BASE = "https://hacker-news.firebaseio.com/v0"
HN_ITEM = HN_BASE + "/item/{}.json"
HN_TOP = HN_BASE + "/topstories.json"




def _strip_html(raw: str) -> str:
    text = _re.sub(r"<p>", "\n\n", raw)
    text = _re.sub(r"<[^>]+>", "", text)
    return _html.unescape(text).strip()


@dataclass
class Story:
    id: int
    title: str
    url: str
    score: int
    comments: int
    body: str = ""  # present for Ask HN / Tell HN posts
    source: str = "HN"


async def _fetch_item(client: httpx.AsyncClient, item_id: int) -> Story | None:
    try:
        r = await client.get(HN_ITEM.format(item_id), timeout=10)
        r.raise_for_status()
        d = r.json()
        if not d or d.get("type") != "story":
            return None
        raw_text = d.get("text", "")
        return Story(
            id=d["id"],
            title=d.get("title", "(no title)"),
            url=d.get("url") or f"https://news.ycombinator.com/item?id={d['id']}",
            score=d.get("score", 0),
            comments=d.get("descendants", 0),
            body=_strip_html(raw_text) if raw_text else "",
        )
    except Exception:
        return None


async def fetch_hn_top_ids(client: httpx.AsyncClient) -> list[int]:
    r = await client.get(HN_TOP, timeout=10)
    r.raise_for_status()
    return r.json()


async def fetch_hn_stories_by_ids(
    ids: list[int],
    client: httpx.AsyncClient | None = None,
) -> list[Story]:
    async def _run(c: httpx.AsyncClient) -> list[Story]:
        sem = asyncio.Semaphore(10)

        async def _bounded(item_id: int) -> Story | None:
            async with sem:
                return await _fetch_item(c, item_id)

        results = await asyncio.gather(*[_bounded(i) for i in ids])
        return [s for s in results if s is not None]

    if client is not None:
        return await _run(client)
    async with httpx.AsyncClient() as c:
        return await _run(c)


async def fetch_hn_stories(
    count: int = 30,
    client: httpx.AsyncClient | None = None,
) -> list[Story]:
    async def _run(c: httpx.AsyncClient) -> list[Story]:
        ids = (await fetch_hn_top_ids(c))[:count]
        return await fetch_hn_stories_by_ids(ids, c)

    if client is not None:
        return await _run(client)
    async with httpx.AsyncClient() as c:
        return await _run(c)
