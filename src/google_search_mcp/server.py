"""
Google Search MCP Server

A Model Context Protocol (MCP) server that performs real Google searches
using headless Chromium (via Playwright) and returns structured results.

Tools provided:
    - google_search: Search Google with optional time filtering, site filtering, and pagination
    - google_news: Search Google News for recent headlines
    - visit_page: Fetch a URL and return its text content
"""

import re
from urllib.parse import quote_plus

from mcp.server.fastmcp import FastMCP
from playwright.async_api import async_playwright

mcp = FastMCP("google-search")

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux aarch64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

# Google's time filter parameter values
TIME_RANGE_MAP = {
    "past_hour": "qdr:h",
    "past_day": "qdr:d",
    "past_week": "qdr:w",
    "past_month": "qdr:m",
    "past_year": "qdr:y",
}


async def _launch_browser(pw):
    """Launch a headless Chromium browser with standard settings."""
    browser = await pw.chromium.launch(
        headless=True,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
        ],
    )
    context = await browser.new_context(
        user_agent=USER_AGENT,
        viewport={"width": 1280, "height": 800},
        locale="en-US",
    )
    return browser, context


async def _dismiss_consent(page):
    """Dismiss Google consent banner if present."""
    try:
        consent_btn = page.locator(
            "button:has-text('Accept all'), "
            "button:has-text('Accept All'), "
            "button:has-text('I agree'), "
            "button:has-text('Reject all'), "
            "button:has-text('Reject All')"
        )
        if await consent_btn.count() > 0:
            await consent_btn.first.click()
            await page.wait_for_load_state("domcontentloaded", timeout=5000)
    except Exception:
        pass


async def _do_google_search(
    query: str,
    num_results: int = 5,
    time_range: str | None = None,
    site: str | None = None,
    page: int = 1,
) -> str:
    """Launch headless Chromium, search Google, and scrape results."""
    # Build the search query
    search_query = query
    if site:
        search_query = f"site:{site} {search_query}"

    # Build URL with parameters
    encoded_query = quote_plus(search_query)
    start = (page - 1) * num_results
    url = f"https://www.google.com/search?q={encoded_query}&hl=en&num={num_results + 5}"
    if start > 0:
        url += f"&start={start}"
    if time_range and time_range in TIME_RANGE_MAP:
        url += f"&tbs={TIME_RANGE_MAP[time_range]}"

    async with async_playwright() as pw:
        browser, context = await _launch_browser(pw)
        browser_page = await context.new_page()

        try:
            await browser_page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await _dismiss_consent(browser_page)
            await browser_page.wait_for_selector("div#search", timeout=15000)

            results = await browser_page.evaluate(
                """
                (numResults) => {
                    const results = [];

                    // Strategy 1: Standard search result divs
                    const containers = document.querySelectorAll('div#search div.g');
                    for (const el of containers) {
                        if (results.length >= numResults) break;

                        const linkEl = el.querySelector('a[href^="http"]');
                        const titleEl = el.querySelector('h3');
                        const snippetEl = el.querySelector(
                            'div[data-sncf], div.VwiC3b, span.aCOpRe, div[style*="-webkit-line-clamp"]'
                        );

                        if (linkEl && titleEl) {
                            results.push({
                                title: titleEl.innerText.trim(),
                                url: linkEl.href,
                                snippet: snippetEl ? snippetEl.innerText.trim() : ''
                            });
                        }
                    }

                    // Strategy 2: Fallback if Strategy 1 yields nothing
                    if (results.length === 0) {
                        const allLinks = document.querySelectorAll('div#search a[href^="http"]');
                        for (const a of allLinks) {
                            if (results.length >= numResults) break;
                            const h3 = a.querySelector('h3');
                            if (h3) {
                                const parent = a.closest('div.g') || a.parentElement?.parentElement;
                                const snippetEl = parent?.querySelector(
                                    'div[data-sncf], div.VwiC3b, span.aCOpRe, div[style*="-webkit-line-clamp"]'
                                );
                                results.push({
                                    title: h3.innerText.trim(),
                                    url: a.href,
                                    snippet: snippetEl ? snippetEl.innerText.trim() : ''
                                });
                            }
                        }
                    }

                    return results;
                }
                """,
                num_results,
            )

            if not results:
                return f"No results found for: {query}"

            # Format results as readable text
            header = f"Google Search Results for: {query}"
            if time_range:
                header += f" (filtered: {time_range.replace('_', ' ')})"
            if site:
                header += f" (site: {site})"
            if page > 1:
                header += f" (page {page})"

            lines = [header + "\n"]
            offset = (page - 1) * num_results
            for i, r in enumerate(results[:num_results], offset + 1):
                lines.append(f"{i}. {r['title']}")
                lines.append(f"   URL: {r['url']}")
                if r.get("snippet"):
                    lines.append(f"   {r['snippet']}")
                lines.append("")

            return "\n".join(lines)

        except Exception as e:
            return f"Search failed: {e}"

        finally:
            await browser.close()


@mcp.tool()
async def google_search(
    query: str,
    num_results: int = 5,
    time_range: str = "",
    site: str = "",
    page: int = 1,
) -> str:
    """Search Google and return results with titles, URLs, and snippets.

    Args:
        query: The search query string.
        num_results: Number of results to return (default 5, max 10).
        time_range: Filter by time. One of: "past_hour", "past_day", "past_week", "past_month", "past_year". Leave empty for no filter.
        site: Limit results to a specific domain (e.g. "reddit.com", "stackoverflow.com"). Leave empty for all sites.
        page: Results page number (default 1). Use 2, 3, etc. to get more results.
    """
    num_results = max(1, min(num_results, 10))
    page = max(1, min(page, 10))
    return await _do_google_search(
        query,
        num_results,
        time_range=time_range or None,
        site=site or None,
        page=page,
    )


