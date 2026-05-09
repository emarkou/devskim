from __future__ import annotations

import base64
import re
import time
from dataclasses import dataclass, field

import httpx

USER_AGENT = "grokfeed:v0.1.0 (terminal feed reader)"
TRENDING_URL = "https://github.com/trending"
README_API = "https://api.github.com/repos/{repo}/readme"


@dataclass
class GitHubRepo:
    owner: str
    name: str
    description: str = ""
    language: str = ""
    stars: int = 0
    stars_today: int = 0
    forks: int = 0
    created_at: int = field(default_factory=lambda: int(time.time()))

    @property
    def title(self) -> str:
        return f"{self.owner}/{self.name}"

    @property
    def url(self) -> str:
        return f"https://github.com/{self.owner}/{self.name}"

    @property
    def id(self) -> str:
        return f"{self.owner}/{self.name}"

    @property
    def body(self) -> str:
        """Markdown stats card for the split view left pane."""
        rows = [
            f"## {self.owner}/{self.name}\n",
            f"{self.description}\n" if self.description else "",
            "\n| | |\n|---|---|\n",
            f"| ⭐ Stars | {self.stars:,} |\n",
            f"| 🔥 Today | +{self.stars_today:,} stars |\n",
            f"| 🍴 Forks | {self.forks:,} |\n",
        ]
        if self.language:
            rows.append(f"| 💻 Language | {self.language} |\n")
        return "".join(rows)


def _parse_repos(html: str, count: int) -> list[GitHubRepo]:
    repos: list[GitHubRepo] = []
    for article in re.split(r"<article\b[^>]*>", html)[1:]:
        if len(repos) >= count:
            break

        # owner/repo from h2 link
        h2_m = re.search(r"<h2[^>]*>(.*?)</h2>", article, re.DOTALL)
        if not h2_m:
            continue
        href_m = re.search(r'href="(/[^/"]+/[^/"]+)"', h2_m.group(1))
        if not href_m:
            continue
        parts = href_m.group(1).strip("/").split("/")
        if len(parts) != 2:
            continue
        owner, name = parts

        # description
        desc_m = re.search(r'<p\s[^>]*col-9[^>]*>(.*?)</p>', article, re.DOTALL)
        description = ""
        if desc_m:
            description = re.sub(r"<[^>]+>", "", desc_m.group(1)).strip()

        # language
        lang_m = re.search(r'itemprop="programmingLanguage"[^>]*>(.*?)</span>', article)
        language = lang_m.group(1).strip() if lang_m else ""

        # total stars
        stars_m = re.search(
            rf'href="/{re.escape(owner)}/{re.escape(name)}/stargazers"[^>]*>'
            r".*?([\d,]+)\s*</a>",
            article,
            re.DOTALL,
        )
        stars = int(stars_m.group(1).replace(",", "")) if stars_m else 0

        # forks
        forks_m = re.search(
            rf'href="/{re.escape(owner)}/{re.escape(name)}/network/members"[^>]*>'
            r".*?([\d,]+)\s*</a>",
            article,
            re.DOTALL,
        )
        forks = int(forks_m.group(1).replace(",", "")) if forks_m else 0

        # stars today
        today_m = re.search(r"([\d,]+)\s+stars?\s+today", article)
        stars_today = int(today_m.group(1).replace(",", "")) if today_m else 0

        repos.append(
            GitHubRepo(
                owner=owner,
                name=name,
                description=description,
                language=language,
                stars=stars,
                stars_today=stars_today,
                forks=forks,
            )
        )
    return repos


async def fetch_github_trending(
    count: int = 25,
    language: str = "",
    since: str = "daily",
    client: httpx.AsyncClient | None = None,
) -> list[GitHubRepo]:
    """Scrape GitHub trending repos page."""
    url = f"{TRENDING_URL}/{language}?since={since}" if language else f"{TRENDING_URL}?since={since}"
    headers = {"User-Agent": USER_AGENT}

    async def _run(c: httpx.AsyncClient) -> list[GitHubRepo]:
        try:
            r = await c.get(url, timeout=15)
            r.raise_for_status()
            return _parse_repos(r.text, count)
        except Exception:
            return []

    if client is not None:
        return await _run(client)
    async with httpx.AsyncClient(headers=headers) as c:
        return await _run(c)


async def fetch_github_readme(repo: str, client: httpx.AsyncClient | None = None) -> str:
    """Fetch and decode the README for owner/repo. Returns empty string on failure."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/vnd.github.v3+json",
    }
    url = README_API.format(repo=repo)

    async def _run(c: httpx.AsyncClient) -> str:
        try:
            r = await c.get(url, timeout=15)
            r.raise_for_status()
            data = r.json()
            if data.get("encoding") == "base64":
                return base64.b64decode(data["content"]).decode("utf-8", errors="replace")
            return ""
        except Exception:
            return ""

    if client is not None:
        return await _run(client)
    async with httpx.AsyncClient(headers=headers) as c:
        return await _run(c)
