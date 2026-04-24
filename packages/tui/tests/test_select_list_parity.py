import unittest

from probid_tui.components.select_list import (
    SelectItem,
    SelectList,
    SelectListLayoutOptions,
    SelectListTheme,
)
from probid_tui.core.ansi_utils import visible_width


def _visible_index_of(line: str, text: str) -> int:
    idx = line.find(text)
    if idx < 0:
        raise AssertionError(f"'{text}' not found in line: {line!r}")
    return visible_width(line[:idx])


class SelectListParityTests(unittest.TestCase):
    def setUp(self):
        self.theme = SelectListTheme(
            selected_prefix=lambda s: s,
            selected_text=lambda s: s,
            description=lambda s: s,
            scroll_info=lambda s: s,
            no_match=lambda s: s,
        )

    def test_normalizes_multiline_descriptions_to_single_line(self):
        items = [
            SelectItem(value="test", label="test", description="Line one\nLine two\nLine three"),
        ]
        rendered = SelectList(items, 5, self.theme).render(100)
        self.assertTrue(rendered)
        self.assertNotIn("\n", rendered[0])
        self.assertIn("Line one Line two Line three", rendered[0])

    def test_keeps_descriptions_aligned_when_primary_is_truncated(self):
        items = [
            SelectItem(value="short", label="short", description="short description"),
            SelectItem(
                value="very-long-command-name-that-needs-truncation",
                label="very-long-command-name-that-needs-truncation",
                description="long description",
            ),
        ]
        rendered = SelectList(items, 5, self.theme).render(80)
        self.assertEqual(
            _visible_index_of(rendered[0], "short description"),
            _visible_index_of(rendered[1], "long description"),
        )

    def test_uses_configured_min_primary_column_width(self):
        items = [
            SelectItem(value="a", label="a", description="first"),
            SelectItem(value="bb", label="bb", description="second"),
        ]
        list_view = SelectList(
            items,
            5,
            self.theme,
            SelectListLayoutOptions(min_primary_column_width=12, max_primary_column_width=20),
        )
        rendered = list_view.render(80)
        self.assertEqual(rendered[0].find("first"), 14)
        self.assertEqual(rendered[1].find("second"), 14)

    def test_uses_configured_max_primary_column_width(self):
        items = [
            SelectItem(
                value="very-long-command-name-that-needs-truncation",
                label="very-long-command-name-that-needs-truncation",
                description="first",
            ),
            SelectItem(value="short", label="short", description="second"),
        ]
        list_view = SelectList(
            items,
            5,
            self.theme,
            SelectListLayoutOptions(min_primary_column_width=12, max_primary_column_width=20),
        )
        rendered = list_view.render(80)
        self.assertEqual(_visible_index_of(rendered[0], "first"), 22)
        self.assertEqual(_visible_index_of(rendered[1], "second"), 22)

    def test_allows_custom_primary_truncation_without_losing_alignment(self):
        items = [
            SelectItem(
                value="very-long-command-name-that-needs-truncation",
                label="very-long-command-name-that-needs-truncation",
                description="first",
            ),
            SelectItem(value="short", label="short", description="second"),
        ]

        def _truncate(ctx):
            if len(ctx.text) <= ctx.max_width:
                return ctx.text
            return f"{ctx.text[: max(0, ctx.max_width - 1)]}…"

        list_view = SelectList(
            items,
            5,
            self.theme,
            SelectListLayoutOptions(
                min_primary_column_width=12,
                max_primary_column_width=12,
                truncate_primary=_truncate,
            ),
        )
        rendered = list_view.render(80)
        self.assertIn("…", rendered[0])
        self.assertEqual(
            _visible_index_of(rendered[0], "first"),
            _visible_index_of(rendered[1], "second"),
        )


if __name__ == "__main__":
    unittest.main()
