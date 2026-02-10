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
| Google News | Built-in | Usually not available |
| Google Scholar | Built-in | Not available |
| Google Images | Built-in | Separate API needed |
| Google Trends | Built-in | Separate API needed |
| Page fetching | Built-in `visit_page` tool | Usually separate |

## Tools

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

You don't need to teach the LLM anything. MCP automatically exposes all tool names, descriptions, and parameters to the model. When you ask a question like:

- *"What are the latest AI news?"* → LLM calls `google_news`
- *"Find me papers on quantum computing"* → LLM calls `google_scholar`
- *"Search Reddit for home lab setups"* → LLM calls `google_search` with `site="reddit.com"`
- *"What's trending in tech?"* → LLM calls `google_trends`
- *"Show me images of the Northern Lights"* → LLM calls `google_images`
- *"Read this article for me: https://..."* → LLM calls `visit_page`

The LLM picks the right tool and parameters automatically based on your request.

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
