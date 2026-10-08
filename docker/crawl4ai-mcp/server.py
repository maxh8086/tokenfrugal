"""Thin stdio MCP wrapper over a local Crawl4AI service (open-source Firecrawl replacement)."""
import os

import httpx
from fastmcp import FastMCP

BASE = os.environ.get("CRAWL4AI_URL", "http://host.docker.internal:11235").rstrip("/")
SEARX = os.environ.get("SEARXNG_URL", "http://host.docker.internal:8088").rstrip("/")
mcp = FastMCP("crawl4ai")


def _post(path: str, body: dict) -> dict:
    tok = os.environ.get("CRAWL4AI_API_TOKEN", "")
    headers = {"Authorization": f"Bearer {tok}"} if tok else {}
    r = httpx.post(f"{BASE}{path}", json=body, headers=headers, timeout=120)
    r.raise_for_status()
    return r.json()


def _first(data: dict) -> dict:
    res = data.get("results") or [{}]
    return res[0]


@mcp.tool()
def crawl_markdown(url: str) -> str:
    """Fetch a web page and return it as clean markdown."""
    data = _post("/crawl", {"urls": [url]})
    md = _first(data).get("markdown", "")
    return md.get("raw_markdown", "") if isinstance(md, dict) else str(md)


@mcp.tool()
def crawl_links(url: str) -> dict:
    """Fetch a web page and return its internal and external links."""
    return _first(_post("/crawl", {"urls": [url]})).get("links", {})


@mcp.tool()
def web_search(query: str, max_results: int = 5) -> str:
    """Search the web (local SearXNG). Returns title, URL and snippet per result; crawl a URL for full text."""
    r = httpx.get(f"{SEARX}/search", params={"q": query, "format": "json"}, timeout=30)
    r.raise_for_status()
    hits = r.json().get("results", [])[:max_results]
    return chr(10).join(f"{h.get('title','')} | {h.get('url','')} | {(h.get('content') or '')[:200]}" for h in hits) or "no results"


if __name__ == "__main__":
    mcp.run()
