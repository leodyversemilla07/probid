import unittest


class AgentProviderRegistryTests(unittest.TestCase):
    def test_get_provider_returns_registered_provider(self):
        from app.agent.provider_registry import get_provider

        provider = get_provider("deterministic")

        self.assertEqual(provider.name, "deterministic")
        self.assertTrue(callable(provider.handle))

    def test_register_provider_overrides_and_unregister_by_source(self):
        from app.agent.provider_registry import (
            Provider,
            get_provider,
            register_provider,
            unregister_providers,
        )

        def _dummy_handler(user_input, runtime):
            return {
                "intent": "probe",
                "query": user_input,
                "assumptions": [],
                "evidence": [],
                "findings": [],
                "caveats": [],
                "next_actions": [],
                "tool_trace": [],
            }

        register_provider(Provider(name="dummy", handle=_dummy_handler), source_id="tests")
        self.assertIsNotNone(get_provider("dummy"))

        unregister_providers("tests")
        self.assertIsNone(get_provider("dummy"))


if __name__ == "__main__":
    unittest.main()
