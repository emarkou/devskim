from __future__ import annotations

import html as _html
import re as _re
from dataclasses import dataclass, field

import httpx


def _strip_html(raw: str) -> str:
    text = _re.sub(r"<p>", "\n\n", raw)
    text = _re.sub(r"<[^>]+>", "", text)
    return _html.unescape(text).strip()

LOBSTERS_URL = "https://lobste.rs/hottest.json"
USER_AGENT = "grokfeed:v0.1.0 (terminal feed reader)"


@dataclass
class LobstersPost:
    id: str
    title: str
    url: str
    score: int
    comments: int
    body: str = ""  # description for discussion posts
    source: str = "lobste.rs"


async def fetch_lobsters_posts(count: int = 25) -> list[LobstersPost]:
    headers = {"User-Agent": USER_AGENT}
    async with httpx.AsyncClient(headers=headers) as client:
        try:
            r = await client.get(LOBSTERS_URL, timeout=15)
            r.raise_for_status()
            data = r.json()
        except Exception:
            return []

    posts: list[LobstersPost] = []
    for item in data[:count]:
        raw_desc = item.get("description", "")
        ext_url = item.get("url", "")
        posts.append(LobstersPost(
            id=item.get("short_id", ""),
            title=item.get("title", "(no title)"),
            url=ext_url or item.get("comments_url", ""),
            score=item.get("score", 0),
            comments=item.get("comment_count", 0),
            body=_strip_html(raw_desc) if raw_desc else "",
        ))
    return posts
