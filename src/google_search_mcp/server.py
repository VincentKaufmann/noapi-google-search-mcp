"""
Google Search MCP Server

A Model Context Protocol (MCP) server that performs real Google searches
using headless Chromium (via Playwright) and returns structured results.

Tools provided:
    - google_search: Search with time filtering, site filtering, pagination, language/region
    - google_news: Search Google News for recent headlines
    - google_scholar: Search Google Scholar for academic papers
    - google_images: Search Google Images for image URLs
    - google_trends: Check Google Trends for topic interest over time
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


# ---------------------------------------------------------------------------
# google_search
# ---------------------------------------------------------------------------

async def _do_google_search(
    query: str,
    num_results: int = 5,
    time_range: str | None = None,
    site: str | None = None,
    page: int = 1,
    language: str | None = None,
    region: str | None = None,
) -> str:
    """Launch headless Chromium, search Google, and scrape results."""
    search_query = query
    if site:
        search_query = f"site:{site} {search_query}"

    encoded_query = quote_plus(search_query)
    start = (page - 1) * num_results
    url = f"https://www.google.com/search?q={encoded_query}&num={num_results + 5}"

    # Language and region
    if language:
        url += f"&lr=lang_{language}&hl={language}"
    else:
        url += "&hl=en"
    if region:
        url += f"&gl={region}"

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

            header = f"Google Search Results for: {query}"
            if time_range:
                header += f" (filtered: {time_range.replace('_', ' ')})"
            if site:
                header += f" (site: {site})"
            if language:
                header += f" (lang: {language})"
            if region:
                header += f" (region: {region})"
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
    language: str = "",
    region: str = "",
) -> str:
    """Search Google and return results with titles, URLs, and snippets.

    Args:
        query: The search query string.
        num_results: Number of results to return (default 5, max 10).
        time_range: Filter by time. One of: "past_hour", "past_day", "past_week", "past_month", "past_year". Leave empty for no filter.
        site: Limit results to a specific domain (e.g. "reddit.com", "stackoverflow.com", "github.com", "arxiv.org"). Leave empty for all sites.
        page: Results page number (default 1). Use 2, 3, etc. to get more results.
        language: Language code for results (e.g. "en", "de", "fr", "es", "ja", "zh"). Leave empty for English.
        region: Country/region code (e.g. "us", "gb", "de", "fr", "jp"). Leave empty for default.
    """
    num_results = max(1, min(num_results, 10))
    page = max(1, min(page, 10))
    return await _do_google_search(
        query,
        num_results,
        time_range=time_range or None,
        site=site or None,
        page=page,
        language=language or None,
        region=region or None,
    )


# ---------------------------------------------------------------------------
# google_news
# ---------------------------------------------------------------------------

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
                    if (results.length === 0) {
                        const allLinks = document.querySelectorAll('div#search a[href^="http"]');
                        for (const a of allLinks) {
                            if (results.length >= numResults) break;
                            const heading = a.querySelector('div[role="heading"], h3');
                            if (heading) {
                                results.push({
                                    title: heading.innerText.trim(),
                                    url: a.href,
                                    source: '', time: '', snippet: ''
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


# ---------------------------------------------------------------------------
# google_scholar
# ---------------------------------------------------------------------------

async def _do_google_scholar(query: str, num_results: int = 5) -> str:
    """Launch headless Chromium, search Google Scholar, and scrape results."""
    encoded_query = quote_plus(query)
    url = f"https://scholar.google.com/scholar?q={encoded_query}&hl=en&num={num_results + 5}"

    async with async_playwright() as pw:
        browser, context = await _launch_browser(pw)
        page = await context.new_page()

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await _dismiss_consent(page)
            await page.wait_for_selector("#gs_res_ccl", timeout=15000)

            results = await page.evaluate(
                """
                (numResults) => {
                    const results = [];
                    const entries = document.querySelectorAll('.gs_r.gs_or.gs_scl, .gs_ri');
                    for (const el of entries) {
                        if (results.length >= numResults) break;

                        const titleEl = el.querySelector('.gs_rt a, .gs_rt');
                        const linkEl = el.querySelector('.gs_rt a');
                        const authorsEl = el.querySelector('.gs_a');
                        const snippetEl = el.querySelector('.gs_rs');
                        const citedEl = el.querySelector('.gs_fl a');

                        let citedBy = '';
                        const flLinks = el.querySelectorAll('.gs_fl a');
                        for (const fl of flLinks) {
                            if (fl.textContent.includes('Cited by')) {
                                citedBy = fl.textContent.trim();
                                break;
                            }
                        }

                        if (titleEl) {
                            results.push({
                                title: titleEl.innerText.trim(),
                                url: linkEl ? linkEl.href : '',
                                authors: authorsEl ? authorsEl.innerText.trim() : '',
                                snippet: snippetEl ? snippetEl.innerText.trim() : '',
                                cited_by: citedBy
                            });
                        }
                    }
                    return results;
                }
                """,
                num_results,
            )

            if not results:
                return f"No scholar results found for: {query}"

            lines = [f"Google Scholar Results for: {query}\n"]
            for i, r in enumerate(results[:num_results], 1):
                lines.append(f"{i}. {r['title']}")
                if r.get("url"):
                    lines.append(f"   URL: {r['url']}")
                if r.get("authors"):
                    lines.append(f"   Authors: {r['authors']}")
                if r.get("cited_by"):
                    lines.append(f"   {r['cited_by']}")
                if r.get("snippet"):
                    lines.append(f"   {r['snippet']}")
                lines.append("")

            return "\n".join(lines)

        except Exception as e:
            return f"Scholar search failed: {e}"

        finally:
            await browser.close()


@mcp.tool()
async def google_scholar(query: str, num_results: int = 5) -> str:
    """Search Google Scholar for academic papers, citations, and research.

    Args:
        query: The academic search query string.
        num_results: Number of results to return (default 5, max 10).
    """
    num_results = max(1, min(num_results, 10))
    return await _do_google_scholar(query, num_results)


# ---------------------------------------------------------------------------
# google_images
# ---------------------------------------------------------------------------

async def _do_google_images(query: str, num_results: int = 5) -> str:
    """Launch headless Chromium, search Google Images, and scrape results."""
    encoded_query = quote_plus(query)
    url = f"https://www.google.com/search?q={encoded_query}&hl=en&tbm=isch"

    async with async_playwright() as pw:
        browser, context = await _launch_browser(pw)
        page = await context.new_page()

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await _dismiss_consent(page)
            await page.wait_for_timeout(2000)

            results = await page.evaluate(
                """
                (numResults) => {
                    const results = [];

                    // Google Images stores data in <a> tags with image thumbnails
                    const imgLinks = document.querySelectorAll('div[data-id] a[href^="/imgres"], a[jsname]');
                    for (const a of imgLinks) {
                        if (results.length >= numResults) break;

                        const img = a.querySelector('img[src^="http"], img[data-src^="http"]');
                        if (!img) continue;

                        const thumbnail = img.src || img.dataset.src || '';
                        if (!thumbnail || thumbnail.startsWith('data:')) continue;

                        // Try to extract the full image URL from the href
                        let fullUrl = '';
                        try {
                            const href = a.href || '';
                            const params = new URLSearchParams(href.split('?')[1] || '');
                            fullUrl = params.get('imgurl') || '';
                        } catch(e) {}

                        const title = img.alt || '';

                        results.push({
                            title: title,
                            thumbnail: thumbnail,
                            url: fullUrl || thumbnail,
                        });
                    }

                    // Fallback: grab all visible images with http src
                    if (results.length === 0) {
                        const allImgs = document.querySelectorAll('#search img[src^="http"], #islrg img[src^="http"]');
                        for (const img of allImgs) {
                            if (results.length >= numResults) break;
                            if (img.width < 50 || img.height < 50) continue;
                            results.push({
                                title: img.alt || '',
                                thumbnail: img.src,
                                url: img.src,
                            });
                        }
                    }

                    return results;
                }
                """,
                num_results,
            )

            if not results:
                return f"No image results found for: {query}"

            lines = [f"Google Image Results for: {query}\n"]
            for i, r in enumerate(results[:num_results], 1):
                lines.append(f"{i}. {r.get('title', 'Untitled')}")
                lines.append(f"   Image URL: {r['url']}")
                if r.get("thumbnail") and r["thumbnail"] != r["url"]:
                    lines.append(f"   Thumbnail: {r['thumbnail']}")
                lines.append("")

            return "\n".join(lines)

        except Exception as e:
            return f"Image search failed: {e}"

        finally:
            await browser.close()


@mcp.tool()
async def google_images(query: str, num_results: int = 5) -> str:
    """Search Google Images and return image URLs with descriptions.

    Args:
        query: The image search query string.
        num_results: Number of image results to return (default 5, max 10).
    """
    num_results = max(1, min(num_results, 10))
    return await _do_google_images(query, num_results)


# ---------------------------------------------------------------------------
# google_trends
# ---------------------------------------------------------------------------

async def _do_google_trends(query: str) -> str:
    """Launch headless Chromium, check Google Trends, and scrape interest data."""
    encoded_query = quote_plus(query)
    url = f"https://trends.google.com/trends/explore?q={encoded_query}&hl=en"

    async with async_playwright() as pw:
        browser, context = await _launch_browser(pw)
        page = await context.new_page()

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            # Trends takes longer to load its widgets
            await page.wait_for_timeout(5000)

            data = await page.evaluate(
                """
                () => {
                    const data = { interest: [], related_topics: [], related_queries: [] };

                    // Interest over time - try to get the widget content
                    const timeWidget = document.querySelector('fe-line-chart-directive, .fe-line-chart');
                    if (timeWidget) {
                        data.interest_note = 'Interest over time data available (see Google Trends for chart)';
                    }

                    // Related topics
                    const topicWidgets = document.querySelectorAll('fe-related-queries .comparison-item, .fe-atoms-generic-list .item');
                    for (const el of topicWidgets) {
                        const label = el.querySelector('.label-text, .item-text, a');
                        const value = el.querySelector('.progress-bar-wrapper, .bar');
                        if (label) {
                            data.related_topics.push({
                                topic: label.innerText.trim(),
                                value: value ? value.getAttribute('aria-label') || value.innerText.trim() : ''
                            });
                        }
                    }

                    // Related queries - look for the queries widget
                    const queryCards = document.querySelectorAll('.fe-related-queries-wrapper .comparison-item, [class*="related"] .item');
                    for (const el of queryCards) {
                        const label = el.querySelector('.label-text, .item-text, a');
                        const value = el.querySelector('.progress-bar-wrapper, .bar');
                        if (label) {
                            data.related_queries.push({
                                query: label.innerText.trim(),
                                value: value ? value.getAttribute('aria-label') || value.innerText.trim() : ''
                            });
                        }
                    }

                    // Fallback: get all visible text from the trends page
                    const mainContent = document.querySelector('.trends-wrapper, main, [role="main"]');
                    if (mainContent) {
                        data.page_text = mainContent.innerText.substring(0, 3000);
                    }

                    return data;
                }
                """
            )

            lines = [f"Google Trends for: {query}\n"]

            if data.get("interest_note"):
                lines.append(f"Note: {data['interest_note']}\n")

            if data.get("related_topics"):
                lines.append("Related Topics:")
                for t in data["related_topics"][:10]:
                    val = f" ({t['value']})" if t.get("value") else ""
                    lines.append(f"  - {t['topic']}{val}")
                lines.append("")

            if data.get("related_queries"):
                lines.append("Related Queries:")
                for q in data["related_queries"][:10]:
                    val = f" ({q['value']})" if q.get("value") else ""
                    lines.append(f"  - {q['query']}{val}")
                lines.append("")

            # If structured data extraction didn't work well, fall back to page text
            if not data.get("related_topics") and not data.get("related_queries"):
                page_text = data.get("page_text", "")
                if page_text:
                    # Clean up the text
                    page_text = re.sub(r'\n{3,}', '\n\n', page_text).strip()
                    lines.append(page_text)
                else:
                    lines.append("Could not extract structured trends data.")
                    lines.append(f"Visit: https://trends.google.com/trends/explore?q={encoded_query}")

            return "\n".join(lines)

        except Exception as e:
            return f"Trends lookup failed: {e}"

        finally:
            await browser.close()


@mcp.tool()
async def google_trends(query: str) -> str:
    """Check Google Trends for a topic to see interest over time, related topics, and related queries.

    Args:
        query: The topic or search term to check trends for.
    """
    return await _do_google_trends(query)


# ---------------------------------------------------------------------------
# visit_page
# ---------------------------------------------------------------------------

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
                    const remove = document.querySelectorAll(
                        'script, style, nav, footer, header, iframe, noscript, '
                        + 'svg, [role="navigation"], [role="banner"], '
                        + '[role="complementary"], .sidebar, .ad, .ads, .advertisement'
                    );
                    remove.forEach(el => el.remove());

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
