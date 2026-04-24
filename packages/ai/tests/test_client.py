"""Tests for AI client base classes."""

import os
import unittest
from unittest.mock import patch

from probid_ai.client import getenv_or_raise
from probid_ai.env_api_keys import get_env_api_key
from probid_ai.openai_client import OpenAIClient
from probid_ai.types import ChatCompletionRequest, Message


class AIClientTests(unittest.TestCase):
    def test_getenv_or_raise_raises_when_missing(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError) as ctx:
                getenv_or_raise("MISSING_ENV_VAR")
            self.assertIn("MISSING_ENV_VAR", str(ctx.exception))

    def test_getenv_or_raise_returns_when_present(self):
        with patch.dict(os.environ, {"TEST_KEY": "test-value"}):
            result = getenv_or_raise("TEST_KEY")
            self.assertEqual(result, "test-value")

    def test_openai_client_accepts_api_key_and_base_url(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            client = OpenAIClient()
            self.assertEqual(client.api_key, "sk-test")
            self.assertEqual(client.base_url, "https://api.openai.com/v1")

    def test_openai_client_uses_custom_base_url(self):
        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "sk-test",
                "OPENAI_BASE_URL": "http://localhost:8080/v1",
            },
        ):
            client = OpenAIClient()
            self.assertEqual(client.base_url, "http://localhost:8080/v1")

    def test_openai_client_builds_headers(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            client = OpenAIClient()
            headers = client._headers()
            self.assertIn("Authorization", headers)
            self.assertIn("Bearer", headers["Authorization"])
            self.assertIn("Content-Type", headers)

    def test_get_env_api_key_openai_mapping(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-openai"}, clear=True):
            self.assertEqual(get_env_api_key("openai"), "sk-openai")

    def test_get_env_api_key_anthropic_oauth_takes_precedence(self):
        with patch.dict(
            os.environ,
            {"ANTHROPIC_API_KEY": "sk-ant", "ANTHROPIC_OAUTH_TOKEN": "oauth-ant"},
            clear=True,
        ):
            self.assertEqual(get_env_api_key("anthropic"), "oauth-ant")

    def test_get_env_api_key_github_copilot_fallbacks(self):
        with patch.dict(os.environ, {"GH_TOKEN": "gh-token"}, clear=True):
            self.assertEqual(get_env_api_key("github-copilot"), "gh-token")
        with patch.dict(os.environ, {"GITHUB_TOKEN": "github-token"}, clear=True):
            self.assertEqual(get_env_api_key("github-copilot"), "github-token")

    @patch("probid_ai.env_api_keys.Path.exists", return_value=True)
    def test_get_env_api_key_google_vertex_authenticated_marker(self, _exists):
        with patch.dict(
            os.environ,
            {"GOOGLE_CLOUD_PROJECT": "proj", "GOOGLE_CLOUD_LOCATION": "us-central1"},
            clear=True,
        ):
            self.assertEqual(get_env_api_key("google-vertex"), "<authenticated>")

    def test_get_env_api_key_amazon_bedrock_authenticated_marker(self):
        with patch.dict(os.environ, {"AWS_PROFILE": "default"}, clear=True):
            self.assertEqual(get_env_api_key("amazon-bedrock"), "<authenticated>")


class ChatRequestTests(unittest.TestCase):
    def test_chat_completion_request_defaults(self):
        request = ChatCompletionRequest(
            model="gpt-4",
            messages=[Message(role="user", content="hello")],
        )
        self.assertEqual(request.model, "gpt-4")
        self.assertEqual(request.temperature, 0.7)
        self.assertFalse(request.stream)


if __name__ == "__main__":
    unittest.main()
