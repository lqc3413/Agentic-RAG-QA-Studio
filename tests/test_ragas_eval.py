import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


class RagasEvalTests(unittest.TestCase):
    def _load_module(self):
        import importlib.util

        module_path = ROOT_DIR / "eval" / "ragas_eval.py"
        spec = importlib.util.spec_from_file_location("ragas_eval", module_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules["ragas_eval"] = module
        spec.loader.exec_module(module)
        return module

    def test_load_cases_requires_reference_for_reference_metrics(self):
        ragas_eval = self._load_module()
        with tempfile.TemporaryDirectory() as tmp:
            cases_path = Path(tmp) / "cases.json"
            cases_path.write_text(
                json.dumps(
                    [
                        {
                            "id": "case_1",
                            "question": "What is B+ Tree?",
                            "expected_sources": ["mysql"],
                        }
                    ]
                ),
                encoding="utf-8",
            )

            with self.assertRaises(ValueError) as ctx:
                ragas_eval.load_cases(cases_path, require_reference=True)

        self.assertIn("reference", str(ctx.exception))

    def test_build_ragas_rows_uses_full_selected_content_from_trace(self):
        ragas_eval = self._load_module()
        case = ragas_eval.EvalCase(
            id="case_1",
            question="What is B+ Tree?",
            reference="B+ Tree is an index structure.",
            reference_contexts=["B+ Tree stores sorted keys."],
            expected_sources=["mysql"],
            tags=["mysql"],
        )
        result = {
            "answer": "B+ Tree is an index structure.",
            "sources": [{"source": "mysql"}],
            "retrieval_traces": [
                {
                    "selected_results": [
                        {
                            "source": "mysql",
                            "content": "FULL_CONTEXT_TEXT",
                            "content_preview": "PREVIEW_ONLY",
                        }
                    ]
                }
            ],
            "elapsed_seconds": 1.25,
        }

        row = ragas_eval.build_ragas_row(case, result)

        self.assertEqual(row["user_input"], "What is B+ Tree?")
        self.assertEqual(row["response"], "B+ Tree is an index structure.")
        self.assertEqual(row["retrieved_contexts"], ["FULL_CONTEXT_TEXT"])
        self.assertEqual(row["reference"], "B+ Tree is an index structure.")
        self.assertEqual(row["reference_contexts"], ["B+ Tree stores sorted keys."])

    def test_build_ragas_row_falls_back_to_preview_when_full_content_missing(self):
        ragas_eval = self._load_module()
        case = ragas_eval.EvalCase(
            id="case_1",
            question="What is B+ Tree?",
            reference="B+ Tree is an index structure.",
            reference_contexts=[],
            expected_sources=["mysql"],
            tags=[],
        )
        result = {
            "answer": "B+ Tree is an index structure.",
            "sources": [{"source": "mysql", "content_preview": "SOURCE_PREVIEW"}],
            "retrieval_traces": [
                {
                    "selected_results": [
                        {
                            "source": "mysql",
                            "content_preview": "TRACE_PREVIEW",
                        }
                    ]
                }
            ],
        }

        row = ragas_eval.build_ragas_row(case, result)

        self.assertEqual(row["retrieved_contexts"], ["TRACE_PREVIEW"])

    def test_run_mock_evaluation_writes_json_and_markdown_report(self):
        ragas_eval = self._load_module()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            cases_path = tmp_path / "cases.json"
            reports_dir = tmp_path / "reports"
            cases_path.write_text(
                json.dumps(
                    [
                        {
                            "id": "case_1",
                            "question": "What is B+ Tree?",
                            "reference": "B+ Tree is an index structure.",
                            "reference_contexts": ["B+ Tree is an index structure."],
                            "expected_sources": ["mysql"],
                            "tags": ["mysql"],
                        }
                    ]
                ),
                encoding="utf-8",
            )

            args = ragas_eval.parse_args(
                [
                    "--cases",
                    str(cases_path),
                    "--reports-dir",
                    str(reports_dir),
                    "--runner",
                    "mock",
                    "--evaluator",
                    "mock",
                ]
            )
            report = ragas_eval.run_eval(args)

            json_path = Path(report["run"]["json_report_path"])
            markdown_path = Path(report["run"]["markdown_report_path"])
            saved = json.loads(json_path.read_text(encoding="utf-8"))

            self.assertTrue(json_path.exists())
            self.assertTrue(markdown_path.exists())
            self.assertEqual(saved["summary"]["case_count"], 1)
            self.assertIn("faithfulness", saved["summary"]["metric_averages"])
            self.assertEqual(saved["cases"][0]["case_id"], "case_1")
            self.assertIn("Ragas Evaluation Report", markdown_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
