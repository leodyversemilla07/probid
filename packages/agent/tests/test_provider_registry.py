import unittest

from probid_agent.errors import ProviderRegistryError
from probid_agent.provider_registry import Provider, clear_providers, register_provider, require_provider


def _handler(_input, _runtime):
    return {"intent": "probe", "query": "x", "assumptions": [], "evidence": [], "findings": [], "caveats": [], "next_actions": [], "tool_trace": []}


class ProviderRegistryTests(unittest.TestCase):
    def tearDown(self):
        clear_providers()

    def test_require_provider_raises_typed_error(self):
        with self.assertRaises(ProviderRegistryError):
            require_provider("missing")

    def test_require_provider_returns_registered(self):
        register_provider(Provider(name="deterministic", handle=_handler))
        provider = require_provider("deterministic")
        self.assertEqual(provider.name, "deterministic")


if __name__ == "__main__":
    unittest.main()
