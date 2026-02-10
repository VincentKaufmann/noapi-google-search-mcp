"""
Google Search MCP Server

A Model Context Protocol (MCP) server that performs real Google searches
using headless Chromium (via Playwright) and returns structured results.

Tools provided:
    - google_search(query, num_results): Searches Google and returns titles, URLs, snippets
    - visit_page(url): Fetches a URL and returns its text content
"""

import re

from mcp.server.fastmcp import FastMCP
from playwright.async_api import async_playwright

mcp = FastMCP("google-search")

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux aarch64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


async def _do_google_search(query: str, num_results: int = 5) -> str:
    """Launch headless Chromium, search Google, and scrape results."""
    async with async_playwright() as pw:
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
        page = await context.new_page()

        try:
            # Navigate to Google search
            url = f"https://www.google.com/search?q={query}&hl=en&num={num_results + 5}"
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)

            # Dismiss consent banner if present (common in some regions)
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
                pass  # No consent banner or already dismissed

            # Wait for search results to appear
            await page.wait_for_selector("div#search", timeout=15000)

            # Extract results using multiple selector strategies
            results = await page.evaluate(
                """
                (numResults) => {
                    const results = [];

                    // Strategy 1: Standard search result divs
                    const containers = document.querySelectorAll('div#search div.g');
                    for (const el of containers) {
                        if (results.length >= numResults) break;

                        const linkEl = el.querySelector('a[href^="http"]');
                        const titleEl = el.querySelector('h3');

                        // Snippet can be in various containers
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
            lines = [f"Google Search Results for: {query}\n"]
            for i, r in enumerate(results[:num_results], 1):
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
async def google_search(query: str, num_results: int = 5) -> str:
    """Search Google and return results with titles, URLs, and snippets.

    Args:
        query: The search query string.
        num_results: Number of results to return (default 5, max 10).
    """
    num_results = max(1, min(num_results, 10))
    return await _do_google_search(query, num_results)


MAX_PAGE_CHARS = 8000


async def _fetch_page_text(url: str) -> str:
    """Fetch a URL with headless Chromium and extract readable text."""
    async with async_playwright() as pw:
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
        page = await context.new_page()

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            # Wait a moment for JS-rendered content
            await page.wait_for_timeout(2000)

            # Extract readable text, stripping nav/footer/script noise
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

            # Clean up whitespace: collapse multiple blank lines
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
