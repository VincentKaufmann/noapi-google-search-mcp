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
    - google_maps: Search Google Maps for places, restaurants, businesses
    - google_finance: Look up stock prices and market data
    - google_weather: Get current weather and forecasts
    - google_shopping: Search Google Shopping for products and prices
    - google_books: Search Google Books for books and publications
    - google_translate: Translate text between languages
    - google_flights: Search for flights between destinations
    - google_hotels: Search for hotels and accommodation
    - google_lens: Reverse image search to identify objects, products, brands
    - google_lens_detect: Detect objects in image and identify each via Lens
    - ocr_image: Extract text from images locally using RapidOCR (no internet needed)
    - transcribe_video: Download and transcribe YouTube videos with timestamps
    - extract_video_clip: Extract a segment from a video by timestamps
    - list_images: List image files in a directory for use with google_lens
    - visit_page: Fetch a URL and return its text content
"""

import os
import re
from datetime import datetime
from pathlib import Path
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
    """Dismiss Google consent banner if present (supports multiple languages)."""
    try:
        consent_btn = page.locator(
            "button:has-text('Accept all'), "
            "button:has-text('Accept All'), "
            "button:has-text('I agree'), "
            "button:has-text('Reject all'), "
            "button:has-text('Reject All'), "
            "button:has-text('Alle akzeptieren'), "
            "button:has-text('Alle ablehnen'), "
            "button:has-text('Tout accepter'), "
            "button:has-text('Tout refuser'), "
            "button:has-text('Aceptar todo'), "
            "button:has-text('Rechazar todo'), "
            "button:has-text('Accetta tutto'), "
            "button:has-text('Rifiuta tutto')"
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

    Sample prompts that trigger this tool:
        - "Search for the best Python web frameworks"
        - "Find Reddit discussions about home lab setups from the past week"
        - "Search Stack Overflow for async Python examples"
        - "Look up recent news about SpaceX in German"
        - "Get page 2 of results for machine learning tutorials"
        - "Search Hacker News for posts about Rust programming"
        - "Find Japanese results about Tokyo restaurants"

    Args:
        query: The search query string.
        num_results: Number of results to return (default 5, max 10).
        time_range: Filter by time. One of: "past_hour", "past_day", "past_week", "past_month", "past_year". Leave empty for no filter.
        site: Limit results to a specific domain (e.g. "reddit.com", "stackoverflow.com", "github.com", "arxiv.org", "news.ycombinator.com"). Leave empty for all sites.
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
                    lines.append(f"   Source: {' - '.join(source_info)}")
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

    Sample prompts that trigger this tool:
        - "What are the latest AI news?"
        - "Get me today's top headlines"
        - "Any recent news about the stock market?"
        - "What happened in the US election?"
        - "Latest news about climate change"

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

    Sample prompts that trigger this tool:
        - "Find me papers on transformer attention mechanisms"
        - "Look up academic research about quantum computing"
        - "Search for citations on CRISPR gene editing"
        - "Find recent studies about large language models"
        - "What does the research say about intermittent fasting?"

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

    Sample prompts that trigger this tool:
        - "Show me images of the Northern Lights"
        - "Find pictures of modern kitchen designs"
        - "Search for diagrams of neural network architecture"
        - "Find images of the Mars rover"

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

    Sample prompts that trigger this tool:
        - "What's trending in tech right now?"
        - "Is Python more popular than JavaScript?"
        - "Check the trend for electric vehicles"
        - "What are people searching for about AI?"

    Args:
        query: The topic or search term to check trends for.
    """
    return await _do_google_trends(query)


# ---------------------------------------------------------------------------
# google_maps
# ---------------------------------------------------------------------------

async def _do_google_maps(query: str, num_results: int = 5) -> str:
    """Search Google for places using the local pack results."""
    encoded_query = quote_plus(query)
    # Use Google Search which shows a local pack for place queries
    url = f"https://www.google.com/search?q={encoded_query}&hl=en"

    async with async_playwright() as pw:
        browser, context = await _launch_browser(pw)
        page = await context.new_page()

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await _dismiss_consent(page)
            await page.wait_for_timeout(3000)

            results = await page.evaluate(
                """
                (numResults) => {
                    const results = [];

                    // Try local pack results (div.VkpGBb or similar)
                    const localItems = document.querySelectorAll(
                        '[data-attrid*="local"] .VkpGBb, ' +
                        '.rllt__details, ' +
                        '[jscontroller] div[data-index], ' +
                        '.cXedhc a[data-cid]'
                    );

                    for (const el of localItems) {
                        if (results.length >= numResults) break;

                        const nameEl = el.querySelector(
                            '.dbg0pd, .OSrXXb, [role="heading"], .fontHeadlineSmall, span.OSrXXb'
                        );
                        const ratingEl = el.querySelector('.yi40Hd, .MW4etd, span[aria-label*="stars"], span[aria-label*="rated"]');
                        const reviewsEl = el.querySelector('.RDApEe, .UY7F9, span[aria-label*="reviews"]');
                        const infoEl = el.querySelector('.rllt__details div:nth-child(2), .W4Efsd');
                        const addressEl = el.querySelector('.rllt__details div:nth-child(3), .lMbq3e');

                        const name = nameEl ? nameEl.innerText.trim() : '';
                        if (!name) continue;

                        let rating = '';
                        if (ratingEl) {
                            rating = ratingEl.innerText.trim() ||
                                     (ratingEl.getAttribute('aria-label') || '').replace(/[^0-9.]/g, '');
                        }

                        let reviews = '';
                        if (reviewsEl) {
                            reviews = reviewsEl.innerText.trim().replace(/[()]/g, '') ||
                                      (reviewsEl.getAttribute('aria-label') || '').replace(/[^0-9,]/g, '');
                        }

                        results.push({
                            name: name,
                            rating: rating,
                            reviews: reviews,
                            category: infoEl ? infoEl.innerText.trim() : '',
                            address: addressEl ? addressEl.innerText.trim() : '',
                        });
                    }

                    // Fallback: try to find any place-like results from the page
                    if (results.length === 0) {
                        // Look for the map pack container
                        const mapPack = document.querySelector('.AEprdc, .C8TUKc, [data-attrid="kc:/local:local_pack"]');
                        if (mapPack) {
                            const items = mapPack.querySelectorAll('[data-cid], .VkpGBb, div[jsaction]');
                            for (const item of items) {
                                if (results.length >= numResults) break;
                                const text = item.innerText.trim();
                                if (text && text.length > 3 && text.length < 500) {
                                    // Parse the text block
                                    const lines = text.split('\\n').filter(l => l.trim());
                                    if (lines.length >= 1) {
                                        results.push({
                                            name: lines[0],
                                            rating: '',
                                            reviews: '',
                                            category: lines.length > 1 ? lines[1] : '',
                                            address: lines.length > 2 ? lines[2] : '',
                                        });
                                    }
                                }
                            }
                        }
                    }

                    // Last resort: get text from any local results section
                    if (results.length === 0) {
                        const allText = document.querySelector('.rlfl__tls, .AEprdc, [data-async-type="localPack"]');
                        if (allText) {
                            return [{
                                name: '__raw__',
                                raw_text: allText.innerText.substring(0, 2000),
                                rating: '', reviews: '', category: '', address: ''
                            }];
                        }
                    }

                    return results;
                }
                """,
                num_results,
            )

            # Deduplicate by name
            seen_names = set()
            deduped = []
            for r in results:
                if r.get("name") not in seen_names:
                    seen_names.add(r.get("name"))
                    deduped.append(r)
            results = deduped

            if not results:
                return f"No map results found for: {query}"

            # Handle raw text fallback
            if len(results) == 1 and results[0].get("name") == "__raw__":
                raw = results[0].get("raw_text", "")
                return f"Google Maps Results for: {query}\n\n{raw}"

            lines = [f"Google Maps Results for: {query}\n"]
            for i, r in enumerate(results[:num_results], 1):
                lines.append(f"{i}. {r['name']}")
                if r.get("rating"):
                    rating_str = f"   Rating: {r['rating']}"
                    if r.get("reviews"):
                        rating_str += f" ({r['reviews']} reviews)"
                    lines.append(rating_str)
                if r.get("category"):
                    lines.append(f"   Type: {r['category']}")
                if r.get("address"):
                    lines.append(f"   Address: {r['address']}")
                lines.append("")

            return "\n".join(lines)

        except Exception as e:
            return f"Maps search failed: {e}"

        finally:
            await browser.close()


@mcp.tool()
async def google_maps(query: str, num_results: int = 5) -> str:
    """Search Google Maps for places, restaurants, businesses, and locations with ratings and addresses.

    Sample prompts that trigger this tool:
        - "Find Italian restaurants near Times Square"
        - "Where are the best coffee shops in Berlin?"
        - "Search for hotels in Tokyo"
        - "Find EV charging stations in San Francisco"
        - "What are the top-rated gyms in London?"

    Args:
        query: The place search query (e.g. "pizza near Central Park", "hotels in Paris").
        num_results: Number of results to return (default 5, max 10).
    """
    num_results = max(1, min(num_results, 10))
    return await _do_google_maps(query, num_results)


# ---------------------------------------------------------------------------
# google_finance
# ---------------------------------------------------------------------------

