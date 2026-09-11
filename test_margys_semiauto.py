import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


from margys_semiauto import (
    KPI,
    analyze_export,
    build_analysis_payload,
    classify_note,
    load_export,
    summarize,
    validate_reconciliation,
)


class MetricTests(unittest.TestCase):
    def test_summary_recomputes_ratio_metrics_from_sums(self):
        rows = [
            {"spend": 100.0, "visits": 10.0, "gmv": 200.0},
            {"spend": 300.0, "visits": 5.0, "gmv": 100.0},
        ]

        result = summarize(rows)

        self.assertEqual(result["spend"], 400.0)
        self.assertEqual(result["visits"], 15.0)
        self.assertAlmostEqual(result["cpuv"], 400.0 / 15.0)
        self.assertAlmostEqual(result["roi"], 300.0 / 400.0)


class ClassificationTests(unittest.TestCase):
    def test_high_roi_note_scales_even_when_cpuv_is_above_50(self):
        result = classify_note(
            spend=1200,
            visits=10,
            gmv=6000,
            active_days=14,
            kpi=KPI,
        )

        self.assertEqual(result["decision"], "加量")
        self.assertEqual(result["reason_code"], "ROI>4")

    def test_under_800_is_sample_insufficient_not_pause(self):
        result = classify_note(
            spend=500,
            visits=2,
            gmv=0,
            active_days=5,
            kpi=KPI,
        )

        self.assertEqual(result["decision"], "样本不足")

    def test_mature_low_roi_high_cpuv_note_pauses(self):
        result = classify_note(
            spend=1600,
            visits=20,
            gmv=1000,
            active_days=14,
            kpi=KPI,
        )

        self.assertEqual(result["decision"], "暂停")


class ExportContractTests(unittest.TestCase):
    def test_load_export_drops_total_row_and_rejects_missing_metric(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "notes.csv"
            with path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["时间", "笔记ID", "消费", "行业商品进店量30日"])
                writer.writerow(["合计1条记录", "-", "100", "2"])
                writer.writerow(["2026-08-01", "note-1", "100", "2"])

            with self.assertRaisesRegex(ValueError, "行业商品GMV"):
                load_export(path, "note")

    def test_note_export_groups_by_note_and_recomputes_metrics(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "notes.csv"
            with path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(
                    [
                        "时间",
                        "笔记ID",
                        "消费",
                        "行业商品进店量30日",
                        "行业商品GMV（30日)",
                    ]
                )
                writer.writerow(["合计2条记录", "-", "400", "15", "300"])
                writer.writerow(["2026-08-01", "note-1", "100", "10", "200"])
                writer.writerow(["2026-08-02", "note-1", "300", "5", "100"])

            export = load_export(path, "note")
            result = analyze_export(export)

            self.assertEqual(len(result), 1)
            self.assertEqual(result.iloc[0]["active_days"], 2)
            self.assertAlmostEqual(result.iloc[0]["cpuv"], 400 / 15)
            self.assertAlmostEqual(result.iloc[0]["roi"], 300 / 400)

    def test_candidate_actions_have_fixed_review_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "notes.csv"
            with path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["时间", "笔记ID", "消费", "行业商品进店量30日", "行业商品GMV（30日)"])
                writer.writerow(["合计4条记录", "-", "4100", "64", "6400"])
                writer.writerow(["2026-08-01", "scale", "1200", "10", "6000"])
                writer.writerow(["2026-08-01", "hold", "1200", "30", "400"])
                writer.writerow(["2026-08-01", "pause", "1600", "20", "0"])
                writer.writerow(["2026-08-01", "sample", "100", "4", "0"])

            decisions = analyze_export(load_export(path, "note"))["decision"].tolist()

            self.assertEqual(decisions, ["加量", "观察", "暂停", "样本不足"])

    def test_reconciliation_rejects_silent_partial_data(self):
        with self.assertRaisesRegex(ValueError, "合计对账失败"):
            validate_reconciliation(
                computed={"spend": 80.0, "visits": 2.0, "gmv": 100.0},
                reported={"spend": 100.0, "visits": 2.0, "gmv": 100.0},
                source_name="notes.csv",
            )

    def test_audience_export_does_not_exactly_reconcile_gmv_derived_from_rounded_roi(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "audience.csv"
            with path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(
                    [
                        "日期",
                        "人群包ID",
                        "人群包名称",
                        "消费",
                        "店铺访问量(30日)",
                        "店铺成交ROI(30日)",
                    ]
                )
                writer.writerow(["合计2条记录", "-", "-", "100", "10", "3.11"])
                writer.writerow(["20260801", "1", "人群A", "60", "6", "3.10"])
                writer.writerow(["20260801", "2", "人群B", "40", "4", "3.13"])

            result = analyze_export(load_export(path, "audience"))

            self.assertEqual(len(result), 2)

    def test_payload_keeps_each_source_period_separate(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            note_path = tmp_path / "notes.csv"
            creative_path = tmp_path / "creatives.csv"
            for path, entity_column, entity_value, start_date in (
                (note_path, "笔记ID", "note-1", "2026-08-18"),
                (creative_path, "创意ID", "creative-1", "2026-08-01"),
            ):
                name_column = [] if entity_column == "笔记ID" else ["创意名称"]
                header = ["时间", entity_column, *name_column, "消费", "行业商品进店量30日", "行业商品GMV（30日)"]
                total = ["合计1条记录", "-", *(["-"] if name_column else []), "100", "10", "300"]
                row = [start_date, entity_value, *(["创意A"] if name_column else []), "100", "10", "300"]
                with path.open("w", encoding="utf-8-sig", newline="") as handle:
                    writer = csv.writer(handle)
                    writer.writerow(header)
                    writer.writerow(total)
                    writer.writerow(row)

            payload = build_analysis_payload(
                {
                    "note": load_export(note_path, "note"),
                    "creative": load_export(creative_path, "creative"),
                }
            )

            self.assertEqual(payload["sources"]["note"]["date_start"], "2026-08-18")
            self.assertEqual(payload["sources"]["creative"]["date_start"], "2026-08-01")

    def test_cli_writes_json_payload_for_explicit_inputs(self):
        output = Path(tempfile.gettempdir()) / "margys-semiauto-test-output.json"
        if output.exists():
            output.unlink()
        command = [
            sys.executable,
            str(Path(__file__).parents[1] / "margys_semiauto.py"),
            "--creative",
            "/Users/ouyangyang/Downloads/创意-投放数据 (22).csv",
            "--note",
            "/Users/ouyangyang/Downloads/笔记-投放数据.csv",
            "--audience",
            "/Users/ouyangyang/Downloads/人群包报表 (1).csv",
            "--keyword",
            "/Users/ouyangyang/Downloads/关键词-投放数据.csv",
            "--json-out",
            str(output),
        ]

        subprocess.run(command, check=True, capture_output=True, text=True)
        payload = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(payload["project"], "MARGY'S骨胶原面膜")
        self.assertEqual(payload["sources"]["creative"]["rows"], 1987)


if __name__ == "__main__":
    unittest.main()
