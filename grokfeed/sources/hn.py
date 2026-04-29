from __future__ import annotations

import asyncio
from dataclasses import dataclass

import httpx

HN_BASE = "https://hacker-news.firebaseio.com/v0"
HN_ITEM = HN_BASE + "/item/{}.json"
HN_TOP = HN_BASE + "/topstories.json"


import html as _html
import re as _re


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


async def fetch_hn_stories(count: int = 30) -> list[Story]:
    async with httpx.AsyncClient() as client:
        r = await client.get(HN_TOP, timeout=10)
        r.raise_for_status()
        ids = r.json()[:count]
        tasks = [_fetch_item(client, i) for i in ids]
        results = await asyncio.gather(*tasks)
    return [s for s in results if s is not None]