async def _do_google_finance(query: str) -> str:
    """Search Google Finance for stock/market data."""
    encoded_query = quote_plus(query)
    url = f"https://www.google.com/finance/quote/{encoded_query}"

    async with async_playwright() as pw:
        browser, context = await _launch_browser(pw)
        page = await context.new_page()

        try:
            # First try direct quote URL
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await _dismiss_consent(page)
            await page.wait_for_timeout(2000)

            data = await page.evaluate(
                """
                () => {
                    const data = {};

                    // Price - use data attribute (most reliable)
                    const dataEl = document.querySelector('[data-last-price]');
                    if (dataEl) {
                        data.price = dataEl.getAttribute('data-last-price');
                    }

                    // Currency and exchange from data attributes
                    const currencyEl = document.querySelector('[data-currency-code]');
                    data.currency = currencyEl ? currencyEl.getAttribute('data-currency-code') : 'USD';

                    const exchangeEl = document.querySelector('[data-exchange]');
                    data.exchange = exchangeEl ? exchangeEl.getAttribute('data-exchange') : '';

                    // Displayed price with currency symbol
                    const displayEl = document.querySelector('.fxKbKc, .kf1m0');
                    data.display_price = displayEl ? displayEl.innerText.trim() : '';

                    // Change percentage and absolute
                    const rPF6Lc = document.querySelector('.rPF6Lc');
                    if (rPF6Lc) {
                        const text = rPF6Lc.innerText.trim();
                        const lines = text.split('\\n');
                        if (lines.length >= 2) {
                            data.change_pct = lines[1] ? lines[1].trim() : '';
                            data.change_abs = lines[2] ? lines[2].trim() : '';
                        }
                    }

                    // Company name
                    const nameEl = document.querySelector('.zzDege');
                    data.name = nameEl ? nameEl.innerText.trim() : '';

                    // Key stats - use first line only (labels include tooltip descriptions)
                    const stats = {};
                    const statRows = document.querySelectorAll('.gyFHrc .P6K39c, .eYanAe .P6K39c, table.slpEwd tr');
                    for (const row of statRows) {
                        const label = row.querySelector('.mfs7Fc, td:first-child');
                        const value = row.querySelector('.QXDnM, td:last-child');
                        if (label && value) {
                            const k = label.innerText.trim().split('\\n')[0];
                            const v = value.innerText.trim().split('\\n')[0];
                            if (k && v) stats[k] = v;
                        }
                    }
                    data.stats = stats;

                    // About/description
                    const aboutEl = document.querySelector('.bLLb2d, .Yfwt5');
                    data.about = aboutEl ? aboutEl.innerText.trim().substring(0, 500) : '';

                    return data;
                }
                """
            )

            if not data.get("price") and not data.get("name"):
                # Fallback: try Google search for finance info
                search_url = f"https://www.google.com/search?q={encoded_query}+stock+price&hl=en"
                await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(2000)

                data = await page.evaluate(
                    """
                    () => {
                        const data = {};
                        const priceEl = document.querySelector('[data-attrid*="Price"], .YMlKec, .kCrYT .IsqQVc');
                        data.price = priceEl ? priceEl.innerText.trim() : '';

                        const nameEl = document.querySelector('.oPhL2e .PZPZlf, [data-attrid*="title"]');
                        data.name = nameEl ? nameEl.innerText.trim() : '';

                        const changeEl = document.querySelector('[data-attrid*="change"], .JwB6zf');
                        data.change = changeEl ? changeEl.innerText.trim() : '';

                        // Get the knowledge panel text as fallback
                        const panel = document.querySelector('.kp-wholepage, .knowledge-panel');
                        data.panel_text = panel ? panel.innerText.substring(0, 1500) : '';

                        return data;
                    }
                    """
                )

            lines = [f"Google Finance: {query}\n"]

            if data.get("name"):
                lines.append(f"Company: {data['name']}")
            if data.get("display_price"):
                lines.append(f"Price: {data['display_price']}")
            elif data.get("price"):
                currency = data.get("currency", "USD")
                lines.append(f"Price: {data['price']} {currency}")
            if data.get("exchange"):
                lines.append(f"Exchange: {data['exchange']}")
            if data.get("change_pct") or data.get("change_abs"):
                change_parts = []
                if data.get("change_abs"):
                    change_parts.append(data["change_abs"])
                if data.get("change_pct"):
                    change_parts.append(f"({data['change_pct']})")
                lines.append(f"Change: {' '.join(change_parts)}")
            if data.get("stats"):
                lines.append("\nKey Stats:")
                for k, v in data["stats"].items():
                    lines.append(f"  {k}: {v}")

            if data.get("about"):
                lines.append(f"\nAbout: {data['about']}")

            if not data.get("price"):
                lines.append("Could not find financial data. Try a stock ticker like 'AAPL:NASDAQ' or 'TSLA:NASDAQ'.")

            return "\n".join(lines)

        except Exception as e:
            return f"Finance lookup failed: {e}"

        finally:
            await browser.close()


@mcp.tool()
async def google_finance(query: str) -> str:
    """Look up stock prices, market data, and company information on Google Finance.

    Sample prompts that trigger this tool:
        - "What's Apple's stock price?"
        - "How is Tesla stock doing?"
        - "Look up NVIDIA market cap"
        - "Get me the stock price for Microsoft"
        - "How is the S&P 500 doing today?"

    Args:
        query: Stock ticker with exchange (e.g. "AAPL:NASDAQ", "TSLA:NASDAQ", "MSFT:NASDAQ", ".INX:INDEXSP") or company name.
    """
    return await _do_google_finance(query)


# ---------------------------------------------------------------------------
# google_weather
# ---------------------------------------------------------------------------

async def _do_google_weather(location: str) -> str:
    """Get weather data from Google's weather card."""
    encoded_location = quote_plus(f"weather {location}")
    url = f"https://www.google.com/search?q={encoded_location}&hl=en"

    async with async_playwright() as pw:
        browser, context = await _launch_browser(pw)
        page = await context.new_page()

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await _dismiss_consent(page)
            await page.wait_for_timeout(2000)

            data = await page.evaluate(
                """
                () => {
                    const data = {};

                    // Location
                    const locEl = document.querySelector('#wob_loc');
                    data.location = locEl ? locEl.innerText.trim() : '';

                    // Current temperature
                    const tempEl = document.querySelector('#wob_tm');
                    data.temp_c = tempEl ? tempEl.innerText.trim() : '';

                    const tempFEl = document.querySelector('#wob_ttm');
                    data.temp_f = tempFEl ? tempFEl.innerText.trim() : '';

                    // Condition (e.g. "Sunny", "Partly cloudy")
                    const condEl = document.querySelector('#wob_dc');
                    data.condition = condEl ? condEl.innerText.trim() : '';

                    // Precipitation
                    const precipEl = document.querySelector('#wob_pp');
                    data.precipitation = precipEl ? precipEl.innerText.trim() : '';

                    // Humidity
                    const humidEl = document.querySelector('#wob_hm');
                    data.humidity = humidEl ? humidEl.innerText.trim() : '';

                    // Wind
                    const windEl = document.querySelector('#wob_ws');
                    data.wind = windEl ? windEl.innerText.trim() : '';

                    // Day/time
                    const timeEl = document.querySelector('#wob_dts');
                    data.time = timeEl ? timeEl.innerText.trim() : '';

                    // Forecast days
                    data.forecast = [];
                    const forecastDays = document.querySelectorAll('.wob_df');
                    for (const day of forecastDays) {
                        const dayName = day.querySelector('.Z1VzSb, .QrNVmd');
                        const highEl = day.querySelector('.wob_t:first-of-type .wob_t');
                        const lowEl = day.querySelector('.wob_t:last-of-type .wob_t');
                        const iconEl = day.querySelector('img');

                        // Get high and low from the spans
                        const temps = day.querySelectorAll('.wob_t span:first-child');
                        let high = '', low = '';
                        if (temps.length >= 2) {
                            high = temps[0].innerText.trim();
                            low = temps[1].innerText.trim();
                        }

                        if (dayName) {
                            data.forecast.push({
                                day: dayName.innerText.trim(),
                                high: high,
                                low: low,
                                condition: iconEl ? iconEl.alt || '' : ''
                            });
                        }
                    }

                    return data;
                }
                """
            )

            if not data.get("temp_c") and not data.get("location"):
                return f"Could not find weather data for: {location}"

            # Use the provided location name if Google's #wob_loc is generic
            display_location = data.get("location", location)
            if not display_location or display_location.lower() in ("weather", ""):
                display_location = location

            lines = [f"Weather for: {display_location}\n"]

            if data.get("time"):
                lines.append(f"As of: {data['time']}")

            if data.get("temp_c"):
                temp_str = f"Temperature: {data['temp_c']}°C"
                if data.get("temp_f"):
                    temp_str += f" ({data['temp_f']}°F)"
                lines.append(temp_str)

            if data.get("condition"):
                lines.append(f"Condition: {data['condition']}")
            if data.get("precipitation"):
                lines.append(f"Precipitation: {data['precipitation']}")
            if data.get("humidity"):
                lines.append(f"Humidity: {data['humidity']}")
            if data.get("wind"):
                lines.append(f"Wind: {data['wind']}")

            if data.get("forecast"):
                lines.append("\nForecast:")
                for f in data["forecast"][:7]:
                    day_str = f"  {f['day']}"
                    if f.get("high") and f.get("low"):
                        day_str += f": {f['high']}° / {f['low']}°"
                    if f.get("condition"):
                        day_str += f" - {f['condition']}"
                    lines.append(day_str)

            return "\n".join(lines)

        except Exception as e:
            return f"Weather lookup failed: {e}"

        finally:
            await browser.close()


