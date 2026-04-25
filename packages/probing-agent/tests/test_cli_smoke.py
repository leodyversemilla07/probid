"""Smoke tests for probid CLI entrypoint."""

import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import Mock, patch


class CliSmokeTests(unittest.TestCase):
    def test_cli_help_exits_zero(self):
        from click.testing import CliRunner

        from probid_probing_agent.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("probid", result.output.lower())
        self.assertIn("session-aware follow-ups", result.output)
        self.assertIn("show last export destination", result.output)
        self.assertIn("list prior exports", result.output)
        self.assertIn("exports", result.output)
        self.assertIn("--export-output", result.output)
        self.assertIn("--continue-recent", result.output)

    def test_cli_probe_command_runs(self):
        from click.testing import CliRunner

        from probid_probing_agent.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["probe", "laptop"])
        # Should not crash; may have no cache but should handle gracefully
        self.assertNotIn("Traceback", result.output)

    def test_cli_probe_refreshes_recent_awards_before_analysis(self):
        from click.testing import CliRunner

        from probid_probing_agent.cli import cli

        @contextmanager
        def fake_connection(db_path=None):
            yield object()

        fake_result = {
            "metadata": {"query": "laptop", "min_confidence": "low", "max_findings": 5},
            "summary": {
                "records_scanned": 0,
                "notice_count": 0,
                "award_count": 0,
                "agencies_touched": 0,
                "total_known_value": 0,
                "finding_count": 0,
                "data_quality_status": "constrained",
                "data_quality_note": "test",
            },
            "risk_map": {},
            "findings": [],
        }

        runner = CliRunner()
        with (
            patch(
                "probid_probing_agent.cli.commands.search.cache.connection",
                fake_connection,
            ),
            patch(
                "probid_probing_agent.cli.commands.search.geps.search",
                return_value=[{"ref_no": "N1", "title": "Laptop notice", "agency": "DICT"}],
            ) as mock_search,
            patch(
                "probid_probing_agent.cli.commands.search.geps.search_awards",
                return_value=[
                    {
                        "ref_no": "A1",
                        "project_title": "Laptop award",
                        "agency": "DICT",
                        "supplier": "ACME",
                    }
                ],
            ) as mock_search_awards,
            patch("probid_probing_agent.cli.commands.search.cache.upsert_notice") as mock_upsert_notice,
            patch("probid_probing_agent.cli.commands.search.cache.upsert_award") as mock_upsert_award,
            patch(
                "probid_probing_agent.cli.commands.search.analysis.analyze_probe_findings",
                return_value=fake_result,
            ) as mock_analyze,
            patch("probid_probing_agent.cli.commands.search.geps.close") as mock_close,
        ):
            result = runner.invoke(cli, ["probe", "laptop", "--json"])

        self.assertEqual(result.exit_code, 0)
        mock_search.assert_called_once_with("laptop", max_pages=1)
        mock_search_awards.assert_called_once_with(agency="", max_pages=1)
        mock_upsert_notice.assert_called_once()
        mock_upsert_award.assert_called_once()
        mock_analyze.assert_called_once()
        mock_close.assert_called_once()
        self.assertIn('"query": "laptop"', result.output)

    def test_cli_detail_cache_only_uses_cache_without_scraping(self):
        from click.testing import CliRunner

        from probid_probing_agent.cli import cli

        cached_row = {
            "ref_no": "12905086",
            "title": "Cached laptop notice",
            "agency": "DICT",
            "documents": "[]",
        }
        conn = Mock()
        conn.execute.return_value.fetchone.return_value = cached_row

        @contextmanager
        def fake_connection(db_path=None):
            yield conn

        runner = CliRunner()
        with (
            patch("probid_probing_agent.cli.commands.search.cache.connection", fake_connection),
            patch("probid_probing_agent.cli.commands.search.geps.get_notice_detail") as mock_get_detail,
        ):
            result = runner.invoke(cli, ["detail", "12905086", "--cache-only"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Showing cached data", result.output)
        self.assertIn("Cached laptop notice", result.output)
        mock_get_detail.assert_not_called()

    def test_cli_detail_cache_only_reports_missing_cache_without_scraping(self):
        from click.testing import CliRunner

        from probid_probing_agent.cli import cli

        conn = Mock()
        conn.execute.return_value.fetchone.return_value = None

        @contextmanager
        def fake_connection(db_path=None):
            yield conn

        runner = CliRunner()
        with (
            patch("probid_probing_agent.cli.commands.search.cache.connection", fake_connection),
            patch("probid_probing_agent.cli.commands.search.geps.get_notice_detail") as mock_get_detail,
        ):
            result = runner.invoke(cli, ["detail", "12905086", "--cache-only"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("No cached detail found for 12905086", result.output)
        mock_get_detail.assert_not_called()

    def test_cli_exports_command_lists_recent_export_artifacts(self):
        import tempfile

        from click.testing import CliRunner

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
            result = runner.invoke(cli, ["exports", "--session-dir", td])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Export artifacts for session", result.output)
        self.assertIn("json: /tmp/export.json", result.output)

    def test_cli_exports_help_mentions_format_filter(self):
        from click.testing import CliRunner

        from probid_probing_agent.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["exports", "--help"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("--format", result.output)
        self.assertIn("unique prefix", result.output)

    def test_cli_exports_command_can_filter_by_format(self):
        import tempfile

        from click.testing import CliRunner

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
            manager.append_turn(
                session_id,
                {
                    "type": "export_artifact",
                    "export_format": "markdown",
                    "query": "laptop",
                    "output_path": "/tmp/report.md",
                    "destination": "file",
                },
            )
            runner = CliRunner()
            result = runner.invoke(cli, ["exports", "--session-dir", td, "--format", "markdown"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("format=markdown", result.output)
        self.assertIn("markdown: /tmp/report.md", result.output)
        self.assertNotIn("json: /tmp/export.json", result.output)

    def test_cli_exports_command_supports_all_flag(self):
        import tempfile

        from click.testing import CliRunner

        from probid_probing_agent.cli import cli
        from probid_probing_agent.core.session_manager import ProbidSessionManager

        with tempfile.TemporaryDirectory() as td:
            manager = ProbidSessionManager(Path(td))
            # Session 1
            session_id1, _path = manager.create_session()
            manager.append_turn(
                session_id1,
                {
                    "type": "export_artifact",
                    "export_format": "json",
                    "query": "laptop",
                    "output_path": "/tmp/export.json",
                    "destination": "file",
                },
            )
            # Session 2
            session_id2, _path = manager.create_session()
            manager.append_turn(
                session_id2,
                {
                    "type": "export_artifact",
                    "export_format": "markdown",
                    "query": "server",
                    "output_path": "/tmp/report.md",
                    "destination": "file",
                },
            )
            runner = CliRunner()
            result = runner.invoke(cli, ["exports", "--session-dir", td, "--all"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Export artifacts across all sessions", result.output)
        self.assertIn("json: /tmp/export.json", result.output)
        self.assertIn("markdown: /tmp/report.md", result.output)

    def test_cli_exports_command_supports_limit(self):
        import tempfile

        from click.testing import CliRunner

        from probid_probing_agent.cli import cli
        from probid_probing_agent.core.session_manager import ProbidSessionManager

        with tempfile.TemporaryDirectory() as td:
            manager = ProbidSessionManager(Path(td))
            session_id, _path = manager.create_session()
            for i in range(5):
                manager.append_turn(
                    session_id,
                    {
                        "type": "export_artifact",
                        "export_format": "json",
                        "query": f"query{i}",
                        "output_path": f"/tmp/export{i}.json",
                        "destination": "file",
                    },
                )
            runner = CliRunner()
            result = runner.invoke(cli, ["exports", "--session-dir", td, "--limit", "3"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("limit=3", result.output)
        # Should show only 3 entries
        self.assertEqual(result.output.count("json: /tmp/export"), 3)

    def test_cli_query_mode_translates_runtime_value_error_to_cli_error(self):
        from click.testing import CliRunner

        from probid_probing_agent.cli import cli

        runner = CliRunner()
        with patch(
            "probid_probing_agent.core.runtime.ProbidAgentRuntime.handle_input",
            side_effect=ValueError("Failed to parse LLM response"),
        ):
            result = runner.invoke(cli, ["-q", "probe laptop", "--provider", "ai"])

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("Failed to parse LLM response", result.output)
        self.assertNotIn("Traceback", result.output)

    def test_cli_agent_query_mode_translates_runtime_value_error_to_cli_error(self):
        from click.testing import CliRunner

        from probid_probing_agent.cli import cli

        runner = CliRunner()
        with patch(
            "probid_probing_agent.core.runtime.ProbidAgentRuntime.handle_input",
            side_effect=ValueError("Failed to parse LLM response"),
        ):
            result = runner.invoke(cli, ["agent", "-q", "probe laptop", "--provider", "ai"])

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("Failed to parse LLM response", result.output)
        self.assertNotIn("Traceback", result.output)

    def test_cli_version_flag(self):
        from click.testing import CliRunner

        from probid_probing_agent.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("0.1.0", result.output)


if __name__ == "__main__":
    unittest.main()
