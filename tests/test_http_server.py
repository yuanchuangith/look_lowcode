from __future__ import annotations

import asyncio
import unittest

import httpx

from http_server import create_http_app


class HttpServerCorsTests(unittest.TestCase):
    def test_cors_is_exact_and_exposes_session_header(self) -> None:
        asyncio.run(self._assert_cors())

    async def _assert_cors(self) -> None:
        app = create_http_app(port=8890)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://43.135.137.212:8890",
        ) as client:
            allowed = await client.options(
                "/mcp",
                headers={
                    "Origin": "http://cpm.gxp2.com",
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "content-type,mcp-protocol-version,mcp-session-id",
                },
            )
            self.assertEqual(allowed.status_code, 200)
            self.assertEqual(
                allowed.headers.get("access-control-allow-origin"),
                "http://cpm.gxp2.com",
            )
            self.assertIn(
                "mcp-session-id",
                allowed.headers.get("access-control-allow-headers", "").lower(),
            )

            denied = await client.options(
                "/mcp",
                headers={
                    "Origin": "http://evil.example",
                    "Access-Control-Request-Method": "POST",
                },
            )
            self.assertNotEqual(
                denied.headers.get("access-control-allow-origin"),
                "http://evil.example",
            )


if __name__ == "__main__":
    unittest.main()
