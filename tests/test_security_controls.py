import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import api_client
import client_settings
import config_manager
import discord_helper


class ConfigManagerSecurityTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.old_config_file = config_manager.CONFIG_FILE
        config_manager.CONFIG_FILE = os.path.join(self.tmpdir.name, "config.json")

    def tearDown(self):
        config_manager.CONFIG_FILE = self.old_config_file
        self.tmpdir.cleanup()

    def test_save_config_never_persists_riot_api_key(self):
        config_manager.save_config({"api_key": "test-secret", "use_stub": True})

        data = json.loads(Path(config_manager.CONFIG_FILE).read_text(encoding="utf-8"))
        self.assertEqual(data["api_key"], "")

    def test_normalize_config_strips_legacy_client_backend_fields(self):
        config = config_manager.normalize_config({
            "api_transport": "proxy",
            "proxy_url": "https://script.google.com/macros/s/example/exec",
            "proxy_auth_token": "operator-token",
            "callback_url": "https://example.com/callback",
        })

        self.assertEqual(config["api_transport"], "supabase")
        self.assertNotIn("proxy_url", config)
        self.assertNotIn("proxy_auth_token", config)
        self.assertNotIn("callback_url", config)

    def test_normalize_config_uses_build_supabase_settings(self):
        with patch.object(client_settings, "SUPABASE_PROJECT_URL", "https://project-ref.supabase.co"), \
             patch.object(client_settings, "SUPABASE_ANON_KEY", "build-anon"):
            config = config_manager.normalize_config({
                "supabase_url": "https://attacker.supabase.co",
                "supabase_anon_key": "attacker-anon",
            })

        self.assertEqual(config["supabase_url"], "https://project-ref.supabase.co")
        self.assertEqual(config["supabase_anon_key"], "build-anon")

    def test_save_config_drops_unknown_secret_like_fields(self):
        config_manager.save_config({
            "api_key": "test-secret",
            "riot_api_key": "test-secret",
            "service_role": "service-secret",
            "supabase_service_role_key": "service-secret",
        })

        data = json.loads(Path(config_manager.CONFIG_FILE).read_text(encoding="utf-8"))
        self.assertEqual(data["api_key"], "")
        self.assertNotIn("riot_api_key", data)
        self.assertNotIn("service_role", data)
        self.assertNotIn("supabase_service_role_key", data)

    def test_production_warnings_require_supabase_auth_settings(self):
        with patch.object(client_settings, "SUPABASE_PROJECT_URL", ""), \
             patch.object(client_settings, "SUPABASE_ANON_KEY", ""):
            config = config_manager.normalize_config({"use_stub": False})

            warnings = config_manager.production_config_warnings(config)

        self.assertTrue(any("Supabase Project URL" in warning for warning in warnings))
        self.assertTrue(any("anon key" in warning for warning in warnings))
        self.assertTrue(any("authentication" in warning for warning in warnings))

    def test_production_warnings_accept_complete_supabase_settings(self):
        with patch.object(client_settings, "SUPABASE_PROJECT_URL", "https://project-ref.supabase.co"), \
             patch.object(client_settings, "SUPABASE_ANON_KEY", "anon-public-key"):
            config = config_manager.normalize_config({
                "use_stub": False,
                "supabase_access_token": "operator-jwt",
                "supabase_client_id": config_manager.get_supabase_client_id(),
            })

            self.assertEqual(config_manager.production_config_warnings(config), [])