@mcp.tool()
async def google_weather(location: str) -> str:
    """Get current weather conditions and forecast for any location.

    Sample prompts that trigger this tool:
        - "What's the weather in Dubai?"
        - "Is it going to rain in London today?"
        - "What's the temperature in New York?"
        - "Weather forecast for Tokyo this week"
        - "How hot is it in Dubai right now?"

    Args:
        location: The city or location to get weather for (e.g. "Dubai", "New York", "London, UK", "Tokyo").
    """
    return await _do_google_weather(location)


# ---------------------------------------------------------------------------
# google_shopping
# ---------------------------------------------------------------------------

async def _do_google_shopping(query: str, num_results: int = 5) -> str:
    """Search Google Shopping for products and prices."""
    encoded_query = quote_plus(query)
    url = f"https://www.google.com/search?q={encoded_query}&hl=en&tbm=shop&num={num_results + 5}"

    async with async_playwright() as pw:
        browser, context = await _launch_browser(pw)
        page = await context.new_page()

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await _dismiss_consent(page)
            await page.wait_for_timeout(2000)

            results = await page.evaluate(
                r"""
                (numResults) => {
                    const results = [];

                    // Google Shopping uses various container classes
                    const items = document.querySelectorAll(
                        '.sh-dgr__content, .sh-dlr__list-result, ' +
                        '.KZmu8e, .i0X6df, .xcR77, ' +
                        '[data-docid], .sh-pr__product-result'
                    );

                    for (const el of items) {
                        if (results.length >= numResults) break;

                        const titleEl = el.querySelector('h3, h4, .tAxDx, .Xjkr3b, .EI11Pd');
                        const priceEl = el.querySelector('.a8Pemb, .HRLxBb, .kHxwFf, .T14wmb, b');
                        const storeEl = el.querySelector('.aULzUe, .IuHnof, .E5ocAb, .dD8iuc');
                        const linkEl = el.querySelector('a[href]');
                        const ratingEl = el.querySelector('.Rsc7Yb, .QIrs8, .yi40Hd');

                        const title = titleEl ? titleEl.innerText.trim() : '';
                        if (!title) continue;

                        results.push({
                            title: title,
                            price: priceEl ? priceEl.innerText.trim() : '',
                            store: storeEl ? storeEl.innerText.trim() : '',
                            rating: ratingEl ? ratingEl.innerText.trim() : '',
                            url: linkEl ? linkEl.href : '',
                        });
                    }

                    // Fallback: parse the visible text on shopping results
                    if (results.length === 0) {
                        const body = document.querySelector('#search, #rso, main');
                        if (body) {
                            const text = body.innerText;
                            // Look for price patterns to split products
                            const pricePattern = /(?:[$£€]|CHF|USD|EUR)\s*[\d,.]+/g;
                            const matches = [...text.matchAll(pricePattern)];
                            if (matches.length > 0) {
                                return [{
                                    title: '__raw__',
                                    raw_text: text.substring(0, 3000),
                                    price: '', store: '', rating: '', url: ''
                                }];
                            }
                        }
                    }

                    return results;
                }
                """,
                num_results,
            )

            if not results:
                return f"No shopping results found for: {query}"

            # Handle raw text fallback
            if len(results) == 1 and results[0].get("title") == "__raw__":
                raw = results[0].get("raw_text", "")
                raw = re.sub(r'\n{3,}', '\n\n', raw).strip()
                return f"Google Shopping Results for: {query}\n\n{raw}"

            lines = [f"Google Shopping Results for: {query}\n"]
            for i, r in enumerate(results[:num_results], 1):
                lines.append(f"{i}. {r['title']}")
                if r.get("price"):
                    lines.append(f"   Price: {r['price']}")
                if r.get("store"):
                    lines.append(f"   Store: {r['store']}")
                if r.get("rating"):
                    lines.append(f"   Rating: {r['rating']}")
                if r.get("url"):
                    lines.append(f"   URL: {r['url']}")
                lines.append("")

            return "\n".join(lines)

        except Exception as e:
            return f"Shopping search failed: {e}"

        finally:
            await browser.close()


@mcp.tool()
async def google_shopping(query: str, num_results: int = 5) -> str:
    """Search Google Shopping for products with prices, stores, and ratings.

    Sample prompts that trigger this tool:
        - "Find the cheapest MacBook Air"
        - "Compare prices for Sony WH-1000XM5 headphones"
        - "How much does a Nintendo Switch cost?"
        - "Search for running shoes under $100"
        - "Find deals on mechanical keyboards"

    Args:
        query: The product search query string.
        num_results: Number of results to return (default 5, max 10).
    """
    num_results = max(1, min(num_results, 10))
    return await _do_google_shopping(query, num_results)


# ---------------------------------------------------------------------------
# google_books
# ---------------------------------------------------------------------------

async def _do_google_books(query: str, num_results: int = 5) -> str:
    """Search Google Books for books and publications."""
    encoded_query = quote_plus(query)
    url = f"https://www.google.com/search?q={encoded_query}&hl=en&tbm=bks&num={num_results + 5}"

    async with async_playwright() as pw:
        browser, context = await _launch_browser(pw)
        page = await context.new_page()

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await _dismiss_consent(page)
            await page.wait_for_timeout(2000)

            results = await page.evaluate(
                r"""
                (numResults) => {
                    const results = [];

                    // Find all h3 elements that are book results
                    const allH3 = document.querySelectorAll('h3');
                    for (const h3 of allH3) {
                        if (results.length >= numResults) break;

                        const title = h3.innerText.trim();
                        if (!title || title.length < 3) continue;
                        // Skip navigation/header h3s
                        if (title === 'Search Results' || title === 'Filters and topics') continue;

                        // Walk up to find the result container
                        let container = h3.closest('.g') || h3.parentElement?.parentElement?.parentElement;
                        if (!container) continue;

                        // Get the link
                        const linkEl = container.querySelector('a[href*="books.google"], a[href^="http"]');
                        const url = linkEl ? linkEl.href : '';

                        // Get snippet
                        const snippetEl = container.querySelector('.VwiC3b, .cmlJmd, [data-sncf]');
                        const snippet = snippetEl ? snippetEl.innerText.trim() : '';

                        // Get author - look for text between the title and snippet
                        let author = '';
                        const metaEls = container.querySelectorAll('span, cite');
                        for (const el of metaEls) {
                            const t = el.innerText.trim();
                            if (t && t !== title && !t.includes('http') &&
                                (t.includes(',') || t.includes('·') || /\d{4}/.test(t)) &&
                                t.length < 200) {
                                author = t;
                                break;
                            }
                        }

                        results.push({ title, url, author, snippet });
                    }
                    return results;
                }
                """,
                num_results,
            )

            if not results:
                return f"No book results found for: {query}"

            lines = [f"Google Books Results for: {query}\n"]
            for i, r in enumerate(results[:num_results], 1):
                lines.append(f"{i}. {r['title']}")
                if r.get("author"):
                    lines.append(f"   Author: {r['author']}")
                if r.get("url"):
                    lines.append(f"   URL: {r['url']}")
                if r.get("snippet"):
                    lines.append(f"   {r['snippet']}")
                lines.append("")

            return "\n".join(lines)

        except Exception as e:
            return f"Book search failed: {e}"

        finally:
            await browser.close()


@mcp.tool()
async def google_books(query: str, num_results: int = 5) -> str:
    """Search Google Books for books, textbooks, and publications.

    Sample prompts that trigger this tool:
        - "Find books about machine learning"
        - "Search for books by Stephen King"
        - "What are the best books on Python programming?"
        - "Find textbooks on linear algebra"
        - "Look up books about the history of AI"

    Args:
        query: The book search query string.
        num_results: Number of results to return (default 5, max 10).
    """
    num_results = max(1, min(num_results, 10))
    return await _do_google_books(query, num_results)


# ---------------------------------------------------------------------------
# google_translate
# ---------------------------------------------------------------------------

LANGUAGE_CODES = {
    "english": "en", "spanish": "es", "french": "fr", "german": "de",
    "italian": "it", "portuguese": "pt", "japanese": "ja", "korean": "ko",
    "chinese": "zh-CN", "arabic": "ar", "russian": "ru", "hindi": "hi",
    "dutch": "nl", "swedish": "sv", "turkish": "tr", "polish": "pl",
    "thai": "th", "vietnamese": "vi", "indonesian": "id", "greek": "el",
    "hebrew": "he", "czech": "cs", "danish": "da", "finnish": "fi",
    "norwegian": "no", "romanian": "ro", "hungarian": "hu", "ukrainian": "uk",
}


