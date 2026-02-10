# noapi-google-search-mcp

**Google Search for Local LLMs — No API Key Required**

An MCP (Model Context Protocol) server that gives your local LLM real Google search and page fetching abilities using headless Chromium via Playwright. No Google API key, no Custom Search Engine setup, no usage limits — just real Google results.

Works with LM Studio, Claude Desktop, and any MCP-compatible client.

## Why This Instead of API-Based Alternatives?

| | **noapi-google-search-mcp** | API-based MCP servers |
|---|---|---|
| API key required | No | Yes (Google CSE API) |
| Cost | Free | Paid after 100 queries/day |
| Setup time | `pip install` + go | Create Google Cloud project, enable API, get key, configure CSE |
| Results quality | Real Google results | Custom Search Engine (different ranking) |
| JavaScript pages | Renders them (Chromium) | Cannot render JS |
| Page fetching | Built-in `visit_page` tool | Usually separate |

## Tools

- **`google_search`** — Search Google with structured results (titles, URLs, snippets)
  - `time_range` — Filter by recency: `past_hour`, `past_day`, `past_week`, `past_month`, `past_year`
  - `site` — Limit to a domain (e.g. `reddit.com`, `stackoverflow.com`)
  - `page` — Pagination support (page 1, 2, 3...)
- **`google_news`** — Search Google News for headlines with source and timestamp
- **`visit_page`** — Fetch any URL and extract readable text content

## Features

- Headless Chromium renders JavaScript-heavy pages
- Consent banner auto-dismissal
- Smart content extraction (strips nav, ads, footers)
- Zero configuration — no API keys, no environment variables

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

## Usage

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
