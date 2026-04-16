import unittest

from probid_agent.response_composer import BaseResponseComposer


class ResponseComposerTests(unittest.TestCase):
    def test_compose_probe_uses_summary_and_fallback_actions(self):
        composer = BaseResponseComposer()
        payload = {
            "summary": {
                "records_scanned": 10,
                "agencies_touched": 2,
                "data_quality_note": "Limited data",
            },
            "findings": [{"summary": "Example finding"}],
            "next_checks": [],
        }
        result = composer.compose(
            intent="probe",
            query="laptop",
            payload=payload,
            tool_trace=[],
            fallback_next_actions=lambda q: [f"probe {q} --why"],
        )

        self.assertEqual(result["intent"], "probe")
        self.assertIn("records_scanned=10", result["evidence"])
        self.assertIn("agencies_touched=2", result["evidence"])
        self.assertIn("Limited data", result["caveats"])
        self.assertEqual(result["next_actions"], ["probe laptop --why"])

    def test_compose_accepts_assumptions_override_and_enricher(self):
        composer = BaseResponseComposer()
        payload = {"summary": {}, "findings": [], "next_checks": []}

        def _enricher(envelope, _context):
            envelope["caveats"].append("enriched")

        result = composer.compose(
            intent="probe",
            query="server",
            payload=payload,
            tool_trace=[],
            assumptions=["custom assumption"],
            enricher=_enricher,
            fallback_next_actions=lambda q: [f"probe {q} --json"],
        )

        self.assertEqual(result["assumptions"], ["custom assumption"])
        self.assertIn("enriched", result["caveats"])
        self.assertEqual(result["next_actions"], ["probe server --json"])

    def test_compose_supports_domain_policy(self):
        composer = BaseResponseComposer()
        payload = {"summary": {}, "findings": [], "next_checks": []}

        class _Policy:
            def assumptions(self):
                return ["policy assumption"]

            def enrich(self, envelope, _context):
                envelope["evidence"].append("policy=enriched")

        result = composer.compose(
            intent="probe",
            query="network",
            payload=payload,
            tool_trace=[],
            policy=_Policy(),
            fallback_next_actions=lambda q: [f"probe {q} --why"],
        )

        self.assertEqual(result["assumptions"], ["policy assumption"])
        self.assertIn("policy=enriched", result["evidence"])


if __name__ == "__main__":
    unittest.main()
