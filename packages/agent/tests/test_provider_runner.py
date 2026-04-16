import unittest

from probid_agent.provider_runner import BaseProviderRunner, DeterministicProviderAdapter


class _DummyRuntime:
    def __init__(self):
        self.validated = []

    def _validate_plan(self, plan):
        self.validated.append(plan)

    def _compose_response(self, plan, payload, tool_trace):
        return {
            "intent": plan.get("intent", "unknown"),
            "query": plan.get("query", ""),
            "assumptions": [],
            "evidence": [],
            "findings": [],
            "caveats": [],
            "next_actions": [],
            "tool_trace": tool_trace,
            "payload": payload,
        }


class ProviderRunnerTests(unittest.TestCase):
    def test_base_provider_runner_executes_full_lifecycle(self):
        runtime = _DummyRuntime()
        runner = BaseProviderRunner()

        def _build_plan(user_input: str):
            return {"intent": "probe", "query": user_input, "steps": [{"tool": "probe"}]}

        def _execute_plan(_runtime, plan):
            return {"ok": True, "query": plan["query"]}, [{"tool": "probe", "status": "success"}]

        result = runner.execute(
            user_input="laptop",
            runtime=runtime,
            build_plan=_build_plan,
            execute_plan=_execute_plan,
        )

        self.assertEqual(runtime.validated[0]["query"], "laptop")
        self.assertEqual(result["intent"], "probe")
        self.assertEqual(result["payload"]["ok"], True)
        self.assertEqual(result["tool_trace"][0]["tool"], "probe")

    def test_deterministic_provider_adapter_delegates_to_base_runner(self):
        runtime = _DummyRuntime()

        adapter = DeterministicProviderAdapter(
            build_plan=lambda text: {"intent": "probe", "query": text, "steps": [{"tool": "probe"}]},
            execute_plan=lambda _runtime, plan: ({"query": plan["query"]}, [{"tool": "probe", "status": "success"}]),
        )

        result = adapter.handle("server", runtime)

        self.assertEqual(runtime.validated[0]["query"], "server")
        self.assertEqual(result["query"], "server")


if __name__ == "__main__":
    unittest.main()