async def _do_google_translate(text: str, to_language: str, from_language: str = "") -> str:
    """Translate text using Google Translate directly."""
    # Resolve language names to codes
    tl = LANGUAGE_CODES.get(to_language.lower(), to_language.lower())
    sl = LANGUAGE_CODES.get(from_language.lower(), from_language.lower()) if from_language else "auto"

    encoded_text = quote_plus(text)
    url = f"https://translate.google.com/?sl={sl}&tl={tl}&text={encoded_text}&op=translate"

    async with async_playwright() as pw:
        browser, context = await _launch_browser(pw)
        page = await context.new_page()

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await _dismiss_consent(page)
            # Wait for translation to load
            await page.wait_for_timeout(3000)

            data = await page.evaluate(
                r"""
                () => {
                    const data = {};

                    // Translation output is in spans with lang attribute inside the result container
                    const resultContainer = document.querySelector('[data-result-index] .HwtZe, .lRu31, [jsname="W297wb"]');
                    if (resultContainer) {
                        data.translation = resultContainer.innerText.trim();
                    }

                    // Fallback: look for the output textarea or contenteditable
                    if (!data.translation) {
                        const outputArea = document.querySelector(
                            '.J0lOec, [aria-label*="Translation"], ' +
                            'span[jsname="W297wb"], .ryNqvb, ' +
                            '[data-language-to-translate-into] .Y2IQFc'
                        );
                        if (outputArea) {
                            data.translation = outputArea.innerText.trim();
                        }
                    }

                    // Last resort: get all text containers and find the non-source one
                    if (!data.translation) {
                        const containers = document.querySelectorAll('.Y2IQFc');
                        if (containers.length >= 2) {
                            data.translation = containers[containers.length - 1].innerText.trim();
                        }
                    }

                    return data;
                }
                """
            )

            if not data.get("translation") or data["translation"] == text:
                return f"Could not translate: {text}"

            lines = ["Google Translate\n"]
            lines.append(f"Original: {text}")
            lines.append(f"Translation ({to_language}): {data['translation']}")

            return "\n".join(lines)

        except Exception as e:
            return f"Translation failed: {e}"

        finally:
            await browser.close()


@mcp.tool()
async def google_translate(text: str, to_language: str, from_language: str = "") -> str:
    """Translate text from one language to another using Google Translate.

    Sample prompts that trigger this tool:
        - "Translate 'hello world' to Japanese"
        - "How do you say 'thank you' in French?"
        - "Translate this to Spanish: The weather is nice today"
        - "What does 'Guten Morgen' mean in English?"
        - "Translate 'I love programming' to Korean"

    Args:
        text: The text to translate.
        to_language: Target language (e.g. "Spanish", "Japanese", "French", "German", "Korean", "Chinese", "Arabic").
        from_language: Source language (optional, auto-detected if empty).
    """
    return await _do_google_translate(text, to_language, from_language or "")


# ---------------------------------------------------------------------------
# google_flights
# ---------------------------------------------------------------------------

async def _do_google_flights(
    origin: str, destination: str, date: str = "", return_date: str = ""
) -> str:
    """Search Google Flights for flight information."""
    query_parts = [f"flights from {origin} to {destination}"]
    if date:
        query_parts.append(f"on {date}")
    if return_date:
        query_parts.append(f"return {return_date}")

    search_query = " ".join(query_parts)
    encoded_query = quote_plus(search_query)
    url = f"https://www.google.com/search?q={encoded_query}&hl=en"

    async with async_playwright() as pw:
        browser, context = await _launch_browser(pw)
        page = await context.new_page()

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await _dismiss_consent(page)
            await page.wait_for_timeout(3000)

            data = await page.evaluate(
                """
                () => {
                    const data = { flights: [] };

                    // Google's flight card in search results
                    const flightCards = document.querySelectorAll(
                        '.OgdJid, ' +
                        '.zBTtmb, ' +
                        '[data-attrid*="flight"] .wUrVib, ' +
                        '.fltt-card, ' +
                        '.gws-flights__result'
                    );

                    for (const card of flightCards) {
                        const text = card.innerText.trim();
                        if (text && text.length > 10) {
                            data.flights.push({ raw: text });
                        }
                    }

                    // Try the flights widget
                    if (data.flights.length === 0) {
                        const widget = document.querySelector(
                            '[data-attrid*="flight"], ' +
                            '.gws-flights, ' +
                            '.VkpGBb[data-attrid*="flight"]'
                        );
                        if (widget) {
                            data.widget_text = widget.innerText.substring(0, 3000);
                        }
                    }

                    // Also grab the "View all flights" link if present
                    const viewAll = document.querySelector('a[href*="google.com/travel/flights"]');
                    data.flights_url = viewAll ? viewAll.href : '';

                    // Get the knowledge panel or featured snippet about flights
                    const panel = document.querySelector('.kp-wholepage, .liYKde, .ULSxyf');
                    if (panel) {
                        const flightInfo = panel.innerText.substring(0, 2000);
                        if (flightInfo.toLowerCase().includes('flight') || flightInfo.includes('$') || flightInfo.includes('hr')) {
                            data.panel_text = flightInfo;
                        }
                    }

                    return data;
                }
                """
            )

            lines = [f"Google Flights: {origin} to {destination}\n"]
            if date:
                lines.append(f"Date: {date}")
            if return_date:
                lines.append(f"Return: {return_date}")
            lines.append("")

            has_data = False

            if data.get("flights"):
                for f in data["flights"][:5]:
                    raw = f.get("raw", "")
                    # Clean up and format
                    raw = re.sub(r'\n{2,}', '\n', raw).strip()
                    lines.append(raw)
                    lines.append("")
                has_data = True

            if data.get("widget_text"):
                text = re.sub(r'\n{3,}', '\n\n', data["widget_text"]).strip()
                lines.append(text)
                has_data = True

            if data.get("panel_text") and not has_data:
                text = re.sub(r'\n{3,}', '\n\n', data["panel_text"]).strip()
                lines.append(text)
                has_data = True

            if data.get("flights_url"):
                lines.append(f"\nView all flights: {data['flights_url']}")

            if not has_data and not data.get("flights_url"):
                lines.append(f"No flight data found. Try searching directly:")
                lines.append(f"https://www.google.com/travel/flights")

            return "\n".join(lines)

        except Exception as e:
            return f"Flight search failed: {e}"

        finally:
            await browser.close()


@mcp.tool()
async def google_flights(
    origin: str, destination: str, date: str = "", return_date: str = ""
) -> str:
    """Search Google Flights for flight options, prices, and travel times.

    Sample prompts that trigger this tool:
        - "Find flights from New York to London"
        - "Search for cheap flights from LA to Tokyo"
        - "Flights from San Francisco to Paris on March 15"
        - "Find round trip flights from Chicago to Miami"
        - "How much are flights from Dubai to Bangkok?"

    Args:
        origin: Departure city or airport (e.g. "New York", "LAX", "London").
        destination: Arrival city or airport (e.g. "Tokyo", "SFO", "Paris").
        date: Departure date (optional, e.g. "March 15", "2025-03-15").
        return_date: Return date for round trips (optional).
    """
    return await _do_google_flights(origin, destination, date or "", return_date or "")


# ---------------------------------------------------------------------------
# google_hotels
# ---------------------------------------------------------------------------

async def _do_google_hotels(query: str, num_results: int = 5) -> str:
    """Search Google for hotel information."""
    encoded_query = quote_plus(f"hotels {query}")
    url = f"https://www.google.com/search?q={encoded_query}&hl=en"

    async with async_playwright() as pw:
        browser, context = await _launch_browser(pw)
        page = await context.new_page()

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await _dismiss_consent(page)
            await page.wait_for_timeout(3000)

            data = await page.evaluate(
                """
                (numResults) => {
                    const data = { hotels: [] };

                    // Hotel cards in search results
                    const hotelCards = document.querySelectorAll(
                        '.BTPx6e, ' +
                        '[data-attrid*="hotel"] .kp-blk, ' +
                        '.X7NTVe, ' +
                        '.ntKMYc'
                    );

                    for (const card of hotelCards) {
                        if (data.hotels.length >= numResults) break;

                        const nameEl = card.querySelector('.BTPx6e .rOVRL, h3, .GgpMEf, [data-hotel-id] .QrShPb');
                        const priceEl = card.querySelector('.kixHKb, .qeiSWe, .priceText, .hVE8ee');
                        const ratingEl = card.querySelector('.KFi5wf, .MW4etd, .yi40Hd');
                        const reviewsEl = card.querySelector('.jdzyld, .RDApEe');
                        const linkEl = card.querySelector('a[href]');

                        const name = nameEl ? nameEl.innerText.trim() : '';
                        if (!name) continue;

                        data.hotels.push({
                            name: name,
                            price: priceEl ? priceEl.innerText.trim() : '',
                            rating: ratingEl ? ratingEl.innerText.trim() : '',
                            reviews: reviewsEl ? reviewsEl.innerText.trim().replace(/[()]/g, '') : '',
                            url: linkEl ? linkEl.href : '',
                        });
                    }

                    // Fallback: get the hotel widget text
                    if (data.hotels.length === 0) {
                        const widget = document.querySelector(
                            '[data-attrid*="hotel"], .kp-wholepage, .liYKde'
                        );
                        if (widget) {
                            const text = widget.innerText.substring(0, 3000);
                            if (text.toLowerCase().includes('hotel') || text.includes('$') || text.includes('/night')) {
                                data.widget_text = text;
                            }
                        }
                    }

                    // "View all hotels" link
                    const viewAll = document.querySelector('a[href*="google.com/travel/hotels"]');
                    data.hotels_url = viewAll ? viewAll.href : '';

                    return data;
                }
                """,
                num_results,
            )

            lines = [f"Google Hotels: {query}\n"]
            has_data = False

            if data.get("hotels"):
                for i, h in enumerate(data["hotels"][:num_results], 1):
                    lines.append(f"{i}. {h['name']}")
                    if h.get("price"):
                        lines.append(f"   Price: {h['price']}")
                    if h.get("rating"):
                        rating_str = f"   Rating: {h['rating']}"
                        if h.get("reviews"):
                            rating_str += f" ({h['reviews']} reviews)"
                        lines.append(rating_str)
                    if h.get("url"):
                        lines.append(f"   URL: {h['url']}")
                    lines.append("")
                has_data = True

            if data.get("widget_text") and not has_data:
                text = re.sub(r'\n{3,}', '\n\n', data["widget_text"]).strip()
                lines.append(text)
                has_data = True

            if data.get("hotels_url"):
                lines.append(f"\nView all hotels: {data['hotels_url']}")

            if not has_data and not data.get("hotels_url"):
                lines.append("No hotel data found. Try searching directly:")
                lines.append("https://www.google.com/travel/hotels")

            return "\n".join(lines)

        except Exception as e:
            return f"Hotel search failed: {e}"

        finally:
            await browser.close()


