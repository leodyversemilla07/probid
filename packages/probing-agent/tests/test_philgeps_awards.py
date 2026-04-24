import unittest
from unittest.mock import patch

from probid_probing_agent.core.sources import philgeps


class _Waitable:
    def wait_for(self, state=None, timeout=None):
        return None


class _SimpleLocator:
    def __init__(self, *, first=None, items=None):
        self._first = first
        self._items = items or []

    @property
    def first(self):
        return self._first

    def all(self):
        return self._items


class _Cell:
    def __init__(self, text: str, href: str | None = None):
        self._text = text
        self._href = href

    def inner_text(self):
        return self._text

    def locator(self, selector: str):
        if selector == "a" and self._href is not None:
            return _SimpleLocator(first=_Link(self._href))
        return _SimpleLocator(first=_Link(None))


class _Link:
    def __init__(self, href: str | None):
        self._href = href

    def get_attribute(self, name: str):
        if name == "href":
            return self._href
        return None


class _Row:
    def __init__(self, cells):
        self._cells = cells

    def locator(self, selector: str):
        if selector == "td":
            return _SimpleLocator(items=self._cells)
        return _SimpleLocator(items=[])


class _Page:
    def __init__(self, rows):
        self._rows = rows
        self.closed = False

    def goto(self, url, wait_until=None, timeout=None):
        return None

    def locator(self, selector: str):
        if selector == "table tr td":
            return _SimpleLocator(first=_Waitable())
        if selector == "table tr":
            return _SimpleLocator(items=self._rows)
        return _SimpleLocator(items=[])

    def close(self):
        self.closed = True


class _Context:
    def __init__(self, page):
        self._page = page

    def new_page(self):
        return self._page


class PhilgepsAwardsTests(unittest.TestCase):
    @patch("probid_probing_agent.core.sources.philgeps._rate_limit")
    @patch("probid_probing_agent.core.sources.philgeps._get_context")
    def test_search_awards_parses_rows_and_ref_id(self, mock_get_context, _mock_rate_limit):
        rows = [
            _Row(
                [
                    _Cell("#"),
                    _Cell("Date"),
                    _Cell("Project"),
                    _Cell("Supplier"),
                    _Cell("Amount"),
                ]
            ),
            _Row(
                [
                    _Cell("1"),
                    _Cell("01/04/2026"),
                    _Cell(
                        "Laptop Supply",
                        href="SplashBidNoticeAbstractUI.aspx?refID=12905086",
                    ),
                    _Cell("ACME CORP"),
                    _Cell("PHP 1,234,567.89"),
                ]
            ),
            _Row(
                [
                    _Cell("2"),
                    _Cell("02/04/2026"),
                    _Cell(
                        "Server Upgrade",
                        href="SplashBidNoticeAbstractUI.aspx?refID=12000001",
                    ),
                    _Cell("BETA INC"),
                    _Cell("PHP 987,654.00"),
                ]
            ),
        ]
        page = _Page(rows)
        mock_get_context.return_value = _Context(page)

        awards = philgeps.search_awards(agency="DICT", max_pages=1)

        self.assertEqual(len(awards), 2)
        self.assertEqual(awards[0]["ref_no"], "12905086")
        self.assertEqual(awards[0]["agency"], "DICT")
        self.assertEqual(awards[0]["supplier"], "ACME CORP")
        self.assertEqual(awards[0]["award_date"], "2026-04-01")
        self.assertAlmostEqual(awards[0]["award_amount"], 1234567.89)
        self.assertTrue(page.closed)

    @patch("probid_probing_agent.core.sources.philgeps._rate_limit")
    @patch("probid_probing_agent.core.sources.philgeps._get_context")
    def test_search_awards_handles_missing_link_gracefully(self, mock_get_context, _mock_rate_limit):
        rows = [
            _Row(
                [
                    _Cell("1"),
                    _Cell("15/04/2026"),
                    _Cell("No Ref Project"),
                    _Cell("OMEGA LTD"),
                    _Cell("PHP 100,000"),
                ]
            )
        ]
        page = _Page(rows)
        mock_get_context.return_value = _Context(page)

        awards = philgeps.search_awards(agency="", max_pages=1)

        self.assertEqual(len(awards), 1)
        self.assertEqual(awards[0]["ref_no"], "")
        self.assertEqual(awards[0]["project_title"], "No Ref Project")


if __name__ == "__main__":
    unittest.main()
