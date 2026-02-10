# google-search-mcp

An MCP (Model Context Protocol) server that provides Google search and page fetching tools using headless Chromium via Playwright. Works with LM Studio, Claude Desktop, and any MCP-compatible client.

## Features

- **`google_search`** - Search Google and get structured results (titles, URLs, snippets)
- **`visit_page`** - Fetch any URL and extract readable text content
- Headless Chromium for JavaScript-rendered pages
- Consent banner auto-dismissal
- Smart content extraction (strips nav, ads, footers)

## Installation

```bash
pip install google-search-mcp
```

After installing, install the Playwright Chromium browser:

```bash
playwright install chromium
```

## Usage

### As a CLI

```bash
google-search-mcp
```

Or:

```bash
python -m google_search_mcp
```

### LM Studio

Add to `~/.lmstudio/mcp.json`:

```json
{
  "mcpServers": {
    "google-search": {
      "command": "google-search-mcp",
      "env": {
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

### Claude Desktop

Add to your Claude Desktop config:

```json
{
  "mcpServers": {
    "google-search": {
      "command": "google-search-mcp"
    }
  }
}
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