@mcp.tool()
async def google_hotels(query: str, num_results: int = 5) -> str:
    """Search for hotels and accommodation with prices and ratings.

    Sample prompts that trigger this tool:
        - "Find hotels in Paris for next weekend"
        - "Search for cheap hotels in Tokyo"
        - "Best hotels near Times Square New York"
        - "Find 5-star hotels in Dubai"
        - "Hotels in London under $200 per night"

    Args:
        query: Hotel search query with location (e.g. "Paris", "Tokyo near Shibuya", "New York March 15-20").
        num_results: Number of results to return (default 5, max 10).
    """
    num_results = max(1, min(num_results, 10))
    return await _do_google_hotels(query, num_results)


# ---------------------------------------------------------------------------
# google_lens (reverse image search)
# ---------------------------------------------------------------------------

def _is_local_file(path: str) -> bool:
    """Check if the input looks like a local file path rather than a URL."""
    if path.startswith(("http://", "https://", "data:")):
        return False
    # Absolute or relative path, or ~ home path
    return path.startswith(("/", "~", "./", "../")) or os.path.exists(path)


async def _do_google_lens(image_source: str) -> str:
    """Reverse image search using Google Lens. Supports URLs and local file paths."""
    is_local = _is_local_file(image_source)

    if is_local:
        file_path = str(Path(image_source).expanduser().resolve())
        if not os.path.isfile(file_path):
            return f"File not found: {image_source}\nPlease provide a valid file path or a public image URL."

    async with async_playwright() as pw:
        browser, context = await _launch_browser(pw)
        page = await context.new_page()

        try:
            if is_local:
                # Local file: go to Google Images and upload via file chooser
                await page.goto("https://images.google.com/?hl=en", wait_until="domcontentloaded", timeout=30000)
                await _dismiss_consent(page)
                await page.wait_for_timeout(1000)

                # Click the camera/lens icon to open image search
                lens_btn = page.locator("[aria-label='Search by image'], .Gdd5U, .nDcEnd, .tdAaF")
                if await lens_btn.count() > 0:
                    await lens_btn.first.click()
                    await page.wait_for_timeout(1500)

                # Upload the file - Playwright file chooser approach
                file_input = page.locator("input[type='file']")
                if await file_input.count() > 0:
                    await file_input.first.set_input_files(file_path)
                else:
                    # Fallback: try drag area upload button
                    upload_btn = page.locator("a:has-text('upload a file'), span:has-text('upload a file'), div:has-text('upload a file')")
                    if await upload_btn.count() > 0:
                        async with page.expect_file_chooser() as fc_info:
                            await upload_btn.first.click()
                        file_chooser = await fc_info.value
                        await file_chooser.set_files(file_path)
                    else:
                        return "Could not find the upload button on Google Images. Try providing a public image URL instead."

                # Wait for Lens results to load
                await page.wait_for_load_state("domcontentloaded", timeout=30000)
                await page.wait_for_timeout(5000)
                await _dismiss_consent(page)

            else:
                # URL-based: use uploadbyurl
                encoded_url = quote_plus(image_source)
                url = f"https://lens.google.com/uploadbyurl?url={encoded_url}&hl=en"
                await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                await _dismiss_consent(page)
                await page.wait_for_timeout(2000)

            # Click "Change to English" if present
            try:
                eng_link = page.locator("a:has-text('Change to English'), a:has-text('English')")
                if await eng_link.count() > 0:
                    await eng_link.first.click()
                    await page.wait_for_load_state("domcontentloaded", timeout=10000)
                    await _dismiss_consent(page)
            except Exception:
                pass

            # Lens takes time to process the image
            await page.wait_for_timeout(4000)

            # Check for error
            page_text = await page.evaluate("() => document.body.innerText.substring(0, 500)")
            if "No image at the URL" in page_text or "Something went wrong" in page_text:
                if is_local:
                    return f"Google Lens could not process the image: {image_source}\nThe file may be corrupted or in an unsupported format."
                return f"Google Lens could not access the image at: {image_source}\nThe image URL must be publicly accessible. Try a direct image link (ending in .jpg, .png, etc.)."

            data = await page.evaluate(
                r"""
                () => {
                    const data = {
                        ai_overview: '',
                        visual_matches: [],
                        product_results: [],
                        exact_matches: []
                    };

                    // AI Overview - Google's description of the image
                    const bodyText = document.body.innerText;
                    const aiIdx = bodyText.indexOf('AI Overview');
                    if (aiIdx !== -1) {
                        // Get text after "AI Overview" until next section
                        const afterAi = bodyText.substring(aiIdx + 11, aiIdx + 1500);
                        const endMarkers = ['Visual matches', 'Exact matches', 'Products', 'Related links', 'Footer'];
                        let endIdx = afterAi.length;
                        for (const marker of endMarkers) {
                            const idx = afterAi.indexOf(marker);
                            if (idx !== -1 && idx < endIdx) endIdx = idx;
                        }
                        data.ai_overview = afterAi.substring(0, endIdx).trim();
                        // Clean up
                        if (data.ai_overview.startsWith('\n')) {
                            data.ai_overview = data.ai_overview.substring(1).trim();
                        }
                        // Remove "Dive deeper in AI Mode" suffix
                        const diveIdx = data.ai_overview.indexOf('Dive deeper');
                        if (diveIdx !== -1) {
                            data.ai_overview = data.ai_overview.substring(0, diveIdx).trim();
                        }
                    }

                    // Visual matches section - all the heading DIVs are visual match titles
                    const allHeadings = document.querySelectorAll('div[role="heading"]');
                    const skipTexts = new Set([
                        'Choose what you\'re giving feedback on',
                        'Customised date range',
                        'Search Results',
                        'Filters and topics'
                    ]);
                    for (const h of allHeadings) {
                        if (data.visual_matches.length >= 10) break;
                        const text = h.innerText.trim();
                        if (!text || text.length < 3 || skipTexts.has(text)) continue;

                        // Find parent link
                        const parentLink = h.closest('a[href]');
                        let url = '';
                        let source = '';
                        if (parentLink) {
                            url = parentLink.href || '';
                            // Source is usually the first line of the link text
                            const linkLines = parentLink.innerText.trim().split('\n');
                            if (linkLines.length > 1 && linkLines[0] !== text) {
                                source = linkLines[0];
                            }
                        }

                        // Get rating if present nearby
                        const parent = h.parentElement;
                        let rating = '';
                        if (parent) {
                            const rText = parent.innerText;
                            const rMatch = rText.match(/(\d\.\d)\([\d,]+\)/);
                            if (rMatch) rating = rMatch[0];
                        }

                        if (url && !url.includes('google.com/search')) {
                            data.visual_matches.push({
                                name: text,
                                url: url,
                                source: source,
                                rating: rating
                            });
                        }
                    }

                    // Product results with prices (h3 elements with links)
                    const h3s = document.querySelectorAll('h3');
                    for (const h3 of h3s) {
                        if (data.product_results.length >= 8) break;
                        const text = h3.innerText.trim();
                        if (!text || text.length < 5) continue;

                        const container = h3.closest('.g') || h3.parentElement?.parentElement?.parentElement;
                        if (!container) continue;

                        const linkEl = container.querySelector('a[href^="http"]');
                        const containerText = container.innerText;

                        // Look for price patterns
                        const priceMatch = containerText.match(/(?:US?\$|€|£|CHF|MX\$)\s*[\d,.]+/);
                        const snippetEl = container.querySelector('.VwiC3b, [data-sncf]');

                        if (linkEl) {
                            data.product_results.push({
                                name: text,
                                url: linkEl.href,
                                price: priceMatch ? priceMatch[0] : '',
                                snippet: snippetEl ? snippetEl.innerText.trim().substring(0, 300) : ''
                            });
                        }
                    }

                    // Fallback: get full page text if nothing else worked
                    if (!data.ai_overview && data.visual_matches.length === 0 && data.product_results.length === 0) {
                        const main = document.querySelector('[role="main"], body');
                        if (main) {
                            data.raw_text = main.innerText.substring(0, 5000);
                        }
                    }

                    return data;
                }
                """
            )

            lines = [f"Google Lens Results for image: {image_source}\n"]
            has_data = False

            if data.get("ai_overview"):
                lines.append(f"Image Description: {data['ai_overview']}")
                has_data = True

            if data.get("visual_matches"):
                lines.append("\nVisual Matches:")
                for i, m in enumerate(data["visual_matches"], 1):
                    entry = f"  {i}. {m['name']}"
                    if m.get("rating"):
                        entry += f" ({m['rating']})"
                    lines.append(entry)
                    if m.get("source"):
                        lines.append(f"     Source: {m['source']}")
                    if m.get("url"):
                        lines.append(f"     URL: {m['url']}")
                has_data = True

            if data.get("product_results"):
                lines.append("\nProduct Results:")
                for i, p in enumerate(data["product_results"], 1):
                    lines.append(f"  {i}. {p['name']}")
                    if p.get("price"):
                        lines.append(f"     Price: {p['price']}")
                    if p.get("snippet"):
                        lines.append(f"     {p['snippet']}")
                    if p.get("url"):
                        lines.append(f"     URL: {p['url']}")
                has_data = True

            if not has_data and data.get("raw_text"):
                raw = re.sub(r'\n{3,}', '\n\n', data["raw_text"]).strip()
                lines.append(raw)
                has_data = True

            if not has_data:
                lines.append("Could not identify the image. Try with a clearer image or a direct product photo.")

            return "\n".join(lines)

        except Exception as e:
            return f"Google Lens search failed: {e}"

        finally:
            await browser.close()


