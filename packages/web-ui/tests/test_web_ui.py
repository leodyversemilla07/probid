"""Tests for probid web UI components."""

import unittest

from probid_web_ui.render import escape_html, format_currency_html, render_notices_table
from probid_web_ui.types import AgencyProfile, AwardRecord, Finding, NoticeData, ProbeResult, SupplierProfile


class WebUITypesTests(unittest.TestCase):
    def test_notice_data_defaults(self):
        notice = NoticeData(ref_id="123", title="Test")
        self.assertEqual(notice.ref_id, "123")
        self.assertIsNone(notice.budget)
        self.assertIsNone(notice.winning_bidder)

    def test_finding_defaults(self):
        finding = Finding(code="R1", description="Test finding")
        self.assertEqual(finding.confidence, "medium")

    def test_probe_result_defaults(self):
        result = ProbeResult()
        self.assertEqual(result.data_quality, "adequate")
        self.assertEqual(result.findings, [])

    def test_supplier_profile_defaults(self):
        profile = SupplierProfile(name="ACME")
        self.assertEqual(profile.total_contracts, 0)
        self.assertEqual(profile.agencies, [])

    def test_agency_profile_defaults(self):
        profile = AgencyProfile(name="DICT")
        self.assertEqual(profile.total_budget, 0.0)
        self.assertEqual(profile.categories, [])


class WebUIRenderTests(unittest.TestCase):
    def test_escape_html(self):
        result = escape_html("<script>alert('xss')</script>")
        self.assertNotIn("<script>", result)
        self.assertIn("&lt;", result)

    def test_escape_html_quotes(self):
        result = escape_html('hello "world"')
        self.assertIn("&quot;", result)

    def test_format_currency_html_zero(self):
        result = format_currency_html(0)
        self.assertIn("currency-missing", result)

    def test_format_currency_html_negative(self):
        result = format_currency_html(-100)
        self.assertIn("currency-missing", result)

    def test_format_currency_html_none(self):
        result = format_currency_html(None)
        self.assertIn("currency-missing", result)

    def test_format_currency_html_k(self):
        result = format_currency_html(1500)
        self.assertIn("1.50K", result)

    def test_format_currency_html_m(self):
        result = format_currency_html(2_500_000)
        self.assertIn("2.50M", result)

    def test_format_currency_html_custom(self):
        result = format_currency_html(1500, "USD")
        self.assertIn("USD", result)

    def test_render_notices_table_empty(self):
        result = render_notices_table([])
        self.assertIn("No results found", result)

    def test_render_notices_table_single(self):
        notices = [NoticeData(ref_id="123", title="Test Notice", budget=1000)]
        result = render_notices_table(notices)
        self.assertIn("123", result)
        self.assertIn("Test Notice", result)


if __name__ == "__main__":
    unittest.main()
