import unittest

from probid_probing_agent.core.response_builder import ResponseBuilder


class ResponseBuilderTests(unittest.TestCase):
    def test_build_enriches_multi_step_probe_with_tool_trace(self):
        builder = ResponseBuilder()
        payload = {
            "summary": {
                "records_scanned": 12,
                "agencies_touched": 1,
                "data_quality_note": "Limited data volume",
            },
            "findings": [{"summary": "Repeat supplier concentration"}],
            "next_checks": [],
        }
        tool_trace = [
            {
                "tool": "awards",
                "status": "success",
                "cli_equivalent": 'probid awards --agency "DICT"',
                "payload": [
                    {"agency": "DICT", "supplier": "ACME CORP"},
                    {"agency": "DICT", "supplier": "BYTEWORKS"},
                ],
            },
            {
                "tool": "probe",
                "status": "success",
                "cli_equivalent": 'probid probe "laptop" --agency "DICT"',
                "payload": payload,
            },
        ]

        result = builder.build(
            intent="probe",
            query="laptop",
            payload=payload,
            tool_trace=tool_trace,
            fallback_next_actions=lambda q: [f'probid probe "{q}" --why'],
        )

        self.assertIn("steps_executed=2", result["evidence"])
        self.assertIn("tools_executed=awards,probe", result["evidence"])
        self.assertIn("awards_rows=2", result["evidence"])
        self.assertIn("awards_agencies=1", result["evidence"])
        self.assertIn("awards_suppliers=2", result["evidence"])
        self.assertIn("Limited data volume", result["caveats"])
        self.assertEqual(result["next_actions"], ['probid probe "laptop" --why'])

    def test_build_enriches_supplier_profile_payload(self):
        builder = ResponseBuilder()
        payload = {
            "stats": {
                "total_awards": 4,
                "total_value": 1250000,
                "agency_count": 2,
                "agencies": ["DICT", "DepEd"],
            },
            "awards": [{"ref_no": "A1"}, {"ref_no": "A2"}],
        }
        tool_trace = [
            {
                "tool": "supplier",
                "status": "success",
                "cli_equivalent": 'probid supplier "ACME CORP"',
                "payload": payload,
            },
            {
                "tool": "network",
                "status": "success",
                "cli_equivalent": 'probid network "ACME CORP"',
                "payload": {
                    "supplier": "ACME CORP",
                    "agencies_served": ["DICT", "DepEd"],
                    "competitors": [{"supplier": "BYTEWORKS", "shared_agencies": 2}],
                },
            },
        ]

        result = builder.build(
            intent="supplier",
            query="ACME CORP",
            payload=payload,
            tool_trace=tool_trace,
        )

        self.assertIn("tools_executed=supplier,network", result["evidence"])
        self.assertIn("total_awards=4", result["evidence"])
        self.assertIn("network_agencies=2", result["evidence"])
        self.assertIn("network_competitors=1", result["evidence"])
        self.assertTrue(any("ACME CORP" in finding["summary"] for finding in result["findings"]))
        self.assertIn('probid network "ACME CORP"', result["next_actions"])

    def test_build_enriches_overprice_payload(self):
        builder = ResponseBuilder()
        payload = {
            "category": "laptop",
            "threshold": 200,
            "results": [
                {
                    "category": "IT Equipment",
                    "sample_count": 3,
                    "min_price": 50000,
                    "max_price": 180000,
                }
            ],
        }

        result = builder.build(
            intent="overprice",
            query="laptop",
            payload=payload,
            tool_trace=[
                {
                    "tool": "overprice",
                    "status": "success",
                    "cli_equivalent": 'probid overprice "laptop" --threshold 200',
                    "payload": payload,
                }
            ],
        )

        self.assertIn("overprice_result_count=1", result["evidence"])
        self.assertIn("overprice_threshold_pct=200", result["evidence"])
        self.assertTrue(any("Top budget-spread candidate" in finding["summary"] for finding in result["findings"]))
        self.assertIn('probid probe "laptop" --why', result["next_actions"])

    def test_build_probe_includes_finding_evidence_for_explanation_memory(self):
        builder = ResponseBuilder()
        payload = {
            "summary": {
                "records_scanned": 8,
                "agencies_touched": 1,
                "data_quality_note": "Limited data volume",
            },
            "findings": [
                {
                    "summary": "ACME CORP won 3 awards across 1 agencies.",
                    "evidence": {"supplier": "ACME CORP", "award_count": 3},
                    "refs": ["A-100"],
                }
            ],
            "next_checks": [],
        }

        result = builder.build(
            intent="probe",
            query="laptop",
            payload=payload,
            tool_trace=[
                {
                    "tool": "probe",
                    "status": "success",
                    "cli_equivalent": 'probid probe "laptop"',
                    "payload": payload,
                }
            ],
            fallback_next_actions=lambda q: [f'probid probe "{q}" --why'],
        )

        self.assertEqual(
            result["findings"][0]["summary"],
            "ACME CORP won 3 awards across 1 agencies.",
        )
        self.assertEqual(result["findings"][0]["evidence"]["supplier"], "ACME CORP")


if __name__ == "__main__":
    unittest.main()
