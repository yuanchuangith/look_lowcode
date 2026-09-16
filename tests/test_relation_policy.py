from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

from gxp_core.relation_policy import (
    RelationPolicyStore,
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

    def test_rejection_persists_locally_and_restore_is_idempotent(self) -> None:
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

    def test_local_json_contains_only_opaque_policy_values(self) -> None:
        self.store.reject("shared-dev", self.relation, "wrong_columns")
        content = self.path.read_text(encoding="utf-8")
        self.assertNotIn("orders", content)
        self.assertNotIn("user_id", content)
        payload = json.loads(content)
        decision = payload["decisions"]["shared-dev"][self.relation]
        self.assertEqual("wrong_columns", decision["reason_code"])
        self.assertNotIn("clients", payload)
        self.assertNotIn("token", content.lower())

    async def test_http_policy_endpoints_are_removed(self) -> None:
        app = create_http_app(port=8890)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost:8890") as client:
            for method, path in (
                ("GET", "/relation-policy/v1/health"),
                ("GET", "/relation-policy/v1/scopes/shared-dev"),
                ("PUT", f"/relation-policy/v1/scopes/shared-dev/relations/{self.relation}"),
                ("DELETE", f"/relation-policy/v1/scopes/shared-dev/relations/{self.relation}"),
            ):
                response = await client.request(method, path)
                self.assertEqual(404, response.status_code, (method, path))

    def test_restore_revision_survives_repeated_restore_and_reject(self) -> None:
        self.store.reject("shared-dev", self.relation, "wrong_columns")
        restored = self.store.restore("shared-dev", self.relation)
        self.store.restore("shared-dev", self.relation)
        self.store.reject("shared-dev", self.relation, "wrong_columns")
        snapshot = self.store.snapshot("shared-dev")
        self.assertEqual(restored["revision"], snapshot["restore_revisions"][self.relation])



if __name__ == "__main__":
    unittest.main()