@mcp.tool()
async def google_lens(image_source: str) -> str:
    """Reverse image search using Google Lens. Identify objects, products, brands, landmarks, text in images, and find visually similar results.

    This gives vision capabilities to text-only models. Supports both public image URLs and local file paths.

    For local files, pass the absolute file path (e.g. /home/user/photos/image.jpg).
    For web images, pass the full URL (e.g. https://example.com/photo.jpg).

    Sample prompts that trigger this tool:
        - "What is this product? https://example.com/photo.jpg"
        - "Identify this image: /home/user/photos/image.jpg"
        - "What is in this image? /tmp/screenshot.png"
        - "Do a reverse image search on this URL"
        - "What brand is this? [image URL or file path]"
        - "Find similar images to this one"
        - "Read the text in this image"

    Args:
        image_source: A public image URL or a local file path to the image.
    """
    return await _do_google_lens(image_source)


# ---------------------------------------------------------------------------
# google_lens_detect (object detection + per-object Lens identification)
# ---------------------------------------------------------------------------

MAX_OBJECTS = 4


def _detect_objects(image_path: str, min_area_ratio: float = 0.02) -> list[dict]:
    """Detect distinct objects in an image using OpenCV contour detection.

    Returns list of dicts with keys: x, y, w, h, label (position description).
    """
    try:
        import cv2
        import numpy as np
    except ImportError:
        return []

    img = cv2.imread(image_path)
    if img is None:
        return []

    h, w = img.shape[:2]
    total_area = h * w
    min_area = total_area * min_area_ratio

    # Convert to grayscale and apply edge detection
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (7, 7), 0)
    edges = cv2.Canny(blurred, 30, 100)

    # Dilate edges to close gaps
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
    dilated = cv2.dilate(edges, kernel, iterations=3)

    # Find contours
    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Get bounding boxes for significant contours
    boxes = []
    for cnt in contours:
        x, y, bw, bh = cv2.boundingRect(cnt)
        area = bw * bh
        if area >= min_area and area < total_area * 0.95:
            boxes.append((x, y, bw, bh, area))

    if not boxes:
        return []

    # Sort by area descending
    boxes.sort(key=lambda b: b[4], reverse=True)

    # Merge overlapping boxes
    merged = []
    used = set()
    for i, (x1, y1, w1, h1, a1) in enumerate(boxes):
        if i in used:
            continue
        mx, my, mw, mh = x1, y1, w1, h1
        for j, (x2, y2, w2, h2, a2) in enumerate(boxes):
            if j <= i or j in used:
                continue
            # Check overlap
            ox = max(0, min(mx + mw, x2 + w2) - max(mx, x2))
            oy = max(0, min(my + mh, y2 + h2) - max(my, y2))
            overlap = ox * oy
            smaller_area = min(mw * mh, w2 * h2)
            if smaller_area > 0 and overlap / smaller_area > 0.3:
                # Merge
                nx = min(mx, x2)
                ny = min(my, y2)
                mw = max(mx + mw, x2 + w2) - nx
                mh = max(my + mh, y2 + h2) - ny
                mx, my = nx, ny
                used.add(j)
        merged.append((mx, my, mw, mh))
        used.add(i)

    # Add padding (10%) and generate position labels
    results = []
    for mx, my, mw, mh in merged[:MAX_OBJECTS]:
        pad_x = int(mw * 0.1)
        pad_y = int(mh * 0.1)
        cx = max(0, mx - pad_x)
        cy = max(0, my - pad_y)
        cw = min(w - cx, mw + 2 * pad_x)
        ch = min(h - cy, mh + 2 * pad_y)

        # Position label
        cy_center = (cy + ch / 2) / h
        cx_center = (cx + cw / 2) / w
        v_pos = "top" if cy_center < 0.33 else ("middle" if cy_center < 0.66 else "bottom")
        h_pos = "left" if cx_center < 0.33 else ("center" if cx_center < 0.66 else "right")
        label = f"{v_pos}-{h_pos}"

        results.append({"x": cx, "y": cy, "w": cw, "h": ch, "label": label})

    return results


async def _lens_upload_in_session(page, file_path: str) -> str:
    """Upload a single image to Google Lens within an existing browser session.

    Navigates to images.google.com, uploads, and extracts results.
    """
    await page.goto("https://images.google.com/?hl=en", wait_until="domcontentloaded", timeout=30000)
    await _dismiss_consent(page)
    await page.wait_for_timeout(1000)

    # Click the camera/lens icon
    lens_btn = page.locator("[aria-label='Search by image'], .Gdd5U, .nDcEnd, .tdAaF")
    if await lens_btn.count() > 0:
        await lens_btn.first.click()
        await page.wait_for_timeout(1500)

    # Upload the file
    file_input = page.locator("input[type='file']")
    if await file_input.count() == 0:
        return "Could not find upload input"
    await file_input.first.set_input_files(file_path)

    # Wait for results
    await page.wait_for_load_state("domcontentloaded", timeout=30000)
    await page.wait_for_timeout(5000)
    await _dismiss_consent(page)

    # Click "Change to English" if needed
    try:
        eng_link = page.locator("a:has-text('Change to English'), a:has-text('English')")
        if await eng_link.count() > 0:
            await eng_link.first.click()
            await page.wait_for_load_state("domcontentloaded", timeout=10000)
            await _dismiss_consent(page)
    except Exception:
        pass

    await page.wait_for_timeout(3000)

    # Check for errors
    page_text = await page.evaluate("() => document.body.innerText.substring(0, 500)")
    if "unusual traffic" in page_text.lower() or "sorry" in page_text.lower():
        return "Rate limited by Google. Try again later."
    if "No image at the URL" in page_text or "Something went wrong" in page_text:
        return "Google Lens could not process this image crop."

    # Extract results (same scraper as _do_google_lens)
    data = await page.evaluate(
        r"""
        () => {
            const data = { ai_overview: '', visual_matches: [], product_results: [] };

            const bodyText = document.body.innerText;
            const aiIdx = bodyText.indexOf('AI Overview');
            if (aiIdx !== -1) {
                const afterAi = bodyText.substring(aiIdx + 11, aiIdx + 1500);
                const endMarkers = ['Visual matches', 'Exact matches', 'Products', 'Related links', 'Footer'];
                let endIdx = afterAi.length;
                for (const marker of endMarkers) {
                    const idx = afterAi.indexOf(marker);
                    if (idx !== -1 && idx < endIdx) endIdx = idx;
                }
                data.ai_overview = afterAi.substring(0, endIdx).trim();
                if (data.ai_overview.startsWith('\n')) data.ai_overview = data.ai_overview.substring(1).trim();
                const diveIdx = data.ai_overview.indexOf('Dive deeper');
                if (diveIdx !== -1) data.ai_overview = data.ai_overview.substring(0, diveIdx).trim();
            }

            const allHeadings = document.querySelectorAll('div[role="heading"]');
            const skipTexts = new Set(['Choose what you\'re giving feedback on', 'Customised date range', 'Search Results', 'Filters and topics']);
            for (const h of allHeadings) {
                if (data.visual_matches.length >= 5) break;
                const text = h.innerText.trim();
                if (!text || text.length < 3 || skipTexts.has(text)) continue;
                const parentLink = h.closest('a[href]');
                let url = '', source = '';
                if (parentLink) {
                    url = parentLink.href || '';
                    const linkLines = parentLink.innerText.trim().split('\n');
                    if (linkLines.length > 1 && linkLines[0] !== text) source = linkLines[0];
                }
                if (url && !url.includes('google.com/search')) {
                    data.visual_matches.push({ name: text, url: url, source: source });
                }
            }

            if (!data.ai_overview && data.visual_matches.length === 0) {
                const main = document.querySelector('[role="main"], body');
                if (main) data.raw_text = main.innerText.substring(0, 3000);
            }

            return data;
        }
        """
    )

    lines = []
    if data.get("ai_overview"):
        lines.append(f"Identification: {data['ai_overview']}")
    if data.get("visual_matches"):
        lines.append("Visual Matches:")
        for i, m in enumerate(data["visual_matches"][:3], 1):
            entry = f"  {i}. {m['name']}"
            if m.get("source"):
                entry += f" ({m['source']})"
            lines.append(entry)
            if m.get("url"):
                lines.append(f"     {m['url']}")
    if not lines and data.get("raw_text"):
        raw = re.sub(r'\n{3,}', '\n\n', data["raw_text"]).strip()[:1000]
        lines.append(raw)
    if not lines:
        lines.append("Could not identify this object.")

    return "\n".join(lines)


