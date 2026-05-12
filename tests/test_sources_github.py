import base64

import httpx
import pytest
from pytest_httpx import HTTPXMock

from devskim.sources.github import (
    README_API,
    TRENDING_URL,
    _parse_repos,
    fetch_github_readme,
    fetch_github_trending,
)

# Minimal trending page HTML with two repos
TRENDING_HTML = """
<html><body>
<article class="Box-row">
  <h2 class="h3 lh-condensed">
    <a href="/octocat/Hello-World">octocat / Hello-World</a>
  </h2>
  <p class="col-9 color-fg-muted my-1 pr-4">My first repository on GitHub!</p>
  <span itemprop="programmingLanguage">Python</span>
  <a class="Link--muted" href="/octocat/Hello-World/stargazers">1,234</a>
  <a class="Link--muted" href="/octocat/Hello-World/network/members">567</a>
  <span>89 stars today</span>
</article>
<article class="Box-row">
  <h2 class="h3 lh-condensed">
    <a href="/torvalds/linux">torvalds / linux</a>
  </h2>
  <p class="col-9 color-fg-muted my-1 pr-4">Linux kernel source tree</p>
  <span itemprop="programmingLanguage">C</span>
  <a class="Link--muted" href="/torvalds/linux/stargazers">200,000</a>
  <a class="Link--muted" href="/torvalds/linux/network/members">50,000</a>
  <span>500 stars today</span>
</article>
</body></html>
"""


def test_parse_repos_count():
    repos = _parse_repos(TRENDING_HTML, count=10)
    assert len(repos) == 2


def test_parse_repos_fields():
    repos = _parse_repos(TRENDING_HTML, count=10)
    r = repos[0]
    assert r.owner == "octocat"
    assert r.name == "Hello-World"
    assert r.description == "My first repository on GitHub!"
    assert r.language == "Python"
    assert r.stars == 1234
    assert r.forks == 567
    assert r.stars_today == 89


def test_parse_repos_respects_count():
    repos = _parse_repos(TRENDING_HTML, count=1)
    assert len(repos) == 1
    assert repos[0].owner == "octocat"


def test_parse_repos_title_and_url():
    repos = _parse_repos(TRENDING_HTML, count=10)
    r = repos[1]
    assert r.title == "torvalds/linux"
    assert r.url == "https://github.com/torvalds/linux"
    assert r.id == "torvalds/linux"


def test_parse_repos_body_contains_stats():
    repos = _parse_repos(TRENDING_HTML, count=10)
    body = repos[0].body
    assert "1,234" in body
    assert "+89" in body
    assert "Python" in body


@pytest.mark.asyncio
async def test_fetch_github_trending(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url=f"{TRENDING_URL}?since=daily",
        text=TRENDING_HTML,
    )
    repos = await fetch_github_trending(count=10, language="", since="daily")
    assert len(repos) == 2
    assert repos[0].owner == "octocat"


@pytest.mark.asyncio
async def test_fetch_github_trending_with_language(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url=f"{TRENDING_URL}/python?since=weekly",
        text=TRENDING_HTML,
    )
    repos = await fetch_github_trending(count=10, language="python", since="weekly")
    assert len(repos) == 2


@pytest.mark.asyncio
async def test_fetch_github_trending_http_error(httpx_mock: HTTPXMock):
    httpx_mock.add_response(url=f"{TRENDING_URL}?since=daily", status_code=503)
    repos = await fetch_github_trending()
    assert repos == []


@pytest.mark.asyncio
async def test_fetch_github_readme(httpx_mock: HTTPXMock):
    content = base64.b64encode(b"# Hello\nThis is the README.").decode()
    httpx_mock.add_response(
        url=README_API.format(repo="octocat/Hello-World"),
        json={"encoding": "base64", "content": content},
    )
    readme = await fetch_github_readme("octocat/Hello-World")
    assert readme == "# Hello\nThis is the README."


@pytest.mark.asyncio
async def test_fetch_github_readme_failure(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url=README_API.format(repo="octocat/missing"),
        status_code=404,
    )
    readme = await fetch_github_readme("octocat/missing")
    assert readme == ""


@pytest.mark.asyncio
async def test_fetch_github_readme_with_client(httpx_mock: HTTPXMock):
    content = base64.b64encode(b"readme content").decode()
    httpx_mock.add_response(
        url=README_API.format(repo="owner/repo"),
        json={"encoding": "base64", "content": content},
    )
    async with httpx.AsyncClient() as client:
        readme = await fetch_github_readme("owner/repo", client=client)
    assert readme == "readme content"


@pytest.mark.asyncio
async def test_fetch_github_trending_with_client(httpx_mock: HTTPXMock):
    httpx_mock.add_response(url=f"{TRENDING_URL}?since=daily", text=TRENDING_HTML)
    async with httpx.AsyncClient() as client:
        repos = await fetch_github_trending(count=10, client=client)
    assert len(repos) == 2


def test_parse_repos_missing_stars_forks_today():
    # Article with no star/fork/today spans — should default to 0
    html = """
    <article class="Box-row">
      <h2 class="h3"><a href="/owner/nometrics">owner / nometrics</a></h2>
      <p class="col-9 color-fg-muted my-1 pr-4">No metrics here</p>
    </article>
    """
    repos = _parse_repos(html, count=10)
    assert len(repos) == 1
    assert repos[0].stars == 0
    assert repos[0].forks == 0
    assert repos[0].stars_today == 0


def test_parse_repos_no_language():
    html = """
    <article class="Box-row">
      <h2 class="h3"><a href="/owner/repo">owner / repo</a></h2>
    </article>
    """
    repos = _parse_repos(html, count=10)
    assert len(repos) == 1
    assert repos[0].language == ""


def test_parse_repos_skips_bad_href():
    html = """
    <article class="Box-row">
      <h2 class="h3"><a href="/only-one-part">bad</a></h2>
    </article>
    <article class="Box-row">
      <h2 class="h3"><a href="/owner/repo">owner / repo</a></h2>
    </article>
    """
    repos = _parse_repos(html, count=10)
    assert len(repos) == 1
    assert repos[0].owner == "owner"