class ApiClientSupabaseTests(unittest.TestCase):
    def test_rejects_invalid_routing_value(self):
        with self.assertRaises(ValueError):
            api_client.RiotTournamentClient(platform_routing="kr")

    def test_rejects_desktop_riot_api_key(self):
        with self.assertRaises(ValueError):
            api_client.RiotTournamentClient(api_key="local-secret")

    def test_requires_supabase_configuration_before_network(self):
        client = api_client.RiotTournamentClient(platform_routing="americas")
        result = client.create_tournament(123, "Test")

        self.assertFalse(result["success"])
        self.assertIn("Supabase Project URL", result["error"])

    def test_rejects_invalid_code_request_before_network(self):
        client = api_client.RiotTournamentClient(
            supabase_url="https://project-ref.supabase.co",
            supabase_anon_key="anon",
            supabase_access_token="jwt",
        )
        result = client.create_codes("123", count=0)

        self.assertFalse(result["success"])
        self.assertIn("between 1 and 1000", result["error"])

    def test_provider_creation_does_not_send_client_callback_url(self):
        class FakeResponse:
            status_code = 200
            text = '{"success": true, "data": 123}'
            content = b'{"success": true, "data": 123}'
            headers = {}

            def json(self):
                return {"success": True, "data": 123}

        class FakeSession:
            def __init__(self):
                self.last_url = None
                self.last_json = None
                self.last_headers = None

            def post(self, url, json=None, headers=None, timeout=None):
                self.last_url = url
                self.last_json = json
                self.last_headers = headers
                return FakeResponse()

        client = api_client.RiotTournamentClient(
            use_stub=False,
            platform_routing="americas",
            supabase_url="https://project-ref.supabase.co",
            supabase_anon_key="anon",
            supabase_access_token="jwt",
        )
        fake_session = FakeSession()
        client.session = fake_session

        result = client.create_provider(region="KR")

        self.assertTrue(result["success"])
        self.assertEqual(fake_session.last_url, "https://project-ref.supabase.co/functions/v1/riot-tournament")
        self.assertEqual(fake_session.last_json["action"], "create_provider")
        self.assertEqual(fake_session.last_json["routing_value"], "americas")
        self.assertFalse(fake_session.last_json["use_stub"])
        self.assertEqual(fake_session.last_json["region"], "KR")
        self.assertNotIn("url", fake_session.last_json)
        self.assertEqual(fake_session.last_headers["apikey"], "anon")
        self.assertEqual(fake_session.last_headers["Authorization"], "Bearer jwt")

    def test_supabase_error_body_is_not_treated_as_success(self):
        class FakeResponse:
            status_code = 429
            text = '{"success": false, "error": "rate limit", "status_code": 429, "retry_after": 3}'
            content = text.encode("utf-8")
            headers = {}

            def json(self):
                return {"success": False, "error": "rate limit", "status_code": 429, "retry_after": 3}

        client = api_client.RiotTournamentClient(
            supabase_url="https://project-ref.supabase.co",
            supabase_anon_key="anon",
            supabase_access_token="jwt",
        )
        result = client._normalize_response(FakeResponse())

        self.assertFalse(result["success"])
        self.assertTrue(result["retryable"])
        self.assertEqual(result["retry_after"], 3)

    def test_default_client_does_not_retry_mutating_edge_failures(self):
        class FakeResponse:
            status_code = 503
            text = '{"success": false, "error": "temporary", "status_code": 503}'
            content = text.encode("utf-8")
            headers = {}

            def json(self):
                return {"success": False, "error": "temporary", "status_code": 503}

        class FakeSession:
            def __init__(self):
                self.calls = 0

            def post(self, *args, **kwargs):
                self.calls += 1
                return FakeResponse()

        client = api_client.RiotTournamentClient(
            supabase_url="https://project-ref.supabase.co",
            supabase_anon_key="anon",
            supabase_access_token="jwt",
        )
        fake_session = FakeSession()
        client.session = fake_session

        result = client.create_tournament(123, "Test")

        self.assertFalse(result["success"])
        self.assertTrue(result["retryable"])
        self.assertEqual(fake_session.calls, 1)

    def test_refreshes_supabase_session_after_unauthorized_response(self):
        class FakeEdgeResponse:
            headers = {}
            content = b"{}"

            def __init__(self, status_code, payload):
                self.status_code = status_code
                self.payload = payload
                self.text = json.dumps(payload)

            def json(self):
                return self.payload

        class FakeAuthResponse:
            status_code = 200
            text = '{"access_token": "fresh-jwt", "refresh_token": "fresh-refresh"}'
            content = text.encode("utf-8")

            def json(self):
                return {
                    "access_token": "fresh-jwt",
                    "refresh_token": "fresh-refresh",
                    "user": {"email": "operator@example.com"},
                }

        class FakeSession:
            def __init__(self):
                self.calls = []

            def post(self, url, json=None, headers=None, timeout=None):
                self.calls.append({"url": url, "json": json, "headers": headers})
                if len(self.calls) == 1:
                    return FakeEdgeResponse(401, {"success": False, "error": "invalid jwt", "status_code": 401})
                return FakeEdgeResponse(200, {"success": True, "data": 456})

        refreshed = {}
        client = api_client.RiotTournamentClient(
            supabase_url="https://project-ref.supabase.co",
            supabase_anon_key="anon",
            supabase_access_token="expired-jwt",
            supabase_refresh_token="refresh-token",
            max_retries=0,
            on_session_refresh=lambda session: refreshed.update(session),
        )
        fake_session = FakeSession()
        client.session = fake_session

        with patch("api_client.requests.post", return_value=FakeAuthResponse()):
            result = client.create_tournament(123, "Test")

        self.assertTrue(result["success"])
        self.assertEqual(result["data"], 456)
        self.assertEqual(len(fake_session.calls), 2)
        self.assertEqual(fake_session.calls[0]["headers"]["Authorization"], "Bearer expired-jwt")
        self.assertEqual(fake_session.calls[1]["headers"]["Authorization"], "Bearer fresh-jwt")
        self.assertEqual(client.supabase_refresh_token, "fresh-refresh")
        self.assertEqual(refreshed["user_email"], "operator@example.com")

    def test_marks_rate_limit_failures_as_batch_stoppers(self):
        result = {"success": False, "status_code": 429, "retryable": True}

        self.assertTrue(api_client.should_stop_after_riot_failure(result))

    def test_supabase_sign_in_validates_required_fields_before_network(self):
        result = api_client.supabase_sign_in("https://project-ref.supabase.co", "anon", "", "")

        self.assertFalse(result["success"])
        self.assertIn("email and password", result["error"])


