"""Tests for JsonlTurnLogger edge cases."""

import tempfile
import unittest
from pathlib import Path

from probid_agent.session_logger import JsonlTurnLogger


class JsonlTurnLoggerEdgeCaseTests(unittest.TestCase):
    def test_get_record_raises_on_malformed_json_lines(self):
        with tempfile.NamedTemporaryFile(suffix=".jsonl") as tmp:
            path = Path(tmp.name)
            path.write_text('{"turn_id": "ok"}\nnot valid json\n', encoding="utf-8")

            logger = JsonlTurnLogger(path)
            with self.assertRaisesRegex(ValueError, r"Malformed JSONL in turn log .* line 2"):
                logger.get_record("missing")


if __name__ == "__main__":
    unittest.main()
