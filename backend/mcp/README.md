# Nexus OS MCP Server

The MCP server exposes the Nexus OS agent toolbelt through FastMCP for Claude Desktop, Claude Code, and custom MCP clients.

## Start

```powershell
conda run -n Command python -m backend.mcp_server
```

The server listens on `127.0.0.1:8765` by default. Set `MCP_SERVER_PORT` to change the port.

When `MCP_AUTH_TOKEN` is unset, the server binds to localhost only. When `MCP_AUTH_TOKEN` is set, include `Authorization: Bearer <token>` on HTTP requests.

## HTTP Endpoints

- MCP transport: `http://127.0.0.1:8765/mcp`
- Tool reflection: `http://127.0.0.1:8765/tools/list`
- Test/helper invocation: `POST http://127.0.0.1:8765/tools/{tool_name}/invoke`

Example:

```powershell
Invoke-RestMethod `
  -Uri http://127.0.0.1:8765/tools/search_local_files/invoke `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"query":"known indexed file","top_k":5}'
```

## Claude Desktop

Add this to your Claude Desktop MCP configuration:

```json
{
  "mcpServers": {
    "nexus-os": {
      "url": "http://127.0.0.1:8765/mcp"
    }
  }
}
```

With bearer auth:

```json
{
  "mcpServers": {
    "nexus-os": {
      "url": "http://127.0.0.1:8765/mcp",
      "headers": {
        "Authorization": "Bearer ${MCP_AUTH_TOKEN}"
      }
    }
  }
}
```

## Claude Code

```powershell
claude mcp add --transport http nexus-os http://127.0.0.1:8765/mcp
```

With bearer auth:

```powershell
claude mcp add --transport http nexus-os http://127.0.0.1:8765/mcp --header "Authorization: Bearer %MCP_AUTH_TOKEN%"
```

## Exposed Tools

- `search_local_files(query: str, top_k: int = 5)`
- `search_web(query: str, max_results: int = 10)`
- `save_memory(fact: str, category: str, importance: int)`
- `get_journal_insights(date_range: str = "7d", topic: str | None = None)`
- `save_research_report(title: str, query: str)`
- `analyze_image(image_path: str, question: str)`
