import unittest

from probid_tui.components.input import Input
from probid_tui.core.ansi_utils import visible_width


class InputParityTests(unittest.TestCase):
    def test_submits_value_including_backslash_on_enter(self):
        input_view = Input()
        submitted = {"value": None}
        input_view.on_submit = lambda value: submitted.__setitem__("value", value)

        for ch in "hello\\":
            input_view.handle_input(ch.encode("utf-8"))
        input_view.handle_input(b"\r")
        self.assertEqual(submitted["value"], "hello\\")

    def test_inserts_backslash_as_regular_character(self):
        input_view = Input()
        input_view.handle_input(b"\\")
        input_view.handle_input(b"x")
        self.assertEqual(input_view.get_value(), "\\x")

    def test_render_does_not_overflow_with_wide_text(self):
        width = 40
        cases = [
            "가나다라마바사아자차카타파하 한글 텍스트",
            "これはテスト文章です。日本語の表示幅確認。",
            "这是一段测试文本，用于验证中文字符显示。",
            "ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶ",
        ]

        for text in cases:
            # start
            input_view = Input()
            input_view.set_value(text)
            input_view.focused = True
            line = input_view.render(width)[0]
            self.assertLessEqual(visible_width(line), width)

            # middle
            input_view.handle_input(b"\x01")  # ctrl+a
            for _ in range(10):
                input_view.handle_input(b"\x1b[C")
            line = input_view.render(width)[0]
            self.assertLessEqual(visible_width(line), width)

            # end
            input_view.handle_input(b"\x05")  # ctrl+e
            line = input_view.render(width)[0]
            self.assertLessEqual(visible_width(line), width)

    def test_ctrl_w_then_ctrl_y_yanks_deleted_word(self):
        input_view = Input()
        input_view.set_value("foo bar baz")
        input_view.handle_input(b"\x05")  # ctrl+e
        input_view.handle_input(b"\x17")  # ctrl+w
        self.assertEqual(input_view.get_value(), "foo bar ")

        input_view.handle_input(b"\x01")  # ctrl+a
        input_view.handle_input(b"\x19")  # ctrl+y
        self.assertEqual(input_view.get_value(), "bazfoo bar ")

    def test_alt_y_cycles_kill_ring_after_yank(self):
        input_view = Input()

        input_view.set_value("first")
        input_view.handle_input(b"\x05")
        input_view.handle_input(b"\x17")
        input_view.set_value("second")
        input_view.handle_input(b"\x05")
        input_view.handle_input(b"\x17")
        input_view.set_value("third")
        input_view.handle_input(b"\x05")
        input_view.handle_input(b"\x17")
        self.assertEqual(input_view.get_value(), "")

        input_view.handle_input(b"\x19")  # ctrl+y
        self.assertEqual(input_view.get_value(), "third")
        input_view.handle_input(b"\x1by")  # alt+y
        self.assertEqual(input_view.get_value(), "second")
        input_view.handle_input(b"\x1by")  # alt+y
        self.assertEqual(input_view.get_value(), "first")

    def test_undo_coalesces_word_typing(self):
        input_view = Input()
        for ch in "hello world":
            input_view.handle_input(ch.encode("utf-8"))
        self.assertEqual(input_view.get_value(), "hello world")

        input_view.handle_input(b"\x1b[45;5u")  # ctrl+- (kitty CSI-u)
        self.assertEqual(input_view.get_value(), "hello")
        input_view.handle_input(b"\x1b[45;5u")
        self.assertEqual(input_view.get_value(), "")


if __name__ == "__main__":
    unittest.main()
