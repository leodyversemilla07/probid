import unittest

from probid_ai.api_registry import (
    ApiProvider,
    clear_api_providers,
    get_api_provider,
    get_api_providers,
    register_api_provider,
    unregister_api_providers,
)
from probid_ai.models import (
    calculate_cost,
    get_model,
    get_models,
    get_providers,
    models_are_equal,
    supports_xhigh,
)
from probid_ai.types import Model


def _stream_fn(model, _context, _options=None):
    return {"api": model.api}


class ApiRegistryTests(unittest.TestCase):
    def tearDown(self):
        clear_api_providers()

    def test_register_and_get_api_provider(self):
        provider = ApiProvider(api="openai-responses", stream=_stream_fn, stream_simple=_stream_fn)
        register_api_provider(provider)
        resolved = get_api_provider("openai-responses")
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved.api, "openai-responses")

    def test_wrapped_stream_validates_model_api(self):
        provider = ApiProvider(api="openai-responses", stream=_stream_fn, stream_simple=_stream_fn)
        register_api_provider(provider)
        resolved = get_api_provider("openai-responses")
        with self.assertRaises(ValueError):
            resolved.stream(
                Model(id="x", name="x", api="anthropic-messages", provider="anthropic"),
                {},
            )

    def test_unregister_by_source_id(self):
        register_api_provider(
            ApiProvider(api="openai-responses", stream=_stream_fn, stream_simple=_stream_fn),
            source_id="x",
        )
        register_api_provider(
            ApiProvider(api="anthropic-messages", stream=_stream_fn, stream_simple=_stream_fn),
            source_id="y",
        )
        unregister_api_providers("x")
        self.assertIsNone(get_api_provider("openai-responses"))
        self.assertIsNotNone(get_api_provider("anthropic-messages"))

    def test_get_api_providers_lists_registered_entries(self):
        register_api_provider(ApiProvider(api="openai-responses", stream=_stream_fn, stream_simple=_stream_fn))
        register_api_provider(ApiProvider(api="anthropic-messages", stream=_stream_fn, stream_simple=_stream_fn))
        apis = sorted(p.api for p in get_api_providers())
        self.assertEqual(apis, ["anthropic-messages", "openai-responses"])


class ModelRegistryTests(unittest.TestCase):
    def test_get_model_returns_known_model(self):
        model = get_model("openai-codex", "gpt-5.4")
        self.assertIsNotNone(model)
        self.assertEqual(model.id, "gpt-5.4")

    def test_get_providers_and_models(self):
        providers = get_providers()
        self.assertIn("openai-codex", providers)
        models = get_models("anthropic")
        self.assertGreaterEqual(len(models), 1)

    def test_calculate_cost_updates_usage(self):
        model = get_model("openai-codex", "gpt-5.3-codex")
        usage = {"input": 1000, "output": 500, "cacheRead": 0, "cacheWrite": 0}
        cost = calculate_cost(model, usage)
        self.assertIn("total", cost)
        self.assertGreater(cost["total"], 0)
        self.assertIn("cost", usage)

    def test_supports_xhigh(self):
        self.assertTrue(supports_xhigh(get_model("openai-codex", "gpt-5.4")))
        self.assertTrue(supports_xhigh(get_model("openrouter", "anthropic/claude-opus-4.6")))
        self.assertFalse(supports_xhigh(get_model("anthropic", "claude-sonnet-4-5")))

    def test_models_are_equal(self):
        a = get_model("openai-codex", "gpt-5.4")
        b = get_model("openai-codex", "gpt-5.4")
        c = get_model("anthropic", "claude-sonnet-4-5")
        self.assertTrue(models_are_equal(a, b))
        self.assertFalse(models_are_equal(a, c))
        self.assertFalse(models_are_equal(a, None))


if __name__ == "__main__":
    unittest.main()
