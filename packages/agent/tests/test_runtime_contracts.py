import unittest

from probid_agent.types import RuntimeStateProtocol, SessionProtocol
from probid_probing_agent.core import providers
from probid_probing_agent.core.runtime import ProbidAgentRuntime
from probid_probing_agent.core.session import ProbidAgentSession


class RuntimeContractsTests(unittest.TestCase):
    def test_probid_session_satisfies_session_protocol(self):
        session = ProbidAgentSession(system_prompt="test")
        self.assertIsInstance(session, SessionProtocol)

    def test_probid_runtime_satisfies_runtime_protocol(self):
        providers.register_builtins()
        runtime = ProbidAgentRuntime(default_cache_only=True)
        self.assertIsInstance(runtime, RuntimeStateProtocol)


if __name__ == "__main__":
    unittest.main()
