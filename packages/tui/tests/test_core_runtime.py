import unittest

from probid_tui.core import (
    TUI,
    Container,
    OverlayOptions,
    parse_key,
    split_input_sequences,
    truncate_to_width,
    visible_width,
    wrap_text_with_ansi,
)


class _Static:
    def __init__(self, lines):
        self.lines = lines

    def render(self, width: int):
        return [line[:width] for line in self.lines]

    def handle_input(self, data: bytes):
        return False

    def invalidate(self):
        return


class _Terminal:
    def __init__(self, cols=40, rows=10):
        self.cols = cols
        self.rows = rows
        self.output = ""
        self._resize = []

    def write(self, data: str):
        self.output += data

    def get_size(self):
        return self.cols, self.rows

    def on_resize(self, cb):
        self._resize.append(cb)

    def restore(self):
        return


class CoreRuntimeTests(unittest.TestCase):
    def test_container_concatenates_children(self):
        c = Container()
        c.add_child(_Static(["a"]))
        c.add_child(_Static(["b", "c"]))
        self.assertEqual(c.render(80), ["a", "b", "c"])

    def test_parse_key_legacy_and_plain(self):
        self.assertEqual(parse_key(b"\x1b[A"), "up")
        self.assertEqual(parse_key(b"a"), "a")

    def test_split_input_sequences_handles_mixed_bytes(self):
        mixed = b"ab\x1b[A\x1b[200~x\n\x1b[201~"
        parts = split_input_sequences(mixed)
        self.assertEqual(parts[0], b"a")
        self.assertEqual(parts[1], b"b")
        self.assertEqual(parts[2], b"\x1b[A")
        self.assertTrue(parts[3].startswith(b"\x1b[200~"))

    def test_visible_width_and_truncate(self):
        self.assertEqual(visible_width("abc"), 3)
        self.assertEqual(truncate_to_width("abcdef", 3), "abc")

    def test_wrap_text(self):
        wrapped = wrap_text_with_ansi("hello world", 5)
        self.assertTrue(len(wrapped) >= 2)

    def test_overlay_composites_render_output(self):
        terminal = _Terminal(cols=30, rows=8)
        tui = TUI(terminal)  # type: ignore[arg-type]
        tui.add_child(_Static(["base line"]))
        tui.show_overlay(_Static(["OVR"]), OverlayOptions(width=10, anchor="top-left", margin=0))
        tui._do_render(force=True)
        self.assertIn("OVR", terminal.output)


if __name__ == "__main__":
    unittest.main()
