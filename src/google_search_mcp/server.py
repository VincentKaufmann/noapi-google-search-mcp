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

                    // Price — use data attribute (most reliable)
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

                    // Key stats — use first line only (labels include tooltip descriptions)
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
                        day_str += f" — {f['condition']}"
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
