"""Smoke tests for probid CLI entrypoint."""

import unittest


class CliSmokeTests(unittest.TestCase):
    def test_cli_help_exits_zero(self):
        from click.testing import CliRunner

        from probid_probing_agent.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("probid", result.output.lower())

    def test_cli_probe_command_runs(self):
        from click.testing import CliRunner

        from probid_probing_agent.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["probe", "laptop"])
        # Should not crash; may have no cache but should handle gracefully
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
