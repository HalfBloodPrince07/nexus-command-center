"""FastMCP server for the Nexus OS agent toolbelt."""
from __future__ import annotations

import os
from typing import Any

from fastapi.encoders import jsonable_encoder
from fastmcp import FastMCP
from pydantic import BaseModel
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from backend.config import settings
from backend.mcp import tools as toolbelt


class MCPAuthMiddleware(BaseHTTPMiddleware):
    """Protect HTTP MCP routes with bearer auth or localhost-only access."""

    async def dispatch(self, request: Request, call_next):
        token = os.getenv("MCP_AUTH_TOKEN", "").strip()
        if token:
            expected = f"Bearer {token}"
            if request.headers.get("authorization") != expected:
                return JSONResponse({"detail": "Unauthorized"}, status_code=401)
            return await call_next(request)

        host = request.client.host if request.client else ""
        if host not in {"127.0.0.1", "::1", "localhost", "testclient"}:
            return JSONResponse({"detail": "Localhost access only"}, status_code=403)
        return await call_next(request)


def _encode_tool_result(result: Any) -> dict[str, Any]:
    if isinstance(result, BaseModel):
        return result.model_dump(mode="json")
    return jsonable_encoder(result)


def create_mcp_server() -> FastMCP:
    server = FastMCP(
        "Nexus OS Agent Toolbelt",
        instructions="Expose Nexus OS agent capabilities to external MCP clients.",
        version=settings.APP_VERSION,
    )

    for tool in toolbelt.REGISTERED_TOOLS:
        server.tool(timeout=float(settings.SUPERVISOR_TIMEOUT_SECONDS))(tool)

    @server.custom_route("/health", methods=["GET"], include_in_schema=True)
    async def health(_: Request) -> Response:
        return JSONResponse({"status": "ok", "service": "nexus-os-mcp"})

    @server.custom_route("/tools/list", methods=["GET"], include_in_schema=True)
    async def list_registered_tools(_: Request) -> Response:
        items = []
        for item in await server.list_tools():
            items.append(
                {
                    "name": item.name,
                    "description": item.description,
                    "input_schema": item.parameters,
                    "output_schema": item.output_schema,
                }
            )
        return JSONResponse({"tools": jsonable_encoder(items)})

    @server.custom_route("/tools/{tool_name}/invoke", methods=["POST"], include_in_schema=True)
    async def invoke_tool(request: Request) -> Response:
        tool_name = request.path_params["tool_name"]
        payload = await request.json()
        if not isinstance(payload, dict):
            return JSONResponse({"detail": "JSON object body required"}, status_code=422)
        tool = await server.get_tool(tool_name)
        if tool is None:
            return JSONResponse({"detail": f"Unknown tool: {tool_name}"}, status_code=404)
        result = await getattr(toolbelt, tool_name)(**payload)
        return JSONResponse({"result": _encode_tool_result(result)})

    return server


mcp = create_mcp_server()


def create_app() -> Starlette:
    return mcp.http_app(
        path="/mcp",
        transport="http",
        stateless_http=True,
        middleware=[Middleware(MCPAuthMiddleware)],
    )
