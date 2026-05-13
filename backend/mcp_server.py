"""Standalone runner for the Nexus OS FastMCP server."""
from __future__ import annotations

import os

from starlette.middleware import Middleware

from backend.mcp.server import MCPAuthMiddleware, mcp


def main() -> None:
    port = int(os.getenv("MCP_SERVER_PORT", "8765"))
    host = "0.0.0.0" if os.getenv("MCP_AUTH_TOKEN") else "127.0.0.1"
    mcp.run(
        transport="http",
        host=host,
        port=port,
        path="/mcp",
        stateless_http=True,
        middleware=[Middleware(MCPAuthMiddleware)],
    )


if __name__ == "__main__":
    main()
