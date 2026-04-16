import tempfile
import unittest
from pathlib import Path

from click.testing import CliRunner

from probid_probing_agent.core.session import AgentSessionLogger
from probid_probing_agent.core.data import cache


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
        from probid_probing_agent.core.planner import plan_for_input

        plan = plan_for_input("probe laptop pricing risk")

        self.assertEqual(plan["intent"], "probe")
        self.assertGreaterEqual(len(plan["steps"]), 1)
        self.assertIn("cli_equivalent", plan["steps"][0])
        self.assertTrue(plan["steps"][0]["cli_equivalent"].startswith("probid probe"))

    def test_runtime_returns_contract_keys(self):
        from probid_probing_agent.core.runtime import ProbidAgentRuntime

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
        self.assertIn("session_id", result)
        self.assertIn("state", result)

        self.assertIsInstance(result["assumptions"], list)
        self.assertIsInstance(result["evidence"], list)
        self.assertIsInstance(result["findings"], list)
        self.assertIsInstance(result["caveats"], list)
        self.assertIsInstance(result["next_actions"], list)
        self.assertIsInstance(result["tool_trace"], list)
        self.assertIn("cli_equivalent", result["tool_trace"][0])
        self.assertEqual(result["tool_trace"][0]["status"], "success")
        self.assertTrue(result["tool_trace"][0]["cli_equivalent"].startswith("probid probe"))

    def test_runtime_exposes_system_prompt(self):
        from probid_probing_agent.core.runtime import ProbidAgentRuntime

        runtime = ProbidAgentRuntime(default_cache_only=True)
        self.assertIn("minimal terminal probing agent harness", runtime.system_prompt)
        self.assertIn("Do not claim corruption guilt", runtime.system_prompt)

    def test_runtime_uses_named_provider_and_returns_provider_in_result(self):
        from probid_probing_agent.core.runtime import ProbidAgentRuntime

        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            self._seed_db(tmp.name)
            runtime = ProbidAgentRuntime(db_path=tmp.name, default_cache_only=True, provider="deterministic")
            result = runtime.handle_input("probe laptop")

        self.assertEqual(runtime.provider_name, "deterministic")
        self.assertEqual(result.get("provider"), "deterministic")

    def test_runtime_rejects_unknown_provider(self):
        from probid_probing_agent.core.runtime import ProbidAgentRuntime

        with self.assertRaises(ValueError):
            ProbidAgentRuntime(default_cache_only=True, provider="not-a-provider")

    def test_cli_without_subcommand_starts_repl(self):
        from probid_probing_agent.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, input="/exit\n")

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Enter query text to run a probe", result.output)

    def test_cli_query_mode_runs_single_turn(self):
        from probid_probing_agent.cli import cli

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
        from probid_probing_agent.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["-q", "probe laptop", "search", "laptop"])

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("Cannot use -q/--query together with a subcommand", result.output)

    def test_cli_invalid_provider_returns_user_friendly_error(self):
        from probid_probing_agent.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["-q", "probe laptop", "--provider", "not-a-provider"])

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("Unknown provider 'not-a-provider'", result.output)

    def test_runtime_rejects_step_without_cli_equivalent(self):
        from probid_probing_agent.core.runtime import ProbidAgentRuntime

        runtime = ProbidAgentRuntime(default_cache_only=True)
        with self.assertRaises(ValueError):
            runtime._validate_plan({"steps": [{"tool": "probe", "args": {"query": "laptop"}}]})

    def test_session_emits_tool_execution_events(self):
        from probid_probing_agent.core.runtime import ProbidAgentRuntime

        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            self._seed_db(tmp.name)
            runtime = ProbidAgentRuntime(db_path=tmp.name, default_cache_only=True)
            events = []
            unsubscribe = runtime.session.subscribe(events.append)
            result = runtime.handle_input("probe laptop")
            unsubscribe()

        event_types = [event.get("type") for event in events]
        self.assertIn("turn_start", event_types)
        self.assertIn("tool_execution_start", event_types)
        self.assertIn("tool_execution_end", event_types)
        self.assertIn("turn_end", event_types)
        self.assertEqual(result["tool_trace"][0]["tool"], "probe")

    def test_runtime_persists_session_turns_and_can_continue_recent(self):
        from probid_probing_agent.core.runtime import ProbidAgentRuntime

        with tempfile.TemporaryDirectory() as td, tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            self._seed_db(tmp.name)
            runtime = ProbidAgentRuntime(
                db_path=tmp.name,
                default_cache_only=True,
                session_dir=td,
            )
            first = runtime.handle_input("probe laptop")

            continued = ProbidAgentRuntime(
                db_path=tmp.name,
                default_cache_only=True,
                session_dir=td,
                continue_recent=True,
            )

        self.assertEqual(continued.session.session_id, first["session_id"])
        self.assertGreaterEqual(len(continued.session.messages), 2)

    def test_new_session_replaces_active_session(self):
        from probid_probing_agent.core.runtime import ProbidAgentRuntime

        with tempfile.TemporaryDirectory() as td:
            runtime = ProbidAgentRuntime(default_cache_only=True, session_dir=td)
            first_id = runtime.session.session_id
            runtime.new_session()

        self.assertNotEqual(runtime.session.session_id, first_id)

    def test_session_queue_state_and_applied_messages(self):
        from probid_probing_agent.core.runtime import ProbidAgentRuntime

        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            self._seed_db(tmp.name)
            runtime = ProbidAgentRuntime(db_path=tmp.name, default_cache_only=True)
            events = []
            unsubscribe = runtime.session.subscribe(events.append)
            runtime.session.steer("focus on DICT")
            runtime.session.follow_up("then suggest next checks")
            before = runtime.session.snapshot_state()
            result = runtime.handle_input("probe laptop")
            after = runtime.session.snapshot_state()
            unsubscribe()

        self.assertEqual(before["queued_steering"], 1)
        self.assertEqual(before["queued_follow_up"], 1)
        self.assertEqual(after["queued_steering"], 0)
        self.assertEqual(after["queued_follow_up"], 0)
        self.assertEqual(result["queue_applied"]["steering"], ["focus on DICT"])
        self.assertEqual(result["queue_applied"]["follow_up"], ["then suggest next checks"])
        self.assertIn("queue_update", [event.get("type") for event in events])

    def test_session_queue_drains_one_item_per_turn(self):
        from probid_probing_agent.core.runtime import ProbidAgentRuntime

        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            self._seed_db(tmp.name)
            runtime = ProbidAgentRuntime(db_path=tmp.name, default_cache_only=True)
            runtime.session.steer("focus on DICT")
            runtime.session.steer("focus on laptops")
            runtime.session.follow_up("then suggest next checks")
            runtime.session.follow_up("then show detail command")
            first = runtime.handle_input("probe laptop")
            mid = runtime.session.snapshot_state()
            second = runtime.handle_input("probe laptop")
            end = runtime.session.snapshot_state()

        self.assertEqual(first["queue_applied"]["steering"], ["focus on DICT"])
        self.assertEqual(first["queue_applied"]["follow_up"], ["then suggest next checks"])
        self.assertEqual(mid["queued_steering"], 1)
        self.assertEqual(mid["queued_follow_up"], 1)
        self.assertEqual(second["queue_applied"]["steering"], ["focus on laptops"])
        self.assertEqual(second["queue_applied"]["follow_up"], ["then show detail command"])
        self.assertEqual(end["queued_steering"], 0)
        self.assertEqual(end["queued_follow_up"], 0)

    def test_session_queue_clear_and_has_helpers(self):
        from probid_probing_agent.core.session import ProbidAgentSession

        session = ProbidAgentSession(system_prompt="test")
        self.assertFalse(session.has_queued_messages())

        session.steer("focus")
        session.follow_up("next")
        self.assertTrue(session.has_queued_messages())

        session.clear_steering_queue()
        self.assertEqual(session.queued_steering, [])
        self.assertEqual(session.queued_follow_up, ["next"])
        self.assertTrue(session.has_queued_messages())

        session.clear_all_queues()
        self.assertEqual(session.queued_steering, [])
        self.assertEqual(session.queued_follow_up, [])
        self.assertFalse(session.has_queued_messages())

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
