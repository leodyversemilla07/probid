import unittest

from probid_agent.runtime_lifecycle import open_or_create_session, persist_turn, restore_turn_messages


class _SessionManagerStub:
    def __init__(self, rows=None):
        self._rows = rows or []
        self.appended = []

    def continue_recent(self):
        if not self._rows:
            return None
        return ("session-1", "dummy-path")

    def read_session_file(self, _path):
        return self._rows

    def create_session(self):
        return ("session-new", "new-path")

    def append_turn(self, session_id, turn):
        self.appended.append((session_id, turn))


class _SessionWithRestore(dict):
    def restore_from_messages(self):
        self["restored"] = True


class RuntimeLifecycleTests(unittest.TestCase):
    def test_restore_turn_messages_rebuilds_user_and_assistant_messages(self):
        rows = [
            {"type": "session_start"},
            {"type": "turn", "turn_id": "t1", "user_input": "probe laptop", "result": {"intent": "probe"}},
        ]
        messages = restore_turn_messages(rows)

        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["role"], "user")
        self.assertEqual(messages[1]["role"], "assistant")

    def test_open_or_create_session_continues_recent_when_available(self):
        rows = [{"type": "turn", "turn_id": "t1", "user_input": "probe", "result": {"intent": "probe"}}]
        manager = _SessionManagerStub(rows=rows)

        created = open_or_create_session(
            continue_recent=True,
            session_manager=manager,
            system_prompt="sys",
            session_factory=lambda **kwargs: kwargs,
        )

        self.assertEqual(created["session_id"], "session-1")
        self.assertEqual(len(created["messages"]), 2)

    def test_open_or_create_session_calls_restore_hook_when_available(self):
        rows = [{"type": "turn", "turn_id": "t1", "user_input": "probe", "result": {"intent": "probe"}}]
        manager = _SessionManagerStub(rows=rows)

        created = open_or_create_session(
            continue_recent=True,
            session_manager=manager,
            system_prompt="sys",
            session_factory=lambda **kwargs: _SessionWithRestore(kwargs),
        )

        self.assertTrue(created["restored"])
        self.assertEqual(created["session_id"], "session-1")

    def test_open_or_create_session_creates_new_when_no_recent(self):
        manager = _SessionManagerStub(rows=[])

        created = open_or_create_session(
            continue_recent=True,
            session_manager=manager,
            system_prompt="sys",
            session_factory=lambda **kwargs: kwargs,
        )

        self.assertEqual(created["session_id"], "session-new")
        self.assertNotIn("messages", created)

    def test_persist_turn_uses_canonical_payload_shape(self):
        manager = _SessionManagerStub()
        response = {"turn_id": "t-1", "intent": "probe"}

        persist_turn(
            session_manager=manager,
            session_id="session-xyz",
            user_input="probe laptop",
            response=response,
        )

        self.assertEqual(len(manager.appended), 1)
        session_id, turn = manager.appended[0]
        self.assertEqual(session_id, "session-xyz")
        self.assertEqual(turn["type"], "turn")
        self.assertEqual(turn["user_input"], "probe laptop")
        self.assertEqual(turn["result"]["intent"], "probe")
        self.assertNotEqual(turn["timestamp"], turn["turn_id"])
        self.assertTrue(str(turn["timestamp"]).endswith("Z"))


if __name__ == "__main__":
    unittest.main()
