"""Tests for JsonlSessionManager edge cases."""

import json
import tempfile
import unittest
from pathlib import Path

from probid_agent.session_manager import JsonlSessionManager


class JsonlSessionManagerEdgeCaseTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.manager = JsonlSessionManager(Path(self.tmpdir))

    def tearDown(self):
        import shutil

        shutil.rmtree(self.tmpdir)

    def test_list_sessions_on_empty_dir_returns_empty_list(self):
        self.assertEqual(self.manager.list_sessions(), [])

    def test_continue_recent_on_empty_dir_returns_none(self):
        self.assertIsNone(self.manager.continue_recent())

    def test_read_session_file_on_missing_path_returns_empty_list(self):
        result = self.manager.read_session_file(Path("/nonexistent/file.jsonl"))
        self.assertEqual(result, [])

    def test_read_session_file_raises_on_malformed_json_lines(self):
        session_id, path = self.manager.create_session()

        # Append a turn via the manager (creates valid header + turn)
        self.manager.append_turn(session_id, {"type": "turn", "user_input": "first"})

        # Then manually add malformed content
        with path.open("a", encoding="utf-8") as f:
            f.write('{"type": "turn", "user_input": "ok"}\n')
            f.write("not valid json\n")
            f.write('{"type": "turn", "user_input": "also ok"}\n')

        with self.assertRaisesRegex(ValueError, r"Malformed JSONL in session file .* line 4"):
            self.manager.read_session_file(path)

    def test_create_session_makes_valid_jsonl_with_header(self):
        session_id, path = self.manager.create_session()

        rows = self.manager.read_session_file(path)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["type"], "session_start")
        self.assertEqual(rows[0]["session_id"], session_id)

    def test_append_turn_and_read_roundtrip(self):
        session_id, path = self.manager.create_session()

        turn = {"type": "turn", "user_input": "probe laptop", "result": {"intent": "probe"}}
        self.manager.append_turn(session_id, turn)

        rows = self.manager.read_session_file(path)
        self.assertEqual(len(rows), 2)  # header + turn
        self.assertEqual(rows[1]["user_input"], "probe laptop")
        self.assertEqual(rows[1]["result"]["intent"], "probe")


if __name__ == "__main__":
    unittest.main()
