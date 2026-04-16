import unittest

from probid_agent.errors import PlanValidationError
from probid_agent.proxy import run_plan_execution, validate_plan_contract


class _Registry:
    def __init__(self):
        self.calls = []

    def execute(self, name, args, cli_equivalent="", event_sink=None):
        self.calls.append((name, args, cli_equivalent))
        return {"ok": True}, {"tool": name, "status": "success"}


class ProxyExecutionTests(unittest.TestCase):
    def test_validate_plan_contract_raises_typed_error(self):
        with self.assertRaises(PlanValidationError):
            validate_plan_contract({"steps": [{"args": {}}]})

    def test_run_plan_execution_returns_structured_result(self):
        registry = _Registry()
        result = run_plan_execution(
            {"steps": [{"tool": "probe", "args": {}, "cli_equivalent": "probid probe \"x\""}]},
            registry,
        )

        self.assertEqual(result["payload"]["ok"], True)
        self.assertEqual(result["tool_trace"][0]["tool"], "probe")
        self.assertEqual(registry.calls[0][0], "probe")


if __name__ == "__main__":
    unittest.main()
