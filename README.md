# noapi-google-search-mcp

**Google Search for Local LLMs — No API Key Required**

An MCP (Model Context Protocol) server that gives your local LLM real Google search and browsing abilities using headless Chromium via Playwright. No Google API key, no Custom Search Engine setup, no usage limits — just real Google results.

Works with LM Studio, Claude Desktop, and any MCP-compatible client.

## Why This Instead of API-Based Alternatives?

| | **noapi-google-search-mcp** | API-based MCP servers |
|---|---|---|
| API key required | No | Yes (Google CSE API) |
| Cost | Free | Paid after 100 queries/day |
| Setup time | `pip install` + go | Create Google Cloud project, enable API, get key, configure CSE |
| Results quality | Real Google results | Custom Search Engine (different ranking) |
| JavaScript pages | Renders them (Chromium) | Cannot render JS |
| Google Maps | Built-in | Not available |
| Google Weather | Built-in | Not available |
| Google Finance | Built-in | Not available |
| Google News | Built-in | Usually not available |
| Google Scholar | Built-in | Not available |
| Google Images | Built-in | Separate API needed |
| Google Trends | Built-in | Separate API needed |
| Page fetching | Built-in `visit_page` tool | Usually separate |

## Tools

### `google_maps` — Places Search

Search Google Maps for restaurants, businesses, and places with ratings, addresses, and reviews.

**Parameters:**
| Parameter | Description | Example |
|-----------|-------------|---------|
| `query` | Place search query (required) | `"pizza near Central Park"` |
| `num_results` | Number of results (1-10, default 5) | `5` |

---

### `google_weather` — Weather Lookup

Get current weather conditions and forecast for any location worldwide.

**Parameters:**
| Parameter | Description | Example |
|-----------|-------------|---------|
| `location` | City or location (required) | `"Dubai"`, `"New York"`, `"Tokyo"` |

Returns: temperature (°C/°F), condition, precipitation, humidity, wind, and multi-day forecast.

---

### `google_finance` — Stock & Market Data

Look up stock prices, market data, and company information from Google Finance.

**Parameters:**
| Parameter | Description | Example |
|-----------|-------------|---------|
| `query` | Stock ticker with exchange or company name (required) | `"AAPL:NASDAQ"`, `"TSLA:NASDAQ"` |

Returns: current price, change, market info, key stats, and company description.

---

### `google_search` — Web Search

Search Google and get structured results with titles, URLs, and snippets.

**Parameters:**
| Parameter | Description | Example |
|-----------|-------------|---------|
| `query` | Search query (required) | `"best python frameworks 2025"` |
| `num_results` | Number of results (1-10, default 5) | `5` |
| `time_range` | Filter by recency | `"past_hour"`, `"past_day"`, `"past_week"`, `"past_month"`, `"past_year"` |
| `site` | Limit to a domain | `"reddit.com"`, `"stackoverflow.com"`, `"github.com"`, `"arxiv.org"`, `"news.ycombinator.com"` |
| `page` | Results page (1-10, default 1) | `2` for next page |
| `language` | Language code | `"en"`, `"de"`, `"fr"`, `"es"`, `"ja"`, `"zh"` |
| `region` | Country/region code | `"us"`, `"gb"`, `"de"`, `"fr"`, `"jp"` |

**How your LLM uses it:** The LLM automatically sees these parameters in the tool definition. When you ask "search Reddit for Python tips from the past week", it will call `google_search(query="Python tips", site="reddit.com", time_range="past_week")`.

---

### `google_news` — News Search

Search Google News for recent headlines with source and timestamp.

**Parameters:**
| Parameter | Description | Example |
|-----------|-------------|---------|
| `query` | News search query (required) | `"AI regulation"` |
| `num_results` | Number of results (1-10, default 5) | `5` |

---

### `google_scholar` — Academic Search

Search Google Scholar for papers, citations, and research.

**Parameters:**
| Parameter | Description | Example |
|-----------|-------------|---------|
| `query` | Academic search query (required) | `"transformer attention mechanism"` |
| `num_results` | Number of results (1-10, default 5) | `5` |

Returns: title, URL, authors, citation count, and snippet for each paper.

---

### `google_images` — Image Search

Search Google Images and get image URLs.

**Parameters:**
| Parameter | Description | Example |
|-----------|-------------|---------|
| `query` | Image search query (required) | `"sunset over ocean"` |
| `num_results` | Number of results (1-10, default 5) | `5` |

---

### `google_trends` — Trends Lookup

Check Google Trends for topic interest, related topics, and related queries.

**Parameters:**
| Parameter | Description | Example |
|-----------|-------------|---------|
| `query` | Topic to check trends for (required) | `"artificial intelligence"` |

---

### `visit_page` — Page Fetcher

Fetch any URL and extract readable text content. Use after search to read full articles.

**Parameters:**
| Parameter | Description | Example |
|-----------|-------------|---------|
| `url` | Full URL to fetch (required) | `"https://example.com/article"` |

## How Does the LLM Know About These Tools?

