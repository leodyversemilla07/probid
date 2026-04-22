"""Tests for plan execution edge cases."""

import unittest

from probid_agent.errors import PlanValidationError
from probid_agent.proxy import execute_plan_steps, validate_plan_contract


class _FailingRegistry:
    def __init__(self, fail_on: str = ""):
        self.fail_on = fail_on
        self.calls = []

    def execute(self, name, args, cli_equivalent="", event_sink=None):
        self.calls.append((name, args))
        if name == self.fail_on:
            raise RuntimeError(f"Simulated failure: {name}")
        return {"ok": True, "name": name}, {"tool": name, "status": "success"}


class PlanExecutionEdgeCaseTests(unittest.TestCase):
    def test_validate_plan_rejects_empty_steps(self):
        with self.assertRaises(PlanValidationError):
            validate_plan_contract({"steps": []})

    def test_validate_plan_rejects_step_without_cli_equivalent(self):
        with self.assertRaises(PlanValidationError):
            validate_plan_contract({"steps": [{"tool": "probe", "args": {}}]})

    def test_execute_plan_steps_fails_fast_on_single_failure(self):
        registry = _FailingRegistry(fail_on="fail")

        with self.assertRaises(RuntimeError):
            execute_plan_steps(
                {
                    "steps": [
                        {"tool": "probe", "args": {}, "cli_equivalent": "probid probe x"},
                        {"tool": "fail", "args": {}, "cli_equivalent": "probid fail"},
                        {"tool": "search", "args": {}, "cli_equivalent": "probid search y"},
                    ]
                },
                registry,
            )

        self.assertEqual(len(registry.calls), 2)

    def test_execute_plan_steps_returns_payload_from_last_step(self):
        registry = _FailingRegistry()

        payload, trace = execute_plan_steps(
            {
                "steps": [
                    {"tool": "first", "args": {}, "cli_equivalent": "probid first"},
                    {"tool": "second", "args": {}, "cli_equivalent": "probid second"},
                ]
            },
            registry,
        )

        self.assertEqual(payload["name"], "second")
        self.assertEqual(trace[0]["payload"]["name"], "first")
        self.assertEqual(trace[1]["payload"]["name"], "second")


if __name__ == "__main__":
    unittest.main()
