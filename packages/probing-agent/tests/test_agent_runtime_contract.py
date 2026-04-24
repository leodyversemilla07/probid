import json
import tempfile
import unittest
from pathlib import Path

from click.testing import CliRunner

from probid_probing_agent.core.data import cache
from probid_probing_agent.core.session import AgentSessionLogger


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

    def test_planner_builds_multi_step_probe_for_agency_awards_prompt(self):
        from probid_probing_agent.core.planner import plan_for_input

        plan = plan_for_input("probe laptop awards in DICT for suspicious patterns")

        self.assertEqual(plan["intent"], "probe")
        self.assertEqual(len(plan["steps"]), 2)
        self.assertEqual(plan["steps"][0]["tool"], "awards")
        self.assertEqual(plan["steps"][0]["args"]["agency"], "DICT")
        self.assertEqual(plan["steps"][1]["tool"], "probe")
        self.assertEqual(plan["steps"][1]["args"]["agency"], "DICT")
        self.assertTrue(plan["steps"][1]["cli_equivalent"].startswith("probid probe"))

    def test_planner_builds_supplier_investigation_steps(self):
        from probid_probing_agent.core.planner import plan_for_input

        plan = plan_for_input('check supplier "ACME CORP" for network concentration')

        self.assertEqual(plan["intent"], "supplier")
        self.assertEqual([step["tool"] for step in plan["steps"]], ["supplier", "network", "repeat"])
        self.assertEqual(plan["steps"][0]["args"]["name"], "ACME CORP")
        self.assertEqual(plan["steps"][1]["args"]["supplier_name"], "ACME CORP")

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

    def test_cli_query_mode_can_export_recent_json_content_only(self):
        from probid_probing_agent.cli import cli

        with (
            tempfile.TemporaryDirectory() as td,
            tempfile.NamedTemporaryFile(suffix=".db") as tmp,
        ):
            self._seed_db(tmp.name)
            runner = CliRunner()
            first = runner.invoke(
                cli,
                [
                    "-q",
                    "probe laptop awards",
                    "--db-path",
                    tmp.name,
                    "--session-dir",
                    td,
                    "--json-output",
                ],
            )
            second = runner.invoke(
                cli,
                [
                    "-q",
                    "turn this into json",
                    "--db-path",
                    tmp.name,
                    "--session-dir",
                    td,
                    "--continue-recent",
                    "--export-output",
                    "--json-output",
                ],
            )

        self.assertEqual(first.exit_code, 0)
        self.assertEqual(second.exit_code, 0)
        self.assertIn('"top_finding"', second.output)
        self.assertNotIn('"intent": "explain"', second.output)

    def test_cli_query_mode_can_export_recent_markdown_content_only(self):
        from probid_probing_agent.cli import cli

        with (
            tempfile.TemporaryDirectory() as td,
            tempfile.NamedTemporaryFile(suffix=".db") as tmp,
        ):
            self._seed_db(tmp.name)
            runner = CliRunner()
            runner.invoke(
                cli,
                [
                    "-q",
                    "probe laptop awards",
                    "--db-path",
                    tmp.name,
                    "--session-dir",
                    td,
                    "--json-output",
                ],
            )
            result = runner.invoke(
                cli,
                [
                    "-q",
                    "make this a markdown report",
                    "--db-path",
                    tmp.name,
                    "--session-dir",
                    td,
                    "--continue-recent",
                    "--export-output",
                ],
            )

        self.assertEqual(result.exit_code, 0)
        self.assertIn("# Procurement Probe Report:", result.output)
        self.assertNotIn("'intent': 'explain'", result.output)

    def test_cli_query_mode_can_write_export_to_file(self):
        from probid_probing_agent.cli import cli

        with (
            tempfile.TemporaryDirectory() as td,
            tempfile.NamedTemporaryFile(suffix=".db") as tmp,
            tempfile.NamedTemporaryFile(suffix=".md", delete=False) as out,
        ):
            out_path = out.name
            self._seed_db(tmp.name)
            runner = CliRunner()
            runner.invoke(
                cli,
                [
                    "-q",
                    "probe laptop awards",
                    "--db-path",
                    tmp.name,
                    "--session-dir",
                    td,
                    "--json-output",
                ],
            )
            result = runner.invoke(
                cli,
                [
                    "-q",
                    "make this a markdown report",
                    "--db-path",
                    tmp.name,
                    "--session-dir",
                    td,
                    "--continue-recent",
                    "--export-output",
                    "--output",
                    out_path,
                ],
            )

        self.assertEqual(result.exit_code, 0)
        self.assertIn(f"Written to {out_path}", result.output)
        content = Path(out_path).read_text()
        self.assertIn("# Procurement Probe Report:", content)

    def test_cli_query_mode_infers_json_when_export_written_to_json_file(self):
        from probid_probing_agent.cli import cli

        with (
            tempfile.TemporaryDirectory() as td,
            tempfile.NamedTemporaryFile(suffix=".db") as tmp,
            tempfile.NamedTemporaryFile(suffix=".json", delete=False) as out,
        ):
            out_path = out.name
            self._seed_db(tmp.name)
            runner = CliRunner()
            runner.invoke(
                cli,
                [
                    "-q",
                    "probe laptop awards",
                    "--db-path",
                    tmp.name,
                    "--session-dir",
                    td,
                    "--json-output",
                ],
            )
            result = runner.invoke(
                cli,
                [
                    "-q",
                    "turn this into json",
                    "--db-path",
                    tmp.name,
                    "--session-dir",
                    td,
                    "--continue-recent",
                    "--export-output",
                    "--output",
                    out_path,
                ],
            )

        self.assertEqual(result.exit_code, 0)
        content = Path(out_path).read_text()
        self.assertIn('"top_finding"', content)
        self.assertNotIn('"intent": "explain"', content)

    def test_cli_query_mode_can_write_csv_export_to_csv_file(self):
        from probid_probing_agent.cli import cli

        with (
            tempfile.TemporaryDirectory() as td,
            tempfile.NamedTemporaryFile(suffix=".db") as tmp,
            tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as out,
        ):
            out_path = out.name
            self._seed_db(tmp.name)
            runner = CliRunner()
            runner.invoke(
                cli,
                [
                    "-q",
                    "probe laptop awards",
                    "--db-path",
                    tmp.name,
                    "--session-dir",
                    td,
                    "--json-output",
                ],
            )
            result = runner.invoke(
                cli,
                [
                    "-q",
                    "export a csv summary",
                    "--db-path",
                    tmp.name,
                    "--session-dir",
                    td,
                    "--continue-recent",
                    "--export-output",
                    "--output",
                    out_path,
                ],
            )

        self.assertEqual(result.exit_code, 0)
        content = Path(out_path).read_text()
        self.assertIn("section,detail", content)
        self.assertIn("top_finding,", content)

    def test_cli_export_writes_artifact_metadata_to_session_log(self):
        from probid_probing_agent.cli import cli
        from probid_probing_agent.core.session_manager import ProbidSessionManager

        with (
            tempfile.TemporaryDirectory() as td,
            tempfile.NamedTemporaryFile(suffix=".db") as tmp,
            tempfile.NamedTemporaryFile(suffix=".json", delete=False) as out,
        ):
            out_path = out.name
            self._seed_db(tmp.name)
            runner = CliRunner()
            runner.invoke(
                cli,
                [
                    "-q",
                    "probe laptop awards",
                    "--db-path",
                    tmp.name,
                    "--session-dir",
                    td,
                    "--json-output",
                ],
            )
            result = runner.invoke(
                cli,
                [
                    "-q",
                    "turn this into json",
                    "--db-path",
                    tmp.name,
                    "--session-dir",
                    td,
                    "--continue-recent",
                    "--export-output",
                    "--output",
                    out_path,
                ],
            )
            manager = ProbidSessionManager(Path(td))
            recent = manager.continue_recent()
            self.assertIsNotNone(recent)
            session_id, _path = recent
            rows = manager.read_session(session_id)

        self.assertEqual(result.exit_code, 0)
        artifact_rows = [row for row in rows if row.get("type") == "export_artifact"]
        self.assertTrue(artifact_rows)
        artifact = artifact_rows[-1]
        self.assertEqual(artifact["export_format"], "json")
        self.assertEqual(artifact["output_path"], out_path)
        self.assertEqual(artifact["destination"], "file")
        self.assertTrue(artifact["content_sha256"])
        self.assertTrue(artifact["origin_turn_id"])

    def test_cli_query_mode_rejects_mismatched_reexport_alias_without_export_content(
        self,
    ):
        from probid_probing_agent.cli import cli

        with (
            tempfile.TemporaryDirectory() as td,
            tempfile.NamedTemporaryFile(suffix=".db") as tmp,
            tempfile.NamedTemporaryFile(suffix=".json", delete=False) as out,
        ):
            self._seed_db(tmp.name)
            runner = CliRunner()
            runner.invoke(
                cli,
                [
                    "-q",
                    "probe laptop awards",
                    "--db-path",
                    tmp.name,
                    "--session-dir",
                    td,
                    "--json-output",
                ],
            )
            runner.invoke(
                cli,
                [
                    "-q",
                    "make this a markdown report",
                    "--db-path",
                    tmp.name,
                    "--session-dir",
                    td,
                    "--continue-recent",
                    "--export-output",
                    "--output",
                    out.name.replace(".json", ".md"),
                ],
            )
            result = runner.invoke(
                cli,
                [
                    "-q",
                    "re-export the last json export",
                    "--db-path",
                    tmp.name,
                    "--session-dir",
                    td,
                    "--continue-recent",
                    "--export-output",
                    "--output",
                    out.name,
                ],
            )

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn(
            "Query did not produce export content. Run an export-oriented follow-up first.",
            result.output,
        )

    def test_cli_query_mode_can_reexport_last_markdown_report_to_new_file(self):
        from probid_probing_agent.cli import cli

        with (
            tempfile.TemporaryDirectory() as td,
            tempfile.NamedTemporaryFile(suffix=".db") as tmp,
            tempfile.NamedTemporaryFile(suffix=".md", delete=False) as first_out,
            tempfile.NamedTemporaryFile(suffix=".md", delete=False) as second_out,
        ):
            self._seed_db(tmp.name)
            runner = CliRunner()
            runner.invoke(
                cli,
                [
                    "-q",
                    "probe laptop awards",
                    "--db-path",
                    tmp.name,
                    "--session-dir",
                    td,
                    "--json-output",
                ],
            )
            first = runner.invoke(
                cli,
                [
                    "-q",
                    "make this a markdown report",
                    "--db-path",
                    tmp.name,
                    "--session-dir",
                    td,
                    "--continue-recent",
                    "--export-output",
                    "--output",
                    first_out.name,
                ],
            )
            second = runner.invoke(
                cli,
                [
                    "-q",
                    "re-export the last markdown report",
                    "--db-path",
                    tmp.name,
                    "--session-dir",
                    td,
                    "--continue-recent",
                    "--export-output",
                    "--output",
                    second_out.name,
                ],
            )

        self.assertEqual(first.exit_code, 0)
        self.assertEqual(second.exit_code, 0)
        self.assertEqual(Path(first_out.name).read_text(), Path(second_out.name).read_text())

    def test_cli_query_mode_can_reexport_last_artifact_to_new_file(self):
        from probid_probing_agent.cli import cli

        with (
            tempfile.TemporaryDirectory() as td,
            tempfile.NamedTemporaryFile(suffix=".db") as tmp,
            tempfile.NamedTemporaryFile(suffix=".json", delete=False) as first_out,
            tempfile.NamedTemporaryFile(suffix=".json", delete=False) as second_out,
        ):
            self._seed_db(tmp.name)
            runner = CliRunner()
            runner.invoke(
                cli,
                [
                    "-q",
                    "probe laptop awards",
                    "--db-path",
                    tmp.name,
                    "--session-dir",
                    td,
                    "--json-output",
                ],
            )
            first = runner.invoke(
                cli,
                [
                    "-q",
                    "turn this into json",
                    "--db-path",
                    tmp.name,
                    "--session-dir",
                    td,
                    "--continue-recent",
                    "--export-output",
                    "--output",
                    first_out.name,
                ],
            )
            second = runner.invoke(
                cli,
                [
                    "-q",
                    "re-export the last artifact",
                    "--db-path",
                    tmp.name,
                    "--session-dir",
                    td,
                    "--continue-recent",
                    "--export-output",
                    "--output",
                    second_out.name,
                ],
            )

        self.assertEqual(first.exit_code, 0)
        self.assertEqual(second.exit_code, 0)
        self.assertEqual(Path(first_out.name).read_text(), Path(second_out.name).read_text())

    def test_cli_exports_command_can_render_json_rows(self):
        from probid_probing_agent.cli import cli

        with (
            tempfile.TemporaryDirectory() as td,
            tempfile.NamedTemporaryFile(suffix=".db") as tmp,
            tempfile.NamedTemporaryFile(suffix=".json", delete=False) as out,
        ):
            self._seed_db(tmp.name)
            runner = CliRunner()
            runner.invoke(
                cli,
                [
                    "-q",
                    "probe laptop awards",
                    "--db-path",
                    tmp.name,
                    "--session-dir",
                    td,
                    "--json-output",
                ],
            )
            runner.invoke(
                cli,
                [
                    "-q",
                    "turn this into json",
                    "--db-path",
                    tmp.name,
                    "--session-dir",
                    td,
                    "--continue-recent",
                    "--export-output",
                    "--output",
                    out.name,
                ],
            )
            result = runner.invoke(cli, ["exports", "--session-dir", td, "--json"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn('"exports"', result.output)
        self.assertIn('"export_format": "json"', result.output)
        self.assertIn(out.name, result.output)

    def test_cli_exports_command_accepts_session_id_prefix(self):
        from probid_probing_agent.cli import cli
        from probid_probing_agent.core.session_manager import ProbidSessionManager

        with tempfile.TemporaryDirectory() as td:
            manager = ProbidSessionManager(Path(td))
            session_id, _path = manager.create_session()
            manager.append_turn(
                session_id,
                {
                    "type": "export_artifact",
                    "export_format": "json",
                    "query": "laptop",
                    "output_path": "/tmp/export.json",
                    "destination": "file",
                },
            )
            runner = CliRunner()
            result = runner.invoke(cli, ["exports", "--session-dir", td, "--session-id", session_id[:8]])

        self.assertEqual(result.exit_code, 0)
        self.assertIn(session_id, result.output)
        self.assertIn("json: /tmp/export.json", result.output)

    def test_cli_query_mode_rejects_markdown_export_to_json_file(self):
        from probid_probing_agent.cli import cli

        with (
            tempfile.TemporaryDirectory() as td,
            tempfile.NamedTemporaryFile(suffix=".db") as tmp,
            tempfile.NamedTemporaryFile(suffix=".json", delete=False) as out,
        ):
            self._seed_db(tmp.name)
            runner = CliRunner()
            runner.invoke(
                cli,
                [
                    "-q",
                    "probe laptop awards",
                    "--db-path",
                    tmp.name,
                    "--session-dir",
                    td,
                    "--json-output",
                ],
            )
            result = runner.invoke(
                cli,
                [
                    "-q",
                    "make this a markdown report",
                    "--db-path",
                    tmp.name,
                    "--session-dir",
                    td,
                    "--continue-recent",
                    "--export-output",
                    "--output",
                    out.name,
                ],
            )

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn(
            "Text export should be written to .md, .csv, or stdout, not .json.",
            result.output,
        )

    def test_cli_query_mode_rejects_structured_export_to_markdown_file(self):
        from probid_probing_agent.cli import cli

        with (
            tempfile.TemporaryDirectory() as td,
            tempfile.NamedTemporaryFile(suffix=".db") as tmp,
            tempfile.NamedTemporaryFile(suffix=".md", delete=False) as out,
        ):
            self._seed_db(tmp.name)
            runner = CliRunner()
            runner.invoke(
                cli,
                [
                    "-q",
                    "probe laptop awards",
                    "--db-path",
                    tmp.name,
                    "--session-dir",
                    td,
                    "--json-output",
                ],
            )
            result = runner.invoke(
                cli,
                [
                    "-q",
                    "turn this into json",
                    "--db-path",
                    tmp.name,
                    "--session-dir",
                    td,
                    "--continue-recent",
                    "--export-output",
                    "--output",
                    out.name,
                ],
            )

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn(
            "Structured export should be written to .json, and CSV export should be written to .csv.",
            result.output,
        )

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

        with (
            tempfile.TemporaryDirectory() as td,
            tempfile.NamedTemporaryFile(suffix=".db") as tmp,
        ):
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

    def test_continued_session_restores_structured_memory_for_explanatory_followups(
        self,
    ):
        from probid_probing_agent.core.runtime import ProbidAgentRuntime

        with (
            tempfile.TemporaryDirectory() as td,
            tempfile.NamedTemporaryFile(suffix=".db") as tmp,
        ):
            self._seed_db(tmp.name)
            runtime = ProbidAgentRuntime(
                db_path=tmp.name,
                default_cache_only=True,
                session_dir=td,
            )
            first = runtime.handle_input("probe laptop awards")

            continued = ProbidAgentRuntime(
                db_path=tmp.name,
                default_cache_only=True,
                session_dir=td,
                continue_recent=True,
            )
            result = continued.handle_input("explain the top finding")

        self.assertEqual(continued.session.session_id, first["session_id"])
        self.assertEqual(result["intent"], "explain")
        self.assertEqual(result["tool_trace"], [])
        self.assertTrue(result["findings"])
        self.assertEqual(result["investigation_context"].get("query"), "laptop")
        self.assertTrue(result["investigation_context"].get("top_finding_summary"))

    def test_continued_session_restores_export_metadata_for_followups(self):
        from probid_probing_agent.core.runtime import ProbidAgentRuntime

        with (
            tempfile.TemporaryDirectory() as td,
            tempfile.NamedTemporaryFile(suffix=".db") as tmp,
        ):
            self._seed_db(tmp.name)
            runtime = ProbidAgentRuntime(
                db_path=tmp.name,
                default_cache_only=True,
                session_dir=td,
            )
            runtime.handle_input("probe laptop awards")
            export_result = runtime.handle_input("turn this into json")
            runtime.record_export_artifact(
                result=export_result,
                output_text=json.dumps(export_result["export"]["content"]),
                output_path="/tmp/probid-export.json",
            )

            continued = ProbidAgentRuntime(
                db_path=tmp.name,
                default_cache_only=True,
                session_dir=td,
                continue_recent=True,
            )
            result = continued.handle_input("show last export destination")

        self.assertEqual(result["intent"], "explain")
        self.assertEqual(result["tool_trace"], [])
        self.assertIn("/tmp/probid-export.json", result["findings"][0]["summary"])
        self.assertEqual(continued.session.investigation_context.get("last_export_format"), "json")
        self.assertEqual(
            continued.session.investigation_context.get("last_export_path"),
            "/tmp/probid-export.json",
        )

    def test_session_followup_mismatched_reexport_alias_returns_no_export(self):
        from probid_probing_agent.core.runtime import ProbidAgentRuntime

        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            self._seed_db(tmp.name)
            runtime = ProbidAgentRuntime(db_path=tmp.name, default_cache_only=True)
            runtime.handle_input("probe laptop awards")
            runtime.handle_input("make this a markdown report")
            result = runtime.handle_input("re-export the last json export")

        self.assertNotIn("export", result)
        self.assertNotEqual(result.get("intent"), "explain")

    def test_session_followup_reexports_last_markdown_report_from_session_log(self):
        from probid_probing_agent.core.runtime import ProbidAgentRuntime

        with (
            tempfile.TemporaryDirectory() as td,
            tempfile.NamedTemporaryFile(suffix=".db") as tmp,
        ):
            self._seed_db(tmp.name)
            runtime = ProbidAgentRuntime(
                db_path=tmp.name,
                default_cache_only=True,
                session_dir=td,
            )
            runtime.handle_input("probe laptop awards")
            export_result = runtime.handle_input("make this a markdown report")
            runtime.record_export_artifact(
                result=export_result,
                output_text=export_result["export"]["content"],
                output_path="/tmp/probid-report.md",
            )

            continued = ProbidAgentRuntime(
                db_path=tmp.name,
                default_cache_only=True,
                session_dir=td,
                continue_recent=True,
            )
            result = continued.handle_input("re-export the last markdown report")

        self.assertEqual(result["intent"], "explain")
        self.assertEqual(result["tool_trace"], [])
        self.assertEqual(result["export"]["format"], "markdown")
        self.assertIn("# Procurement Probe Report:", result["export"]["content"])

    def test_session_followup_reexports_last_artifact_from_session_log(self):
        from probid_probing_agent.core.runtime import ProbidAgentRuntime

        with (
            tempfile.TemporaryDirectory() as td,
            tempfile.NamedTemporaryFile(suffix=".db") as tmp,
        ):
            self._seed_db(tmp.name)
            runtime = ProbidAgentRuntime(
                db_path=tmp.name,
                default_cache_only=True,
                session_dir=td,
            )
            runtime.handle_input("probe laptop awards")
            export_result = runtime.handle_input("turn this into json")
            runtime.record_export_artifact(
                result=export_result,
                output_text=json.dumps(export_result["export"]["content"]),
                output_path="/tmp/probid-export.json",
            )

            continued = ProbidAgentRuntime(
                db_path=tmp.name,
                default_cache_only=True,
                session_dir=td,
                continue_recent=True,
            )
            result = continued.handle_input("re-export the last artifact")

        self.assertEqual(result["intent"], "explain")
        self.assertEqual(result["tool_trace"], [])
        self.assertEqual(result["export"]["format"], "json")
        self.assertIn("top_finding", result["export"]["content"])

    def test_session_followup_lists_prior_exports(self):
        from probid_probing_agent.core.runtime import ProbidAgentRuntime

        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            self._seed_db(tmp.name)
            runtime = ProbidAgentRuntime(db_path=tmp.name, default_cache_only=True)
            runtime.handle_input("probe laptop awards")

            export_json = runtime.handle_input("turn this into json")
            runtime.record_export_artifact(
                result=export_json,
                output_text=json.dumps(export_json["export"]["content"]),
                output_path="/tmp/probid-export.json",
            )

            export_md = runtime.handle_input("make this a markdown report")
            runtime.record_export_artifact(
                result=export_md,
                output_text=export_md["export"]["content"],
                output_path="/tmp/probid-report.md",
            )

            result = runtime.handle_input("list prior exports")

        self.assertEqual(result["intent"], "explain")
        self.assertEqual(result["tool_trace"], [])
        summaries = [item["summary"] for item in result["findings"]]
        self.assertTrue(any("json:/tmp/probid-export.json" in summary for summary in summaries))
        self.assertTrue(any("markdown:/tmp/probid-report.md" in summary for summary in summaries))

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

    def test_session_memory_carries_agency_context_across_turns(self):
        from probid_probing_agent.core.runtime import ProbidAgentRuntime

        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            self._seed_db(tmp.name)
            runtime = ProbidAgentRuntime(db_path=tmp.name, default_cache_only=True)
            first = runtime.handle_input("probe laptop in DICT")
            second = runtime.handle_input("show awards")

        self.assertEqual(first["investigation_context"]["agency"], "DICT")
        self.assertEqual(first["investigation_context"]["query"], "laptop")
        self.assertEqual(second["intent"], "awards")
        self.assertIn('--agency "DICT"', second["tool_trace"][0]["cli_equivalent"])
        self.assertEqual(second["investigation_context"]["agency"], "DICT")

    def test_session_steering_updates_structured_context(self):
        from probid_probing_agent.core.runtime import ProbidAgentRuntime

        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            self._seed_db(tmp.name)
            runtime = ProbidAgentRuntime(db_path=tmp.name, default_cache_only=True)
            runtime.session.steer("focus on DICT")
            result = runtime.handle_input("show awards")

        self.assertEqual(result["intent"], "awards")
        self.assertIn('--agency "DICT"', result["tool_trace"][0]["cli_equivalent"])
        self.assertEqual(result["investigation_context"]["agency"], "DICT")

    def test_session_followup_why_reuses_probe_context(self):
        from probid_probing_agent.core.runtime import ProbidAgentRuntime

        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            self._seed_db(tmp.name)
            runtime = ProbidAgentRuntime(db_path=tmp.name, default_cache_only=True)
            runtime.handle_input("probe laptop in DICT")
            result = runtime.handle_input("why?")

        self.assertEqual(result["intent"], "probe")
        self.assertIn('--agency "DICT"', result["tool_trace"][0]["cli_equivalent"])
        self.assertIn('"laptop"', result["tool_trace"][0]["cli_equivalent"])

    def test_session_followup_high_confidence_uses_context(self):
        from probid_probing_agent.core.runtime import ProbidAgentRuntime

        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            self._seed_db(tmp.name)
            runtime = ProbidAgentRuntime(db_path=tmp.name, default_cache_only=True)
            runtime.handle_input("probe laptop in DICT")
            result = runtime.handle_input("show only high confidence")

        self.assertEqual(result["intent"], "probe")
        self.assertIn("--min-confidence high", result["tool_trace"][0]["cli_equivalent"])
        self.assertIn('--agency "DICT"', result["tool_trace"][0]["cli_equivalent"])

    def test_session_followup_detail_first_ref_uses_previous_probe(self):
        from probid_probing_agent.core.runtime import ProbidAgentRuntime

        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            self._seed_db(tmp.name)
            runtime = ProbidAgentRuntime(db_path=tmp.name, default_cache_only=True)
            runtime.handle_input("probe laptop awards")
            result = runtime.handle_input("detail the first ref")

        self.assertEqual(result["intent"], "detail")
        self.assertTrue(result["tool_trace"][0]["cli_equivalent"].startswith("probid detail A-100"))

    def test_session_followup_supplier_behind_that_uses_previous_probe(self):
        from probid_probing_agent.core.runtime import ProbidAgentRuntime

        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            self._seed_db(tmp.name)
            runtime = ProbidAgentRuntime(db_path=tmp.name, default_cache_only=True)
            runtime.handle_input("probe laptop awards")
            result = runtime.handle_input("check the supplier behind that")

        self.assertEqual(result["intent"], "supplier")
        self.assertIn('probid supplier "ACME CORP"', result["tool_trace"][0]["cli_equivalent"])

    def test_session_followup_second_supplier_uses_ranked_candidates(self):
        from probid_probing_agent.core.runtime import ProbidAgentRuntime

        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            self._seed_db(tmp.name)
            with cache.connection(db_path=tmp.name) as conn:
                cache.upsert_award(
                    conn,
                    {
                        "ref_no": "A-101",
                        "project_title": "Laptop Supply 2",
                        "agency": "DICT",
                        "supplier": "BYTEWORKS INC",
                        "award_amount": 58000000,
                        "award_date": "2026-04-19",
                        "approved_budget": 60000000,
                        "bid_type": "Public Bidding",
                        "url": "https://example.local/awards/A-101",
                    },
                )
            runtime = ProbidAgentRuntime(db_path=tmp.name, default_cache_only=True)
            runtime.handle_input("probe laptop awards")
            result = runtime.handle_input("show the second supplier")

        self.assertEqual(result["intent"], "supplier")
        self.assertIn('probid supplier "BYTEWORKS INC"', result["tool_trace"][0]["cli_equivalent"])

    def test_session_followup_most_recent_award_uses_ranked_refs(self):
        from probid_probing_agent.core.runtime import ProbidAgentRuntime

        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            self._seed_db(tmp.name)
            with cache.connection(db_path=tmp.name) as conn:
                cache.upsert_award(
                    conn,
                    {
                        "ref_no": "A-101",
                        "project_title": "Laptop Supply 2",
                        "agency": "DICT",
                        "supplier": "BYTEWORKS INC",
                        "award_amount": 58000000,
                        "award_date": "2026-04-21",
                        "approved_budget": 60000000,
                        "bid_type": "Public Bidding",
                        "url": "https://example.local/awards/A-101",
                    },
                )
            runtime = ProbidAgentRuntime(db_path=tmp.name, default_cache_only=True)
            runtime.handle_input("probe laptop awards")
            result = runtime.handle_input("open the most recent award")

        self.assertEqual(result["intent"], "detail")
        self.assertTrue(result["tool_trace"][0]["cli_equivalent"].startswith("probid detail A-101"))

    def test_session_followup_drill_into_top_finding_uses_top_ref(self):
        from probid_probing_agent.core.runtime import ProbidAgentRuntime

        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            self._seed_db(tmp.name)
            runtime = ProbidAgentRuntime(db_path=tmp.name, default_cache_only=True)
            runtime.handle_input("probe laptop awards")
            result = runtime.handle_input("drill into the top finding")

        self.assertEqual(result["intent"], "detail")
        self.assertTrue(result["tool_trace"][0]["cli_equivalent"].startswith("probid detail A-100"))

    def test_session_followup_explain_top_finding_replays_last_result(self):
        from probid_probing_agent.core.runtime import ProbidAgentRuntime

        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            self._seed_db(tmp.name)
            runtime = ProbidAgentRuntime(db_path=tmp.name, default_cache_only=True)
            runtime.handle_input("probe laptop awards")
            result = runtime.handle_input("explain the top finding")

        self.assertEqual(result["intent"], "explain")
        self.assertEqual(result["tool_trace"], [])
        self.assertTrue(result["findings"])

    def test_session_followup_evidence_support_replays_last_evidence(self):
        from probid_probing_agent.core.runtime import ProbidAgentRuntime

        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            self._seed_db(tmp.name)
            runtime = ProbidAgentRuntime(db_path=tmp.name, default_cache_only=True)
            runtime.handle_input("probe laptop awards")
            result = runtime.handle_input("what evidence supports that?")

        self.assertEqual(result["intent"], "explain")
        self.assertEqual(result["tool_trace"], [])
        self.assertTrue(result["evidence"])

    def test_session_followup_caveats_replays_last_caveats(self):
        from probid_probing_agent.core.runtime import ProbidAgentRuntime

        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            self._seed_db(tmp.name)
            runtime = ProbidAgentRuntime(db_path=tmp.name, default_cache_only=True)
            runtime.handle_input("probe laptop awards")
            result = runtime.handle_input("what are the caveats?")

        self.assertEqual(result["intent"], "explain")
        self.assertEqual(result["tool_trace"], [])
        self.assertTrue(result["caveats"])

    def test_session_followup_simple_summary_replays_last_result(self):
        from probid_probing_agent.core.runtime import ProbidAgentRuntime

        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            self._seed_db(tmp.name)
            runtime = ProbidAgentRuntime(db_path=tmp.name, default_cache_only=True)
            runtime.handle_input("probe laptop awards")
            result = runtime.handle_input("summarize the last result simply")

        self.assertEqual(result["intent"], "explain")
        self.assertEqual(result["tool_trace"], [])
        self.assertTrue(result["findings"])

    def test_session_followup_compare_top_two_findings(self):
        from probid_probing_agent.core.runtime import ProbidAgentRuntime

        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            self._seed_db(tmp.name)
            with cache.connection(db_path=tmp.name) as conn:
                cache.upsert_award(
                    conn,
                    {
                        "ref_no": "A-101",
                        "project_title": "Laptop Supply 2",
                        "agency": "DICT",
                        "supplier": "BYTEWORKS INC",
                        "award_amount": 58000000,
                        "award_date": "2026-04-19",
                        "approved_budget": 60000000,
                        "bid_type": "Public Bidding",
                        "url": "https://example.local/awards/A-101",
                    },
                )
            runtime = ProbidAgentRuntime(db_path=tmp.name, default_cache_only=True)
            runtime.handle_input("probe laptop awards")
            result = runtime.handle_input("compare the top two findings")

        self.assertEqual(result["intent"], "explain")
        self.assertEqual(result["tool_trace"], [])
        self.assertGreaterEqual(len(result["findings"]), 2)

    def test_session_followup_top_finding_caveats(self):
        from probid_probing_agent.core.runtime import ProbidAgentRuntime

        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            self._seed_db(tmp.name)
            runtime = ProbidAgentRuntime(db_path=tmp.name, default_cache_only=True)
            runtime.handle_input("probe laptop awards")
            result = runtime.handle_input("show only the caveats for the top finding")

        self.assertEqual(result["intent"], "explain")
        self.assertEqual(result["tool_trace"], [])
        self.assertTrue(result["caveats"])

    def test_session_followup_strongest_finding(self):
        from probid_probing_agent.core.runtime import ProbidAgentRuntime

        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            self._seed_db(tmp.name)
            runtime = ProbidAgentRuntime(db_path=tmp.name, default_cache_only=True)
            runtime.handle_input("probe laptop awards")
            result = runtime.handle_input("which finding is strongest?")

        self.assertEqual(result["intent"], "explain")
        self.assertEqual(result["tool_trace"], [])
        self.assertTrue(result["findings"])
        self.assertIn("Strongest current finding", result["findings"][0]["summary"])

    def test_session_followup_next_checks(self):
        from probid_probing_agent.core.runtime import ProbidAgentRuntime

        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            self._seed_db(tmp.name)
            runtime = ProbidAgentRuntime(db_path=tmp.name, default_cache_only=True)
            runtime.handle_input("probe laptop awards")
            result = runtime.handle_input("what should i check next?")

        self.assertEqual(result["intent"], "explain")
        self.assertEqual(result["tool_trace"], [])
        self.assertTrue(result["next_actions"])

    def test_session_followup_more_concise(self):
        from probid_probing_agent.core.runtime import ProbidAgentRuntime

        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            self._seed_db(tmp.name)
            runtime = ProbidAgentRuntime(db_path=tmp.name, default_cache_only=True)
            runtime.handle_input("probe laptop awards")
            result = runtime.handle_input("make that more concise")

        self.assertEqual(result["intent"], "explain")
        self.assertEqual(result["tool_trace"], [])
        self.assertTrue(result["findings"])

    def test_session_followup_nontechnical_reader(self):
        from probid_probing_agent.core.runtime import ProbidAgentRuntime

        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            self._seed_db(tmp.name)
            runtime = ProbidAgentRuntime(db_path=tmp.name, default_cache_only=True)
            runtime.handle_input("probe laptop awards")
            result = runtime.handle_input("write that for a non-technical reader")

        self.assertEqual(result["intent"], "explain")
        self.assertEqual(result["tool_trace"], [])
        self.assertTrue(result["findings"][0]["summary"].startswith("In simple terms:"))

    def test_session_followup_checklist_version(self):
        from probid_probing_agent.core.runtime import ProbidAgentRuntime

        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            self._seed_db(tmp.name)
            runtime = ProbidAgentRuntime(db_path=tmp.name, default_cache_only=True)
            runtime.handle_input("probe laptop awards")
            result = runtime.handle_input("turn that into a checklist")

        self.assertEqual(result["intent"], "explain")
        self.assertEqual(result["tool_trace"], [])
        self.assertTrue(result["next_actions"])
        self.assertTrue(result["findings"])

    def test_session_followup_safest_next_command(self):
        from probid_probing_agent.core.runtime import ProbidAgentRuntime

        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            self._seed_db(tmp.name)
            runtime = ProbidAgentRuntime(db_path=tmp.name, default_cache_only=True)
            runtime.handle_input("probe laptop awards")
            result = runtime.handle_input("what is the safest next command to run?")

        self.assertEqual(result["intent"], "explain")
        self.assertEqual(result["tool_trace"], [])
        self.assertTrue(result["next_actions"])
        self.assertIn("Safest next command:", result["findings"][0]["summary"])

    def test_session_followup_investigation_note(self):
        from probid_probing_agent.core.runtime import ProbidAgentRuntime

        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            self._seed_db(tmp.name)
            runtime = ProbidAgentRuntime(db_path=tmp.name, default_cache_only=True)
            runtime.handle_input("probe laptop awards")
            result = runtime.handle_input("turn this into an investigation note")

        self.assertEqual(result["intent"], "explain")
        self.assertEqual(result["tool_trace"], [])
        self.assertTrue(any(item["summary"].startswith("Subject:") for item in result["findings"]))

    def test_session_followup_short_memo(self):
        from probid_probing_agent.core.runtime import ProbidAgentRuntime

        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            self._seed_db(tmp.name)
            runtime = ProbidAgentRuntime(db_path=tmp.name, default_cache_only=True)
            runtime.handle_input("probe laptop awards")
            result = runtime.handle_input("draft a short memo")

        self.assertEqual(result["intent"], "explain")
        self.assertEqual(result["tool_trace"], [])
        self.assertTrue(any(item["summary"].startswith("Memo:") for item in result["findings"]))

    def test_session_followup_structured_recap(self):
        from probid_probing_agent.core.runtime import ProbidAgentRuntime

        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            self._seed_db(tmp.name)
            runtime = ProbidAgentRuntime(db_path=tmp.name, default_cache_only=True)
            runtime.handle_input("probe laptop awards")
            result = runtime.handle_input("format this as findings, evidence, caveats, next steps")

        self.assertEqual(result["intent"], "explain")
        self.assertEqual(result["tool_trace"], [])
        self.assertTrue(any(item["summary"].startswith("Findings:") for item in result["findings"]))
        self.assertTrue(any(item["summary"].startswith("Evidence:") for item in result["findings"]))

    def test_session_followup_json_export(self):
        from probid_probing_agent.core.runtime import ProbidAgentRuntime

        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            self._seed_db(tmp.name)
            runtime = ProbidAgentRuntime(db_path=tmp.name, default_cache_only=True)
            runtime.handle_input("probe laptop awards")
            result = runtime.handle_input("turn this into json")

        self.assertEqual(result["intent"], "explain")
        self.assertEqual(result["tool_trace"], [])
        self.assertTrue(any(item["summary"].startswith("JSON:") for item in result["findings"]))
        self.assertEqual(result["export"]["format"], "json")
        self.assertEqual(result["export"]["content"]["query"], "laptop")

    def test_session_export_followups_do_not_overwrite_investigation_top_finding(self):
        from probid_probing_agent.core.runtime import ProbidAgentRuntime

        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            self._seed_db(tmp.name)
            runtime = ProbidAgentRuntime(db_path=tmp.name, default_cache_only=True)
            runtime.handle_input("probe laptop awards")
            runtime.handle_input("turn this into json")
            result = runtime.handle_input("make this a markdown report")

        self.assertEqual(result["intent"], "explain")
        self.assertEqual(result["tool_trace"], [])
        self.assertIn(
            "Limited local data may reduce detection reliability.",
            result["export"]["content"],
        )
        self.assertNotIn("JSON:", result["export"]["content"])

    def test_session_followup_markdown_report(self):
        from probid_probing_agent.core.runtime import ProbidAgentRuntime

        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            self._seed_db(tmp.name)
            runtime = ProbidAgentRuntime(db_path=tmp.name, default_cache_only=True)
            runtime.handle_input("probe laptop awards")
            result = runtime.handle_input("make this a markdown report")

        self.assertEqual(result["intent"], "explain")
        self.assertEqual(result["tool_trace"], [])
        self.assertTrue(any(item["summary"].startswith("# Procurement Probe Report:") for item in result["findings"]))
        self.assertEqual(result["export"]["format"], "markdown")
        self.assertIn("# Procurement Probe Report:", result["export"]["content"])

    def test_session_followup_compact_case_summary(self):
        from probid_probing_agent.core.runtime import ProbidAgentRuntime

        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            self._seed_db(tmp.name)
            runtime = ProbidAgentRuntime(db_path=tmp.name, default_cache_only=True)
            runtime.handle_input("probe laptop awards")
            result = runtime.handle_input("export a compact case summary")

        self.assertEqual(result["intent"], "explain")
        self.assertEqual(result["tool_trace"], [])
        self.assertTrue(any(item["summary"].startswith("Case summary:") for item in result["findings"]))
        self.assertEqual(result["export"]["format"], "case_summary")
        self.assertIn("summary", result["export"]["content"])

    def test_session_followup_csv_summary(self):
        from probid_probing_agent.core.runtime import ProbidAgentRuntime

        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            self._seed_db(tmp.name)
            runtime = ProbidAgentRuntime(db_path=tmp.name, default_cache_only=True)
            runtime.handle_input("probe laptop awards")
            result = runtime.handle_input("export a csv summary")

        self.assertEqual(result["intent"], "explain")
        self.assertEqual(result["tool_trace"], [])
        self.assertEqual(result["export"]["format"], "csv")
        self.assertIn("section,detail", result["export"]["content"])

    def test_session_followup_case_timeline(self):
        from probid_probing_agent.core.runtime import ProbidAgentRuntime

        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            self._seed_db(tmp.name)
            runtime = ProbidAgentRuntime(db_path=tmp.name, default_cache_only=True)
            runtime.handle_input("probe laptop awards")
            result = runtime.handle_input("make this a case timeline")

        self.assertEqual(result["intent"], "explain")
        self.assertEqual(result["tool_trace"], [])
        self.assertEqual(result["export"]["format"], "timeline")
        self.assertIn("# Case Timeline:", result["export"]["content"])

    def test_session_followup_findings_table(self):
        from probid_probing_agent.core.runtime import ProbidAgentRuntime

        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            self._seed_db(tmp.name)
            runtime = ProbidAgentRuntime(db_path=tmp.name, default_cache_only=True)
            runtime.handle_input("probe laptop awards")
            result = runtime.handle_input("turn this into a findings table")

        self.assertEqual(result["intent"], "explain")
        self.assertEqual(result["tool_trace"], [])
        self.assertEqual(result["export"]["format"], "findings_table")
        self.assertIn("| Section | Details |", result["export"]["content"])

    def test_session_followup_handoff_note(self):
        from probid_probing_agent.core.runtime import ProbidAgentRuntime

        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            self._seed_db(tmp.name)
            runtime = ProbidAgentRuntime(db_path=tmp.name, default_cache_only=True)
            runtime.handle_input("probe laptop awards")
            result = runtime.handle_input("generate a handoff note for another analyst")

        self.assertEqual(result["intent"], "explain")
        self.assertEqual(result["tool_trace"], [])
        self.assertTrue(any(item["summary"].startswith("Handoff:") for item in result["findings"]))
        self.assertEqual(result["export"]["format"], "handoff")
        self.assertIn("priority_finding", result["export"]["content"])

    def test_session_logger_can_retrieve_record_by_turn_id(self):
        with tempfile.NamedTemporaryFile(suffix=".jsonl") as tmp:
            logger = AgentSessionLogger(path=Path(tmp.name))
            turn_id = logger.log_turn(
                "probe laptop",
                {
                    "intent": "probe",
                    "query": "laptop",
                    "tool_trace": [],
                    "findings": [],
                },
            )
            row = logger.get_record(turn_id)

        self.assertIsNotNone(row)
        self.assertEqual(row["turn_id"], turn_id)
        self.assertEqual(row["intent"], "probe")


if __name__ == "__main__":
    unittest.main()
