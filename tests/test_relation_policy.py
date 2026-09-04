from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
from starlette.applications import Starlette

from gxp_core.relation_policy import (
    RelationPolicyStore,
    add_relation_policy_routes,
)
from http_server import create_http_app


class RelationPolicyTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "relation-policy.json"
        self.store = RelationPolicyStore(self.path)
        self.store.create_scope("shared-dev")
        self.relation = "a" * 64

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_rejection_is_shared_and_restore_is_public(self) -> None:
        first = self.store.reject("shared-dev", self.relation, "user_confirmed_incorrect")
        self.assertEqual([self.relation], [item["relation_id"] for item in self.store.snapshot("shared-dev")["rejections"]])
        second_store = RelationPolicyStore(self.path)
        self.assertEqual([self.relation], [item["relation_id"] for item in second_store.snapshot("shared-dev")["rejections"]])
        repeated = self.store.reject("shared-dev", self.relation, "user_confirmed_incorrect")
        self.assertTrue(repeated["repeated"])
        self.assertEqual(first["revision"], repeated["revision"])
        restored = self.store.restore("shared-dev", self.relation)
        self.assertTrue(restored["changed"])
        self.assertEqual([], self.store.snapshot("shared-dev")["rejections"])

    def test_remote_json_contains_only_opaque_policy_values(self) -> None:
        self.store.reject("shared-dev", self.relation, "wrong_columns")
        content = self.path.read_text(encoding="utf-8")
        self.assertNotIn("orders", content)
        self.assertNotIn("user_id", content)
        payload = json.loads(content)
        decision = payload["decisions"]["shared-dev"][self.relation]
        self.assertEqual("wrong_columns", decision["reason_code"])
        self.assertNotIn("clients", payload)
        self.assertNotIn("token", content.lower())

    async def test_http_is_auth_free_and_keeps_etag_contract(self) -> None:
        app = Starlette()
        add_relation_policy_routes(app, self.store)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="https://policy.test") as client:
            initial = await client.get("/relation-policy/v1/scopes/shared-dev")
            self.assertEqual(200, initial.status_code)
            put = await client.put(
                f"/relation-policy/v1/scopes/shared-dev/relations/{self.relation}",
                json={"reason_code": "user_confirmed_incorrect"},
            )
            self.assertEqual(200, put.status_code)
            fetched = await client.get("/relation-policy/v1/scopes/shared-dev")
            self.assertEqual([self.relation], [item["relation_id"] for item in fetched.json()["rejections"]])
            unchanged = await client.get(
                "/relation-policy/v1/scopes/shared-dev",
                headers={"If-None-Match": fetched.headers["etag"]},
            )
            self.assertEqual(304, unchanged.status_code)
            restored = await client.delete(
                f"/relation-policy/v1/scopes/shared-dev/relations/{self.relation}"
            )
            self.assertEqual(200, restored.status_code)

    async def test_policy_health_starts_without_database_configuration(self) -> None:
        policy_path = Path(self.temp.name) / "standalone.json"
        with patch.dict(os.environ, {
            "GXP_RELATION_POLICY_FILE": str(policy_path),
            "GXP_LOWCODE_CONFIG": str(Path(self.temp.name) / "missing-database.json"),
        }):
            app = create_http_app(port=8890)
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://43.135.137.212:8890"
            ) as client:
                response = await client.get("/relation-policy/v1/health")
        self.assertEqual(200, response.status_code)
        self.assertEqual("json", response.json()["storage"])
        self.assertFalse(response.json()["schema_payload"])


if __name__ == "__main__":
    unittest.main()