You don't need to teach the LLM anything. MCP automatically exposes all tool names, descriptions, and parameters to the model. The LLM picks the right tool and parameters automatically based on your request.

## Sample Prompts

Here are example prompts you can type into LM Studio or Claude Desktop, and which tool the LLM will use:

### Maps & Places
| What you type | Tool called | Parameters used |
|--------------|-------------|-----------------|
| *"Find Italian restaurants near Times Square"* | `google_maps` | `query` |
| *"Where are the best coffee shops in Berlin?"* | `google_maps` | `query` |
| *"Search for hotels in Tokyo"* | `google_maps` | `query` |
| *"Find EV charging stations in San Francisco"* | `google_maps` | `query` |
| *"What are the top-rated gyms in London?"* | `google_maps` | `query` |

### Weather
| What you type | Tool called |
|--------------|-------------|
| *"What's the weather in Dubai?"* | `google_weather` |
| *"Is it going to rain in London today?"* | `google_weather` |
| *"What's the temperature in New York?"* | `google_weather` |
| *"Weather forecast for Tokyo this week"* | `google_weather` |

### Finance & Stocks
| What you type | Tool called |
|--------------|-------------|
| *"What's Apple's stock price?"* | `google_finance` |
| *"How is Tesla stock doing?"* | `google_finance` |
| *"Look up NVIDIA market cap"* | `google_finance` |
| *"How is the S&P 500 doing today?"* | `google_finance` |

### Web Search
| What you type | Tool called | Parameters used |
|--------------|-------------|-----------------|
| *"Search for the best Python web frameworks"* | `google_search` | `query` |
| *"Find Reddit discussions about home lab setups"* | `google_search` | `query` + `site="reddit.com"` |
| *"Search Stack Overflow for async Python examples"* | `google_search` | `query` + `site="stackoverflow.com"` |
| *"What's new in AI this week?"* | `google_search` | `query` + `time_range="past_week"` |
| *"Search Hacker News for posts about Rust"* | `google_search` | `query` + `site="news.ycombinator.com"` |
| *"Find GitHub repos for MCP servers"* | `google_search` | `query` + `site="github.com"` |
| *"Get page 2 of results for machine learning tutorials"* | `google_search` | `query` + `page=2` |
| *"Search for restaurants in Tokyo in Japanese"* | `google_search` | `query` + `language="ja"` + `region="jp"` |
| *"Find German news about the EU from the past month"* | `google_search` | `query` + `language="de"` + `time_range="past_month"` |

### News
| What you type | Tool called |
|--------------|-------------|
| *"What are today's top headlines?"* | `google_news` |
| *"Any recent news about the stock market?"* | `google_news` |
| *"What happened in the Japan election?"* | `google_news` |

### Academic Research
| What you type | Tool called |
|--------------|-------------|
| *"Find papers on transformer attention mechanisms"* | `google_scholar` |
| *"Look up academic research about CRISPR"* | `google_scholar` |
| *"What does the research say about intermittent fasting?"* | `google_scholar` |

### Images
| What you type | Tool called |
|--------------|-------------|
| *"Show me images of the Northern Lights"* | `google_images` |
| *"Find diagrams of neural network architecture"* | `google_images` |

### Trends
| What you type | Tool called |
|--------------|-------------|
| *"What's trending in tech right now?"* | `google_trends` |
| *"Is Python more popular than JavaScript?"* | `google_trends` |

### Page Reading
| What you type | Tool called |
|--------------|-------------|
| *"Read this article for me: https://..."* | `visit_page` |
| *"What does this page say? https://..."* | `visit_page` |

## Installation

### Quick Install (pipx — recommended)

```bash
pipx install noapi-google-search-mcp
playwright install chromium
```

This puts `noapi-google-search-mcp` on your PATH so you can use it directly.

### Install in a Virtual Environment

If you don't have pipx, install in a dedicated venv:

```bash
python3 -m venv ~/.local/share/noapi-google-search-mcp
~/.local/share/noapi-google-search-mcp/bin/pip install noapi-google-search-mcp
~/.local/share/noapi-google-search-mcp/bin/playwright install chromium
```

## Configuration

### LM Studio

Add to `~/.lmstudio/mcp.json`:

**If installed with pipx** (command is on PATH):

```json
{
  "mcpServers": {
    "google-search": {
      "command": "noapi-google-search-mcp",
      "env": {
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

**If installed in a venv** (use the full path):

```json
{
  "mcpServers": {
    "google-search": {
      "command": "~/.local/share/noapi-google-search-mcp/bin/noapi-google-search-mcp",
      "env": {
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

### Claude Desktop

Add to your Claude Desktop config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "google-search": {
      "command": "noapi-google-search-mcp"
    }
  }
}
```

> If installed in a venv, use the full path to the binary instead.

### As a CLI

```bash
noapi-google-search-mcp
```

Or:

```bash
python -m google_search_mcp
```

## Development

```bash
git clone https://github.com/VincentKaufmann/google-search-mcp.git
cd google-search-mcp
pip install -e .
playwright install chromium
```

## License

MIT
