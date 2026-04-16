"""Tests for provider registry overwrite semantics."""

import unittest

from probid_agent.errors import ProviderRegistryError
from probid_agent.provider_registry import (
    Provider,
    clear_providers,
    get_provider,
    register_provider,
    require_provider,
    unregister_providers,
)


def _handler_a(_input, _runtime):
    return {"provider": "a"}


def _handler_b(_input, _runtime):
    return {"provider": "b"}


class ProviderRegistrySemanticsTests(unittest.TestCase):
    def tearDown(self):
        clear_providers()

    def test_register_provider_overwrites_existing_by_name(self):
        p1 = Provider(name="test", handle=_handler_a)
        p2 = Provider(name="test", handle=_handler_b)

        register_provider(p1, source_id="src1")
        register_provider(p2, source_id="src2")

        provider = require_provider("test")
        self.assertEqual(provider.handle(None, None)["provider"], "b")

    def test_unregister_providers_removes_by_source_id(self):
        register_provider(Provider(name="p1", handle=_handler_a), source_id="x")
        register_provider(Provider(name="p2", handle=_handler_b), source_id="y")

        unregister_providers("x")

        self.assertIsNone(get_provider("p1"))
        self.assertIsNotNone(get_provider("p2"))

    def test_require_provider_includes_available_list_in_error(self):
        register_provider(Provider(name="alpha", handle=_handler_a))
        register_provider(Provider(name="beta", handle=_handler_b))

        with self.assertRaises(ProviderRegistryError) as ctx:
            require_provider("missing")

        self.assertIn("alpha", str(ctx.exception))
        self.assertIn("beta", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