async def _do_google_lens_detect(image_path: str) -> str:
    """Detect objects in an image and identify each via Google Lens."""
    try:
        import cv2
    except ImportError:
        return "opencv-python-headless is required for object detection. Install with: pip install opencv-python-headless"

    file_path = str(Path(image_path).expanduser().resolve())
    if not os.path.isfile(file_path):
        return f"File not found: {image_path}"

    # Detect objects
    objects = _detect_objects(file_path)

    # Create temp crops
    import tempfile
    img = cv2.imread(file_path)
    if img is None:
        return f"Could not read image: {file_path}"

    crop_files = []
    temp_dir = tempfile.mkdtemp(prefix="lens_detect_")
    try:
        for i, obj in enumerate(objects):
            crop = img[obj["y"]:obj["y"] + obj["h"], obj["x"]:obj["x"] + obj["w"]]
            crop_path = os.path.join(temp_dir, f"object_{i}_{obj['label']}.jpg")
            cv2.imwrite(crop_path, crop)
            crop_files.append((crop_path, obj["label"]))

        if not crop_files:
            # Fallback: no objects detected, just pass original
            return await _do_google_lens(file_path)

        # Run Lens on original + each crop in a single browser session
        async with async_playwright() as pw:
            browser, context = await _launch_browser(pw)
            page = await context.new_page()

            results = []

            try:
                # First: original full image
                og_result = await _lens_upload_in_session(page, file_path)
                results.append(("Full image (original)", og_result))
                await page.wait_for_timeout(3000)

                # Then: each detected object crop
                for crop_path, label in crop_files:
                    crop_result = await _lens_upload_in_session(page, crop_path)
                    results.append((f"Object ({label})", crop_result))
                    await page.wait_for_timeout(3000)

            except Exception as e:
                results.append(("Error", str(e)))

            finally:
                await browser.close()

        # Format output
        lines = [
            f"Google Lens Object Detection Results",
            f"Image: {image_path}",
            f"Objects detected: {len(crop_files)}",
            ""
        ]
        for label, result in results:
            lines.append(f"--- {label} ---")
            lines.append(result)
            lines.append("")

        return "\n".join(lines)

    finally:
        # Clean up temp files
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)


@mcp.tool()
async def google_lens_detect(image_source: str) -> str:
    """Detect and identify all objects in an image using OpenCV object detection and Google Lens.

    Unlike google_lens which sends the full image, this tool:
    1. Uses OpenCV to detect distinct objects/regions in the image
    2. Crops each object separately
    3. Sends the original image AND each crop to Google Lens
    4. Returns identification results for each object

    This is useful when an image contains multiple items (e.g. a monitor AND a hardware device)
    and you want each identified separately.

    Requires a local file path (not a URL).

    Sample prompts that trigger this tool:
        - "Detect and identify all objects in this image: /path/to/photo.jpg"
        - "What are all the items in this photo? /path/to/image.png"
        - "Identify each object separately in /path/to/setup.jpg"

    Args:
        image_source: Local file path to the image.
    """
    if image_source.startswith(("http://", "https://")):
        return "google_lens_detect only works with local files. Use google_lens for URLs."
    return await _do_google_lens_detect(image_source)


# ---------------------------------------------------------------------------
# list_images (helper for text-only models to discover local images)
# ---------------------------------------------------------------------------

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg", ".tiff", ".tif"}
DEFAULT_IMAGE_DIR = os.path.expanduser("~/lens")


