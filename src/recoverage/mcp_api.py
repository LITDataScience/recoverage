"""Model Context Protocol tool surface over the code graph.

This is the query interface the generator uses. It speaks a single JSON-RPC
request and returns a JSON-RPC response. It does not open a socket.
"""

from __future__ import annotations

import json
from typing import Any

from recoverage.graph import CodeGraph
from recoverage.version import __version__

PROTOCOL = "2024-11-05"
TOOLS = [
    {
        "name": "query_context",
        "description": "PageRank-scoped dependency neighborhood for one focal symbol.",
        "inputSchema": {
            "type": "object",
            "properties": {"symbol": {"type": "string"}, "limit": {"type": "integer"}},
            "required": ["symbol"],
        },
    },
    {
        "name": "pagerank",
        "description": "Return PageRank weights for indexed symbols.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "communities",
        "description": "Return Louvain community ids for indexed symbols.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def handle(message: dict[str, Any], graph: CodeGraph) -> dict[str, Any]:
    method = message.get("method")
    request_id = message.get("id")
    if method == "initialize":
        return _ok(
            request_id,
            {
                "protocolVersion": PROTOCOL,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "recoverage", "version": __version__},
            },
        )
    if method == "tools/list":
        return _ok(request_id, {"tools": TOOLS})
    if method == "tools/call":
        params = message.get("params") or {}
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if name == "query_context":
            payload = graph.query_context(str(arguments.get("symbol", "")), int(arguments.get("limit") or 8))
        elif name == "pagerank":
            payload = [{"symbol": key, "pagerank": value} for key, value in sorted(graph.pagerank.items())]
        elif name == "communities":
            payload = [{"symbol": key, "community": value} for key, value in sorted(graph.communities.items())]
        else:
            return _err(request_id, f"unknown tool {name}")
        return _ok(request_id, {"content": [{"type": "text", "text": json.dumps(payload)}]})
    return _err(request_id, f"unknown method {method}")


def _ok(request_id, result) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _err(request_id, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": message}}
