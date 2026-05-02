from __future__ import annotations

import asyncio
from dataclasses import dataclass

import httpx

USER_AGENT = "grokfeed:v0.1.0 (terminal feed reader)"
REDDIT_HOT = "https://www.reddit.com/r/{subreddit}/hot.json?limit={limit}"


@dataclass
class RedditPost:
    id: str
    title: str
    url: str
    score: int
    comments: int
    subreddit: str
    body: str = ""  # selftext for text posts; empty for link posts
    created_at: int = 0

    @property
    def source(self) -> str:
        return f"r/{self.subreddit}"


REDDIT_HOT_AFTER = "https://www.reddit.com/r/{subreddit}/hot.json?limit={limit}&after={after}"


async def _fetch_subreddit(
    client: httpx.AsyncClient,
    subreddit: str,
    count: int,
    after: str = "",
) -> tuple[list[RedditPost], str]:
    posts: list[RedditPost] = []
    new_after = ""
    try:
        url = (
            REDDIT_HOT_AFTER.format(subreddit=subreddit, limit=count, after=after)
            if after
            else REDDIT_HOT.format(subreddit=subreddit, limit=count)
        )
        r = await client.get(url, timeout=15, headers={"User-Agent": USER_AGENT})
        r.raise_for_status()
        data = r.json()
        listing = data.get("data", {})
        new_after = listing.get("after") or ""
        for child in listing.get("children", []):
            d = child.get("data", {})
            selftext = d.get("selftext", "")
            permalink = f"https://reddit.com{d.get('permalink', '')}"
            post_url = d.get("url") or permalink
            posts.append(
                RedditPost(
                    id=d.get("id", ""),
                    title=d.get("title", "(no title)"),
                    url=permalink if d.get("is_self") else post_url,
                    score=d.get("score", 0),
                    comments=d.get("num_comments", 0),
                    subreddit=subreddit,
                    body=selftext if selftext not in ("", "[deleted]", "[removed]") else "",
                    created_at=int(d.get("created_utc", 0)),
                )
            )
    except Exception:
        pass
    return posts, new_after


async def fetch_reddit_posts(
    subreddits: list[str],
    count: int = 15,
    client: httpx.AsyncClient | None = None,
    after: dict[str, str] | None = None,
) -> tuple[list[RedditPost], dict[str, str]]:
    after = after or {}

    async def _run(c: httpx.AsyncClient) -> tuple[list[RedditPost], dict[str, str]]:
        tasks = [_fetch_subreddit(c, sub, count, after.get(sub, "")) for sub in subreddits]
        results = await asyncio.gather(*tasks)
        posts: list[RedditPost] = []
        new_after: dict[str, str] = {}
        for sub, (batch, cursor) in zip(subreddits, results, strict=False):
            posts.extend(batch)
            if cursor:
                new_after[sub] = cursor
        return posts, new_after

    if client is not None:
        return await _run(client)
    async with httpx.AsyncClient() as c:
        return await _run(c)
