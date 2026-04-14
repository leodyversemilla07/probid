import tempfile
import unittest
from pathlib import Path

from click.testing import CliRunner

from app.agent.session import AgentSessionLogger
from app.data import cache


class AgentRuntimeContractTests(unittest.TestCase):
    def _seed_db(self, db_path: str) -> None:
        with cache.connection(db_path=db_path) as conn:
            cache.upsert_notice(
                conn,
                {
                    "ref_no": "N-100",
                    "title": "Laptop Procurement Batch 1",
                    "agency": "DICT",
                    "notice_type": "Public Bidding",
                    "category": "IT Equipment",
                    "area_of_delivery": "NCR",
                    "posted_date": "2026-04-01",
                    "closing_date": "2026-04-15",
                    "approved_budget": 60_000_000,
                    "description": "Procurement of laptops",
                    "url": "https://example.local/notices/N-100",
                    "documents": [],
                },
            )
            cache.upsert_award(
                conn,
                {
                    "ref_no": "A-100",
                    "project_title": "Laptop Supply",
                    "agency": "DICT",
                    "supplier": "ACME CORP",
                    "award_amount": 59_000_000,
                    "award_date": "2026-04-20",
                    "approved_budget": 60_000_000,
                    "bid_type": "Public Bidding",
                    "url": "https://example.local/awards/A-100",
                },
            )

    def test_planner_routes_probe_intent(self):
        from app.agent.planner import plan_for_input

        plan = plan_for_input("probe laptop pricing risk")

        self.assertEqual(plan["intent"], "probe")
        self.assertGreaterEqual(len(plan["steps"]), 1)
        self.assertIn("cli_equivalent", plan["steps"][0])
        self.assertTrue(plan["steps"][0]["cli_equivalent"].startswith("probid probe"))

    def test_runtime_returns_contract_keys(self):
        from app.agent.runtime import ProbidAgentRuntime

        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            self._seed_db(tmp.name)
            runtime = ProbidAgentRuntime(db_path=tmp.name, default_cache_only=True)
            result = runtime.handle_input("probe laptop")

        self.assertIn("intent", result)
        self.assertIn("query", result)
        self.assertIn("assumptions", result)
        self.assertIn("evidence", result)
        self.assertIn("findings", result)
        self.assertIn("caveats", result)
        self.assertIn("next_actions", result)
        self.assertIn("tool_trace", result)

        self.assertIsInstance(result["assumptions"], list)
        self.assertIsInstance(result["evidence"], list)
        self.assertIsInstance(result["findings"], list)
        self.assertIsInstance(result["caveats"], list)
        self.assertIsInstance(result["next_actions"], list)
        self.assertIsInstance(result["tool_trace"], list)
        self.assertIn("cli_equivalent", result["tool_trace"][0])
        self.assertTrue(result["tool_trace"][0]["cli_equivalent"].startswith("probid probe"))

    def test_runtime_exposes_system_prompt(self):
        from app.agent.runtime import ProbidAgentRuntime

        runtime = ProbidAgentRuntime(default_cache_only=True)
        self.assertIn("minimal procurement probing agent", runtime.system_prompt)
        self.assertIn("Do not claim corruption guilt", runtime.system_prompt)

    def test_runtime_uses_named_provider_and_returns_provider_in_result(self):
        from app.agent.runtime import ProbidAgentRuntime

        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            self._seed_db(tmp.name)
            runtime = ProbidAgentRuntime(db_path=tmp.name, default_cache_only=True, provider="deterministic")
            result = runtime.handle_input("probe laptop")

        self.assertEqual(runtime.provider_name, "deterministic")
        self.assertEqual(result.get("provider"), "deterministic")

    def test_runtime_rejects_unknown_provider(self):
        from app.agent.runtime import ProbidAgentRuntime

        with self.assertRaises(ValueError):
            ProbidAgentRuntime(default_cache_only=True, provider="not-a-provider")

    def test_cli_without_subcommand_starts_repl(self):
        from app.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, input="/exit\n")

        self.assertEqual(result.exit_code, 0)
        self.assertIn("probid (minimal + agentive)", result.output)

    def test_cli_query_mode_runs_single_turn(self):
        from app.cli import cli

        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            self._seed_db(tmp.name)
            runner = CliRunner()
            result = runner.invoke(
                cli,
                ["-q", "probe laptop", "--db-path", tmp.name, "--json-output"],
            )

        self.assertEqual(result.exit_code, 0)
        self.assertIn('"intent": "probe"', result.output)

    def test_cli_query_mode_rejects_subcommand_combo(self):
        from app.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["-q", "probe laptop", "search", "laptop"])

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("Cannot use -q/--query together with a subcommand", result.output)

    def test_cli_invalid_provider_returns_user_friendly_error(self):
        from app.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["-q", "probe laptop", "--provider", "not-a-provider"])

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("Unknown provider 'not-a-provider'", result.output)

    def test_runtime_rejects_step_without_cli_equivalent(self):
        from app.agent.runtime import ProbidAgentRuntime

        runtime = ProbidAgentRuntime(default_cache_only=True)
        with self.assertRaises(ValueError):
            runtime._validate_plan({"steps": [{"tool": "probe", "args": {"query": "laptop"}}]})

    def test_session_logger_can_retrieve_record_by_turn_id(self):
        with tempfile.NamedTemporaryFile(suffix=".jsonl") as tmp:
            logger = AgentSessionLogger(path=Path(tmp.name))
            turn_id = logger.log_turn(
                "probe laptop",
                {"intent": "probe", "query": "laptop", "tool_trace": [], "findings": []},
            )
            row = logger.get_record(turn_id)

        self.assertIsNotNone(row)
        self.assertEqual(row["turn_id"], turn_id)
        self.assertEqual(row["intent"], "probe")


if __name__ == "__main__":
    unittest.main()