async def _do_google_news(query: str, num_results: int = 5) -> str:
    """Launch headless Chromium, search Google News, and scrape results."""
    encoded_query = quote_plus(query)
    url = f"https://www.google.com/search?q={encoded_query}&hl=en&tbm=nws&num={num_results + 5}"

    async with async_playwright() as pw:
        browser, context = await _launch_browser(pw)
        page = await context.new_page()

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await _dismiss_consent(page)
            await page.wait_for_selector("div#search", timeout=15000)

            results = await page.evaluate(
                """
                (numResults) => {
                    const results = [];

                    // News results can appear in different structures
                    // Strategy 1: Standard news result divs
                    const containers = document.querySelectorAll('div#search div.SoaBEf, div#search div.g');
                    for (const el of containers) {
                        if (results.length >= numResults) break;

                        const linkEl = el.querySelector('a[href^="http"]');
                        const titleEl = el.querySelector('div[role="heading"], h3');
                        const sourceEl = el.querySelector('.NUnG9d, .CEMjEf, .UPmit');
                        const timeEl = el.querySelector('.OSrXXb, .WG9SHc, .ZE0LJd span, time, [datetime]');
                        const snippetEl = el.querySelector('.GI74Re, .Y3v8qd, div.VwiC3b');

                        if (linkEl && titleEl) {
                            results.push({
                                title: titleEl.innerText.trim(),
                                url: linkEl.href,
                                source: sourceEl ? sourceEl.innerText.trim() : '',
                                time: timeEl ? timeEl.innerText.trim() : '',
                                snippet: snippetEl ? snippetEl.innerText.trim() : ''
                            });
                        }
                    }

                    // Strategy 2: Fallback - look for any linked headings
                    if (results.length === 0) {
                        const allLinks = document.querySelectorAll('div#search a[href^="http"]');
                        for (const a of allLinks) {
                            if (results.length >= numResults) break;
                            const heading = a.querySelector('div[role="heading"], h3');
                            if (heading) {
                                const parent = a.closest('div.SoaBEf') || a.closest('div.g') || a.parentElement;
                                results.push({
                                    title: heading.innerText.trim(),
                                    url: a.href,
                                    source: '',
                                    time: '',
                                    snippet: ''
                                });
                            }
                        }
                    }

                    return results;
                }
                """,
                num_results,
            )

            if not results:
                return f"No news results found for: {query}"

            lines = [f"Google News Results for: {query}\n"]
            for i, r in enumerate(results[:num_results], 1):
                lines.append(f"{i}. {r['title']}")
                lines.append(f"   URL: {r['url']}")
                source_info = []
                if r.get("source"):
                    source_info.append(r["source"])
                if r.get("time"):
                    source_info.append(r["time"])
                if source_info:
                    lines.append(f"   Source: {' — '.join(source_info)}")
                if r.get("snippet"):
                    lines.append(f"   {r['snippet']}")
                lines.append("")

            return "\n".join(lines)

        except Exception as e:
            return f"News search failed: {e}"

        finally:
            await browser.close()


@mcp.tool()
async def google_news(query: str, num_results: int = 5) -> str:
    """Search Google News for recent headlines and articles.

    Args:
        query: The news search query string.
        num_results: Number of results to return (default 5, max 10).
    """
    num_results = max(1, min(num_results, 10))
    return await _do_google_news(query, num_results)


MAX_PAGE_CHARS = 8000


async def _fetch_page_text(url: str) -> str:
    """Fetch a URL with headless Chromium and extract readable text."""
    async with async_playwright() as pw:
        browser, context = await _launch_browser(pw)
        page = await context.new_page()

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(2000)

            text = await page.evaluate("""
                () => {
                    // Remove elements that add noise
                    const remove = document.querySelectorAll(
                        'script, style, nav, footer, header, iframe, noscript, '
                        + 'svg, [role="navigation"], [role="banner"], '
                        + '[role="complementary"], .sidebar, .ad, .ads, .advertisement'
                    );
                    remove.forEach(el => el.remove());

                    // Try article/main content first
                    const article = document.querySelector(
                        'article, main, [role="main"], .post-content, .article-body, '
                        + '.entry-content, .content, #content'
                    );
                    const source = article || document.body;
                    return source ? source.innerText : '';
                }
            """)

            text = re.sub(r'\n{3,}', '\n\n', text).strip()

            if not text:
                return f"Could not extract text content from: {url}"

            if len(text) > MAX_PAGE_CHARS:
                text = text[:MAX_PAGE_CHARS] + f"\n\n... [truncated, showing first {MAX_PAGE_CHARS} characters]"

            return f"Content from: {url}\n\n{text}"

        except Exception as e:
            return f"Failed to fetch {url}: {e}"

        finally:
            await browser.close()


@mcp.tool()
async def visit_page(url: str) -> str:
    """Fetch a web page and return its text content. Use this after google_search to read the actual content of a result.

    Args:
        url: The full URL to visit and extract text from.
    """
    return await _fetch_page_text(url)
