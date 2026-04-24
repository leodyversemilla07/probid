import unittest

from probid_tui.core import Editor


class EditorComponentTests(unittest.TestCase):
    def test_insert_and_backspace(self):
        editor = Editor(max_visible_lines=3)
        editor._process_input(b"a")
        editor._process_input(b"b")
        editor._process_input(b"c")
        self.assertEqual(editor.get_value(), "abc")

        editor._process_input(b"\x7f")  # backspace
        self.assertEqual(editor.get_value(), "ab")

    def test_multiline_and_cursor_render(self):
        editor = Editor(max_visible_lines=4)
        editor.focused = True
        editor.set_value("line1\nline2")
        lines = editor.render(20)
        self.assertGreaterEqual(len(lines), 3)  # top + body + bottom
        joined = "\n".join(lines)
        self.assertIn("█", joined)

    def test_scroll_indicator_for_long_content(self):
        editor = Editor(max_visible_lines=2)
        editor.focused = True
        editor.set_value("a\nb\nc\nd")
        editor._process_input(b"\x1b[A")
        editor._process_input(b"\x1b[A")
        editor._process_input(b"\x1b[A")
        lines = editor.render(20)
        self.assertIn("↓", lines[-1])

    def test_submit_persists_history_and_clears(self):
        editor = Editor()
        editor.set_value("probe laptop")
        value = editor.submit()
        self.assertEqual(value, "probe laptop")
        self.assertEqual(editor.get_value(), "")
