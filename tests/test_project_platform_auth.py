"""Project login diagnostics use fake HTTP responses and synthetic credentials."""
from __future__ import annotations

import base64
import copy
import json
import unittest
from contextlib import nullcontext
from email.message import Message
from types import SimpleNamespace
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs
from unittest.mock import Mock, patch

from gxp_project_context import platform_auth as auth
from gxp_project_context import settings
from gxp_project_context.context import ProjectError


class ProjectPlatformAuthTests(unittest.TestCase):
    def setUp(self):
        self.profile = {"project_id": "a" * 64, "environment": "test",
                        "platform_binding": {"platform_url": "http://fixture.invalid", "account": "fixture-user",
                                             "app_id": "fixture-app", "site_out_id": "fixture-site",
                                             "form_config": {"api_prefix": "/gxp2"}}}
        self.enterContext(patch("gxp_project_context.settings._secure_keyring"))
        self.store = self.enterContext(patch.object(auth.keyring, "set_password"))
        self.enterContext(patch.object(auth.keyring, "get_password", side_effect=AssertionError("No credential reads")))
        self.enterContext(patch("socket.socket.connect", side_effect=AssertionError("No real network")))

    def opener(self, status=200, cookie="token=synthetic-token; HttpOnly"):
        headers = Message()
        if cookie:
            headers.add_header("Set-Cookie", cookie)
        response = SimpleNamespace(status=status, headers=headers)
        return SimpleNamespace(open=Mock(return_value=nullcontext(response)))

    def failure(self, opener, code):
        with self.assertRaises(ProjectError) as caught:
            auth.login_platform(copy.deepcopy(self.profile), "synthetic-password", opener=opener)
        self.assertEqual(code, caught.exception.code)
        self.assertNotIn("synthetic-password", str(caught.exception))
        self.assertNotIn("synthetic-token", str(caught.exception))
        self.assertNotIn("private-exception-text", str(caught.exception))
        return caught.exception

    def test_native_encoding_and_success_return_no_credentials(self):
        opener = self.opener()
        result = auth.login_platform(self.profile, "synthetic-password", opener=opener)
        self.assertEqual({"ok": True, "authenticated": True}, result)
        request = opener.open.call_args.args[0]
        self.assertEqual("http://fixture.invalid/gxp2/api/auth/login", request.full_url)
        values = parse_qs(request.data.decode("ascii"))
        self.assertEqual("o" + base64.b64encode(b"fixture-user").decode(), values["account"][0])
        self.assertEqual("b" + base64.b64encode(b"synthetic-password").decode(), values["password"][0])
        self.store.assert_called_once()

    def test_404_identifies_missing_endpoint_instead_of_invalid_credentials(self):
        opener = self.opener()
        opener.open.side_effect = HTTPError("http://fixture.invalid", 404, "private-exception-text", {}, None)
        error = self.failure(opener, "PROJECT_PLATFORM_ENDPOINT_NOT_FOUND")
        self.assertIn("API 前缀", str(error))
        self.assertEqual({"http_status": 404}, error.details)
        self.store.assert_not_called()

    def test_explicit_login_link_overrides_automatic_endpoint_and_separates_session(self):
        original_key = auth.credential_key(self.profile)
        self.profile["platform_binding"]["login_url"] = "https://fixture.invalid/custom/auth"
        opener = self.opener()
        auth.login_platform(self.profile, "synthetic-password", opener=opener)
        self.assertEqual("https://fixture.invalid/custom/auth", opener.open.call_args.args[0].full_url)
        self.assertNotEqual(original_key, auth.credential_key(self.profile))

    def test_empty_login_link_retains_legacy_endpoint_and_session_key(self):
        original_key = auth.credential_key(self.profile)
        self.profile["platform_binding"]["login_url"] = ""
        self.assertEqual("http://fixture.invalid/gxp2/api/auth/login", auth.login_url(self.profile))
        self.assertEqual(original_key, auth.credential_key(self.profile))

    def test_invalid_login_links_never_send_credentials(self):
        for url in ("file:///fixture", "http://user:password@fixture.invalid/api/auth/login",
                    "http://fixture.invalid/login?password=example", "http://fixture.invalid/login#secret",
                    "http://fixture.invalid/\r\nlogin"):
            with self.subTest(url=url):
                self.profile["platform_binding"]["login_url"] = url
                opener = self.opener()
                self.failure(opener, "PROJECT_PLATFORM_LOGIN_URL_INVALID")
                opener.open.assert_not_called()

    def test_nonraising_http_adapter_also_classifies_status(self):
        error = self.failure(self.opener(status=404), "PROJECT_PLATFORM_ENDPOINT_NOT_FOUND")
        self.assertEqual(404, error.details["http_status"])
        self.store.assert_not_called()

    def test_authentication_rejection_is_reported_separately(self):
        for status in (401, 403):
            with self.subTest(status=status):
                opener = self.opener()
                opener.open.side_effect = HTTPError("http://fixture.invalid", status, "private-exception-text", {}, None)
                error = self.failure(opener, "PROJECT_PLATFORM_AUTH_REJECTED")
                self.assertEqual(status, error.details["http_status"])

    def test_redirect_is_reported_without_following_it(self):
        opener = self.opener()
        opener.open.side_effect = HTTPError("http://fixture.invalid", 302, "private-exception-text", {}, None)
        self.failure(opener, "PROJECT_PLATFORM_REDIRECT")
        opener.open.assert_called_once()

    def test_server_error_does_not_blame_password(self):
        error = self.failure(self.opener(status=503), "PROJECT_PLATFORM_HTTP_ERROR")
        self.assertEqual(503, error.details["http_status"])

    def test_network_error_hides_underlying_exception_text(self):
        opener = self.opener()
        opener.open.side_effect = URLError("private-exception-text")
        self.failure(opener, "PROJECT_PLATFORM_UNREACHABLE")
        self.store.assert_not_called()

    def test_direct_and_wrapped_timeouts_have_same_diagnostic(self):
        for failure in (TimeoutError("private-exception-text"), URLError(TimeoutError("private-exception-text"))):
            with self.subTest(kind=type(failure).__name__):
                opener = self.opener()
                opener.open.side_effect = failure
                self.failure(opener, "PROJECT_PLATFORM_TIMEOUT")

    def test_missing_token_does_not_report_a_successful_login(self):
        error = self.failure(self.opener(cookie=""), "PROJECT_PLATFORM_TOKEN_MISSING")
        self.assertEqual(200, error.details["http_status"])
        self.store.assert_not_called()

    def test_invalid_token_is_not_stored(self):
        self.failure(self.opener(cookie='token="synthetic-token;bad"'), "PROJECT_PLATFORM_AUTH_CONTEXT_INVALID")
        self.store.assert_not_called()

    def test_local_credential_store_failure_is_not_reported_as_login_rejection(self):
        self.store.side_effect = RuntimeError("private-exception-text")
        self.failure(self.opener(), "PROJECT_PLATFORM_CREDENTIAL_SAVE_FAILED")

    def test_invalid_tenant_context_does_not_reach_credential_store(self):
        self.profile["platform_binding"]["form_config"]["company_id"] = "fixture;bad"
        self.failure(self.opener(), "PROJECT_PLATFORM_AUTH_CONTEXT_INVALID")
        self.store.assert_not_called()

    def test_platform_probe_renews_expired_session_once_using_local_password(self):
        self.profile["platform_binding"]["credential_target"] = "synthetic-reference"
        response = SimpleNamespace(read=lambda limit: json.dumps({"data": {"appId": "fixture-app", "siteOutId": "fixture-site"}}).encode())
        opener = SimpleNamespace(open=Mock(side_effect=[
            HTTPError("http://fixture.invalid", 401, "expired", {}, None), nullcontext(response)]))
        with patch.object(auth, "credential", side_effect=["expired-cookie", "fresh-cookie"]), \
             patch.object(auth, "login_platform") as login, \
             patch.object(settings.keyring, "get_password", return_value="synthetic-local-password"), \
             patch("urllib.request.build_opener", return_value=opener):
            result = settings.probe_platform(self.profile)
        self.assertEqual({"status": "ready"}, result)
        login.assert_called_once_with(self.profile, "synthetic-local-password")
        self.assertEqual(2, opener.open.call_count)
        self.assertEqual("fresh-cookie", opener.open.call_args.args[0].headers["Cookie"])

    def test_platform_probe_does_not_loop_when_renewed_session_is_rejected(self):
        self.profile["platform_binding"]["credential_target"] = "synthetic-reference"
        opener = SimpleNamespace(open=Mock(side_effect=HTTPError("http://fixture.invalid", 401, "expired", {}, None)))
        with patch.object(auth, "credential", side_effect=["expired-cookie", "fresh-cookie"]), \
             patch.object(auth, "login_platform") as login, \
             patch.object(settings.keyring, "get_password", return_value="synthetic-local-password"), \
             patch("urllib.request.build_opener", return_value=opener):
            result = settings.probe_platform(self.profile)
        self.assertEqual("platform_session_expired", result["reason"])
        self.assertEqual(401, result["http_status"])
        self.assertEqual(1, login.call_count)
        self.assertEqual(2, opener.open.call_count)


if __name__ == "__main__":
    unittest.main()
