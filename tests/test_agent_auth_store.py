import json
import tempfile
import unittest
from pathlib import Path

from app.agent.auth import AgentAuthStore, normalize_provider_name


class AgentAuthStoreTests(unittest.TestCase):
    def test_login_and_logout_provider(self):
        with tempfile.TemporaryDirectory() as td:
            store = AgentAuthStore(path=Path(td) / "auth.json")

            normalized = store.login("openai", "token-123")
            self.assertEqual(normalized, "openai")
            self.assertEqual(store.list_logged_in_providers(), ["openai"])

            removed, normalized = store.logout("openai")
            self.assertTrue(removed)
            self.assertEqual(normalized, "openai")
            self.assertEqual(store.list_logged_in_providers(), [])

    def test_logout_all(self):
        with tempfile.TemporaryDirectory() as td:
            store = AgentAuthStore(path=Path(td) / "auth.json")
            store.login("openai", "token-1")
            store.login("anthropic", "token-2")

            removed_any, provider_name = store.logout()
            self.assertTrue(removed_any)
            self.assertIsNone(provider_name)
            self.assertEqual(store.list_logged_in_providers(), [])

            data = json.loads((Path(td) / "auth.json").read_text(encoding="utf-8"))
            self.assertEqual(data.get("providers"), {})
    def test_copilot_aliases_normalize_to_github_copilot(self):
        self.assertEqual(normalize_provider_name("copilot"), "github-copilot")
        self.assertEqual(normalize_provider_name("github copilot"), "github-copilot")
        self.assertEqual(normalize_provider_name("github-copilot"), "github-copilot")

        with tempfile.TemporaryDirectory() as td:
            store = AgentAuthStore(path=Path(td) / "auth.json")
            normalized = store.login("copilot", "ghu_token")
            self.assertEqual(normalized, "github-copilot")
            self.assertEqual(store.list_logged_in_providers(), ["github-copilot"])

            removed, normalized = store.logout("github copilot")
            self.assertTrue(removed)
            self.assertEqual(normalized, "github-copilot")
            self.assertEqual(store.list_logged_in_providers(), [])


if __name__ == "__main__":
    unittest.main()
