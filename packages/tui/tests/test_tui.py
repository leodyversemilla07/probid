"""Tests for probid TUI components."""

import unittest

from probid_tui.components.table import format_currency, create_table, TableConfig
from probid_tui.editor_surface import EditorSurface
from probid_tui.theme import ThemeColors, ThemeStyles, apply_style, get_theme


class TUIThemeTests(unittest.TestCase):
    def test_theme_colors_defaults(self):
        colors = ThemeColors()
        self.assertEqual(colors.primary, "cyan")
        self.assertEqual(colors.success, "green")
        self.assertEqual(colors.error, "red")

    def test_theme_styles_defaults(self):
        styles = ThemeStyles()
        self.assertEqual(styles.header, "bold cyan")
        self.assertEqual(styles.finding_risk, "bold red")

    def test_get_theme_returns_tuple(self):
        colors, styles = get_theme()
        self.assertIsInstance(colors, ThemeColors)
        self.assertIsInstance(styles, ThemeStyles)

    def test_apply_style_wraps_text(self):
        result = apply_style("hello", "bold red")
        self.assertEqual(result, "[bold red]hello[/bold red]")

    def test_apply_style_empty_returns_original(self):
        result = apply_style("hello", "")
        self.assertEqual(result, "hello")


class TUITableTests(unittest.TestCase):
    def test_format_currency_k(self):
        result = format_currency(1500)
        self.assertEqual(result, "PHP 1.50K")

    def test_format_currency_m(self):
        result = format_currency(2_500_000)
        self.assertEqual(result, "PHP 2.50M")

    def test_format_currency_b(self):
        result = format_currency(1_500_000_000)
        self.assertEqual(result, "PHP 1.50B")

    def test_format_currency_zero(self):
        result = format_currency(0)
        self.assertEqual(result, "—")

    def test_format_currency_negative(self):
        result = format_currency(-100)
        self.assertEqual(result, "—")

    def test_format_currency_custom(self):
        result = format_currency(1500, "USD")
        self.assertEqual(result, "USD 1.50K")

    def test_create_table_returns_table(self):
        table = create_table(
            title="Test",
            columns=("A", "B"),
            column_styles=("red", "blue"),
        )
        self.assertEqual(table.title, "Test")
        self.assertEqual(len(table.columns), 2)


class TableConfigTests(unittest.TestCase):
    def test_table_config_defaults(self):
        config = TableConfig()
        self.assertIsNone(config.title)
        self.assertEqual(config.columns, ())
        self.assertFalse(config.show_lines)


class EditorSurfaceTests(unittest.TestCase):
    def test_editor_surface_renders_top_and_bottom_rails(self):
        surface = EditorSurface()
        lines = surface.render(40, [""], 0)
        self.assertEqual(len(lines), 3)
        self.assertTrue(lines[0].startswith("─"))
        self.assertTrue(lines[-1].startswith("─"))

    def test_editor_surface_shows_scroll_indicators(self):
        surface = EditorSurface()
        lines = surface.render(40, ["a", "b", "c", "d", "e", "f"], 2)
        self.assertIn("↑", lines[0])


if __name__ == "__main__":
    unittest.main()
