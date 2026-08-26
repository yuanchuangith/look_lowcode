from __future__ import annotations

import os

import uvicorn
from mcp.server.transport_security import TransportSecuritySettings
from starlette.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp

from server import create_mcp


DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8890
ALLOWED_ORIGINS = [
    "http://cpm.gxp2.com",
    "https://cpm.gxp2.com",
]
ALLOWED_HEADERS = [
    "Accept",
    "Content-Type",
    "Last-Event-ID",
    "MCP-Protocol-Version",
    "Mcp-Session-Id",
]


def create_http_app(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> ASGIApp:
    transport_security = TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=[
            f"43.135.137.212:{port}",
            f"127.0.0.1:{port}",
            f"localhost:{port}",
        ],
        allowed_origins=ALLOWED_ORIGINS,
    )
    mcp = create_mcp(
        host=host,
        port=port,
        streamable_http_path="/mcp",
        json_response=False,
        stateless_http=False,
        transport_security=transport_security,
    )
    app = mcp.streamable_http_app()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=False,
        allow_methods=["POST", "GET", "DELETE", "OPTIONS"],
        allow_headers=ALLOWED_HEADERS,
        expose_headers=["Mcp-Session-Id"],
        max_age=600,
    )
    return app


def main() -> None:
    host = os.environ.get("GXP_LOWCODE_HTTP_HOST", DEFAULT_HOST)
    port = int(os.environ.get("GXP_LOWCODE_HTTP_PORT", str(DEFAULT_PORT)))
    uvicorn.run(create_http_app(host, port), host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
