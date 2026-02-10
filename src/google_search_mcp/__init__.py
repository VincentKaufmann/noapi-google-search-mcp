"""Google Search MCP Server - Search Google and fetch pages via MCP."""

__version__ = "0.1.2"

from .server import mcp


def main():
    """Run the MCP server."""
    mcp.run(transport="stdio")