@mcp.tool()
async def list_images(directory: str = "") -> str:
    """List image files in a directory so you can pass them to google_lens.

    This is useful for text-only models that cannot receive images directly.
    The user saves an image to ~/lens/ (or any folder) and asks you to identify it.

    Default directory: ~/lens/

    Sample prompts that trigger this tool:
        - "What images are in my lens folder?"
        - "Identify the latest image"
        - "Check ~/lens/ for new images"
        - "What did I save?"

    Args:
        directory: Folder to scan for images. Defaults to ~/lens/.
    """
    scan_dir = directory.strip() if directory.strip() else DEFAULT_IMAGE_DIR
    scan_dir = str(Path(scan_dir).expanduser().resolve())

    if not os.path.isdir(scan_dir):
        return f"Directory not found: {scan_dir}\nCreate it with: mkdir -p ~/lens\nThen save images there for identification."

    files = []
    for f in os.listdir(scan_dir):
        ext = os.path.splitext(f)[1].lower()
        if ext in IMAGE_EXTENSIONS:
            full_path = os.path.join(scan_dir, f)
            stat = os.stat(full_path)
            files.append((f, full_path, stat.st_mtime, stat.st_size))

    if not files:
        return f"No images found in {scan_dir}\nSupported formats: {', '.join(sorted(IMAGE_EXTENSIONS))}"

    # Sort by modification time, newest first
    files.sort(key=lambda x: x[2], reverse=True)

    lines = [f"Images in {scan_dir} ({len(files)} found):\n"]
    for name, path, mtime, size in files:
        dt = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
        size_kb = size / 1024
        lines.append(f"  {name}")
        lines.append(f"    Path: {path}")
        lines.append(f"    Modified: {dt} | Size: {size_kb:.0f} KB")

    lines.append(f"\nTo identify an image, use google_lens with the file path above.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# ocr_image (local OCR using RapidOCR - no internet needed)
# ---------------------------------------------------------------------------

@mcp.tool()
async def ocr_image(image_source: str) -> str:
    """Extract text from an image using local OCR. No internet connection needed.

    Uses RapidOCR (PaddleOCR models on ONNX Runtime) to read text from
    screenshots, documents, photos of signs, labels, receipts, or any image
    containing text. Runs entirely locally.

    This gives text-reading capabilities to text-only models without needing
    a vision model or internet access.

    Sample prompts that trigger this tool:
        - "Read the text in this image: /path/to/image.jpg"
        - "OCR this screenshot: /path/to/screenshot.png"
        - "What does this document say? /path/to/document.jpg"
        - "Extract text from /path/to/receipt.jpg"
        - "Read this label: /path/to/photo.jpg"

    Args:
        image_source: Local file path to the image (e.g. /home/user/photo.jpg).
    """
    try:
        from rapidocr_onnxruntime import RapidOCR
    except ImportError:
        return "rapidocr-onnxruntime is required for OCR. Install with: pip install rapidocr-onnxruntime"

    file_path = str(Path(image_source).expanduser().resolve())
    if not os.path.isfile(file_path):
        return f"File not found: {image_source}\nPlease provide a valid file path."

    try:
        engine = RapidOCR()
        result, elapse = engine(file_path)

        if not result:
            return f"No text found in image: {image_source}"

        # Sort by vertical position (top to bottom) then left to right
        # Each result is [bounding_box, text, confidence]
        sorted_results = sorted(result, key=lambda r: (
            min(p[1] for p in r[0]),  # min Y of bounding box
            min(p[0] for p in r[0]),  # min X of bounding box
        ))

        lines = [f"OCR Results for: {image_source}"]
        lines.append(f"Text regions found: {len(sorted_results)}")
        lines.append("")

        # Group text by approximate vertical position into lines
        text_lines = []
        current_line_texts = []
        prev_y = None
        line_threshold = 15  # pixels threshold for same-line grouping

        for box, text, confidence in sorted_results:
            min_y = min(p[1] for p in box)
            if prev_y is not None and abs(min_y - prev_y) > line_threshold:
                if current_line_texts:
                    text_lines.append(" ".join(current_line_texts))
                current_line_texts = []
            current_line_texts.append(text)
            prev_y = min_y

        if current_line_texts:
            text_lines.append(" ".join(current_line_texts))

        lines.append("--- Extracted Text ---")
        for tl in text_lines:
            lines.append(tl)

        # Also provide raw results with confidence for detailed analysis
        lines.append("")
        lines.append("--- Detailed Results (with confidence) ---")
        for box, text, confidence in sorted_results:
            lines.append(f"[{confidence:.0%}] {text}")

        det_time, cls_time, rec_time = elapse
        lines.append(f"\nProcessing time: detection={det_time:.2f}s, recognition={rec_time:.2f}s")

        return "\n".join(lines)

    except Exception as e:
        return f"OCR failed: {e}"


# ---------------------------------------------------------------------------
# transcribe_video (YouTube/video transcription with timestamps)
# ---------------------------------------------------------------------------

TRANSCRIBE_CACHE_DIR = os.path.join(os.path.expanduser("~"), ".cache", "noapi-google-search-mcp")


def _format_timestamp(seconds: float) -> str:
    """Format seconds into H:MM:SS or M:SS."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


@mcp.tool()
async def transcribe_video(
    url: str,
    model_size: str = "base",
    language: str = "",
) -> str:
    """Download and transcribe a YouTube video (or any video URL) with timestamps.

    Downloads the audio, transcribes it locally using Whisper, and returns a
    full timestamped transcript. The LLM can then answer questions about the
    video content and point to specific timestamps.

    Supported model sizes: tiny, base, small, medium, large
    - tiny: fastest, least accurate (~75MB)
    - base: good balance of speed and accuracy (~150MB, default)
    - small: better accuracy, slower (~500MB)
    - medium: high accuracy, much slower (~1.5GB)
    - large: best accuracy, slowest (~3GB)

    Models are downloaded automatically on first use.

    Sample prompts that trigger this tool:
        - "Transcribe this video: https://youtube.com/watch?v=..."
        - "What is discussed in this video? https://youtube.com/watch?v=..."
        - "Summarize this YouTube video: https://..."
        - "At what timestamp do they talk about X in https://..."
        - "Explain the concept from 5:30 in this video: https://..."

    Args:
        url: YouTube URL or any video URL supported by yt-dlp.
        model_size: Whisper model size (tiny/base/small/medium/large). Default: base.
        language: Language code (e.g. "en", "de", "fr"). Auto-detected if empty.
    """
    try:
        import yt_dlp
    except ImportError:
        return "yt-dlp is required. Install with: pip install yt-dlp"

    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return "faster-whisper is required. Install with: pip install faster-whisper"

    # Validate model size
    valid_sizes = ("tiny", "base", "small", "medium", "large")
    if model_size not in valid_sizes:
        model_size = "base"

    # Create cache directory
    os.makedirs(TRANSCRIBE_CACHE_DIR, exist_ok=True)

    # Download audio
    audio_path = os.path.join(TRANSCRIBE_CACHE_DIR, "audio_temp")
    ydl_opts = {
        "format": "bestaudio[ext=m4a]/bestaudio",
        "outtmpl": audio_path + ".%(ext)s",
        "quiet": True,
        "no_warnings": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get("title", "Unknown")
            duration = info.get("duration", 0)
            uploader = info.get("uploader", "Unknown")
            ext = info.get("ext", "m4a")
            actual_audio_path = audio_path + "." + ext
    except Exception as e:
        return f"Failed to download video: {e}"

    if not os.path.isfile(actual_audio_path):
        # Try to find the downloaded file
        for f in os.listdir(TRANSCRIBE_CACHE_DIR):
            if f.startswith("audio_temp"):
                actual_audio_path = os.path.join(TRANSCRIBE_CACHE_DIR, f)
                break
        else:
            return "Failed to download audio from the video."

    try:
        # Transcribe
        model = WhisperModel(model_size, device="cpu", compute_type="int8")

        transcribe_opts = {"beam_size": 5}
        if language:
            transcribe_opts["language"] = language

        segments_gen, info = model.transcribe(actual_audio_path, **transcribe_opts)

        # Collect all segments
        segments = list(segments_gen)

        if not segments:
            return f"No speech detected in: {title}"

        # Format output
        lines = [
            f"Video Transcript",
            f"Title: {title}",
            f"Channel: {uploader}",
            f"Duration: {_format_timestamp(duration)}",
            f"Language: {info.language} (confidence: {info.language_probability:.0%})",
            f"URL: {url}",
            f"",
            f"--- Transcript ---",
        ]

        for seg in segments:
            start = _format_timestamp(seg.start)
            end = _format_timestamp(seg.end)
            text = seg.text.strip()
            lines.append(f"[{start} - {end}] {text}")

        lines.append("")
        lines.append("--- End of Transcript ---")
        lines.append(f"Total segments: {len(segments)}")

        return "\n".join(lines)

    except Exception as e:
        return f"Transcription failed: {e}"

    finally:
        # Clean up audio file
        try:
            os.remove(actual_audio_path)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# extract_video_clip (cut a segment from a video by timestamps)
# ---------------------------------------------------------------------------

CLIPS_DIR = os.path.join(os.path.expanduser("~"), "clips")


@mcp.tool()
async def extract_video_clip(
    url: str,
    start_seconds: float,
    end_seconds: float,
    buffer_seconds: float = 3.0,
    output_filename: str = "",
) -> str:
    """Extract a video clip between two timestamps from a YouTube video or local file.

    Downloads the video (if a URL), then cuts the segment between start_seconds
    and end_seconds. A buffer is added before and after to avoid cutting off
    content. The clip is saved to ~/clips/.

    Use this after transcribe_video to extract segments about specific topics.

    Sample prompts that trigger this tool:
        - "Extract the part where they discuss X (2:30 to 5:15)"
        - "Cut the segment from 10:00 to 15:30 from this video"
        - "Save the clip about Y from the video"
        - "Get me the intro section of this video"

    Args:
        url: YouTube URL, video URL, or local file path.
        start_seconds: Start time in seconds (e.g. 150 for 2:30).
        end_seconds: End time in seconds (e.g. 315 for 5:15).
        buffer_seconds: Extra seconds before/after the segment (default: 3).
        output_filename: Optional filename for the clip (without extension).
    """
    try:
        import av
    except ImportError:
        return "PyAV is required. Install with: pip install av"

    os.makedirs(CLIPS_DIR, exist_ok=True)
    os.makedirs(TRANSCRIBE_CACHE_DIR, exist_ok=True)

    # Apply buffer
    clip_start = max(0, start_seconds - buffer_seconds)
    clip_end = end_seconds + buffer_seconds

    video_path = None
    title = "clip"

    # Check if URL is a local file
    if os.path.isfile(url):
        video_path = url
        title = Path(url).stem
    else:
        # Download video with yt-dlp
        try:
            import yt_dlp
        except ImportError:
            return "yt-dlp is required. Install with: pip install yt-dlp"

        video_dl_path = os.path.join(TRANSCRIBE_CACHE_DIR, "video_temp")
        ydl_opts = {
            "format": "best[ext=mp4][height<=1080]/best[ext=mp4]/best",
            "outtmpl": video_dl_path + ".%(ext)s",
            "quiet": True,
            "no_warnings": True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                title = info.get("title", "clip")
                ext = info.get("ext", "mp4")
                video_path = video_dl_path + "." + ext
        except Exception as e:
            return f"Failed to download video: {e}"

        if not video_path or not os.path.isfile(video_path):
            # Find the downloaded file
            for f in os.listdir(TRANSCRIBE_CACHE_DIR):
                if f.startswith("video_temp"):
                    video_path = os.path.join(TRANSCRIBE_CACHE_DIR, f)
                    break
            else:
                return "Failed to download video."

    # Generate output filename
    safe_title = re.sub(r'[^\w\s-]', '', title)[:50].strip().replace(' ', '_')
    if output_filename:
        safe_title = re.sub(r'[^\w\s-]', '', output_filename)[:50].strip().replace(' ', '_')

    start_str = _format_timestamp(clip_start).replace(':', '-')
    end_str = _format_timestamp(clip_end).replace(':', '-')
    out_name = f"{safe_title}_{start_str}_to_{end_str}.mp4"
    out_path = os.path.join(CLIPS_DIR, out_name)

    try:
        inp = av.open(video_path)

        # Get streams
        video_stream = inp.streams.video[0] if inp.streams.video else None
        audio_stream = inp.streams.audio[0] if inp.streams.audio else None

        if not video_stream and not audio_stream:
            inp.close()
            return "No video or audio streams found in the file."

        total_duration = float(inp.duration / av.time_base) if inp.duration else 0
        if total_duration and clip_end > total_duration:
            clip_end = total_duration

        out = av.open(out_path, 'w')

        # Create output streams
        o_vs = None
        if video_stream:
            o_vs = out.add_stream('libx264', rate=video_stream.average_rate)
            o_vs.width = video_stream.codec_context.width
            o_vs.height = video_stream.codec_context.height
            o_vs.pix_fmt = video_stream.codec_context.pix_fmt or 'yuv420p'

        o_as = None
        if audio_stream:
            o_as = out.add_stream('aac', rate=audio_stream.codec_context.sample_rate)
            o_as.layout = audio_stream.codec_context.layout

        # Extract video frames
        if o_vs and video_stream:
            inp.seek(int(clip_start * av.time_base), any_frame=False)
            for frame in inp.decode(video=0):
                ts = float(frame.time) if frame.time is not None else 0
                if ts < clip_start:
                    continue
                if ts > clip_end:
                    break
                for packet in o_vs.encode(frame):
                    out.mux(packet)
            for packet in o_vs.encode():
                out.mux(packet)

        # Extract audio frames
        if o_as and audio_stream:
            inp.seek(int(clip_start * av.time_base), any_frame=False)
            for frame in inp.decode(audio=0):
                ts = float(frame.time) if frame.time is not None else 0
                if ts < clip_start:
                    continue
                if ts > clip_end:
                    break
                frame.pts = None
                for packet in o_as.encode(frame):
                    out.mux(packet)
            for packet in o_as.encode():
                out.mux(packet)

        out.close()
        inp.close()

        clip_size = os.path.getsize(out_path)
        clip_dur = clip_end - clip_start

        result = [
            f"Video clip extracted successfully!",
            f"",
            f"Source: {title}",
            f"Segment: {_format_timestamp(clip_start)} - {_format_timestamp(clip_end)} "
            f"(requested {_format_timestamp(start_seconds)} - {_format_timestamp(end_seconds)} + {buffer_seconds}s buffer)",
            f"Duration: {_format_timestamp(clip_dur)}",
            f"Size: {clip_size / (1024*1024):.1f} MB",
            f"Saved to: {out_path}",
        ]
        return "\n".join(result)

    except Exception as e:
        return f"Failed to extract clip: {e}"

    finally:
        # Clean up downloaded video (keep clips)
        if not os.path.isfile(url):
            try:
                if video_path and os.path.isfile(video_path):
                    os.remove(video_path)
            except OSError:
                pass


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

    Sample prompts that trigger this tool:
        - "Read this article for me: https://example.com/article"
        - "What does this page say? https://..."
        - "Summarize the content at this URL"
        - "Go to this link and tell me what it says"

    Args:
        url: The full URL to visit and extract text from.
    """
    return await _fetch_page_text(url)
