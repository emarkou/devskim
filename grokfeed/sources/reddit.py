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

    @property
    def source(self) -> str:
        return f"r/{self.subreddit}"


async def _fetch_subreddit(
    client: httpx.AsyncClient, subreddit: str, count: int
) -> list[RedditPost]:
    posts: list[RedditPost] = []
    try:
        url = REDDIT_HOT.format(subreddit=subreddit, limit=count)
        r = await client.get(url, timeout=15, headers={"User-Agent": USER_AGENT})
        r.raise_for_status()
        data = r.json()
        for child in data.get("data", {}).get("children", []):
            d = child.get("data", {})
            selftext = d.get("selftext", "")
            permalink = f"https://reddit.com{d.get('permalink', '')}"
            # self-posts: url == permalink; fall back to permalink for open-in-browser
            post_url = d.get("url") or permalink
            posts.append(RedditPost(
                id=d.get("id", ""),
                title=d.get("title", "(no title)"),
                url=permalink if d.get("is_self") else post_url,
                score=d.get("score", 0),
                comments=d.get("num_comments", 0),
                subreddit=subreddit,
                body=selftext if selftext not in ("", "[deleted]", "[removed]") else "",
            ))
    except Exception:
        pass
    return posts


async def fetch_reddit_posts(
    subreddits: list[str],
    count: int = 15,
    client: httpx.AsyncClient | None = None,
) -> list[RedditPost]:
    headers = {"User-Agent": USER_AGENT}

    async def _run(c: httpx.AsyncClient) -> list[RedditPost]:
        tasks = [_fetch_subreddit(c, sub, count) for sub in subreddits]
        results = await asyncio.gather(*tasks)
        posts: list[RedditPost] = []
        for batch in results:
            posts.extend(batch)
        return posts

    if client is not None:
        return await _run(client)
    async with httpx.AsyncClient(headers=headers) as c:
        return await _run(c)