class DiscordWebhookValidationTests(unittest.TestCase):
    def test_rejects_non_discord_webhook_url(self):
        with redirect_stdout(StringIO()):
            self.assertFalse(discord_helper.send_discord_webhook("https://example.com/hook", "Test", "CODE"))


class PresetFileTests(unittest.TestCase):
    def setUp(self):
        import gui_main

        self.gui_main = gui_main
        self.tmpdir = tempfile.TemporaryDirectory()
        self.old_presets_file = gui_main.PRESETS_FILE
        self.old_legacy_presets_file = gui_main.LEGACY_PRESETS_FILE
        gui_main.PRESETS_FILE = os.path.join(self.tmpdir.name, "presets.json")
        gui_main.LEGACY_PRESETS_FILE = os.path.join(self.tmpdir.name, "legacy-presets.json")

    def tearDown(self):
        self.gui_main.PRESETS_FILE = self.old_presets_file
        self.gui_main.LEGACY_PRESETS_FILE = self.old_legacy_presets_file
        self.tmpdir.cleanup()

    def test_save_and_load_preserves_preset_action_fields(self):
        presets = [{
            "label": "내전 1세트",
            "actions": [{
                "name": "1경기",
                "api_name": "Match_1",
                "url": "https://discord.com/api/webhooks/123/token",
            }],
        }]

        self.assertTrue(self.gui_main.save_presets_file(presets))

        loaded = self.gui_main.load_presets_file()
        self.assertEqual(loaded, presets)

    def test_empty_preset_list_can_be_saved_after_deleting_all_presets(self):
        self.assertTrue(self.gui_main.save_presets_file([]))

        data = json.loads(Path(self.gui_main.PRESETS_FILE).read_text(encoding="utf-8"))
        self.assertEqual(data, [])
        self.assertEqual(self.gui_main.load_presets_file(), [])


class ModuleImportSmokeTests(unittest.TestCase):
    def test_gui_and_cli_modules_import(self):
        __import__("gui_main")
        __import__("main")


if __name__ == "__main__":
    unittest.main()
