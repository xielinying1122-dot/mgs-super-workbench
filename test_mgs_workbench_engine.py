import os
import time
from pathlib import Path

import pandas as pd

from datetime import date

from mgs_workbench_engine import (
    aggregate_metrics,
    build_dashboard_payload,
    data_maturity_report,
    classify_action,
    diagnose_roi_decline,
    ingest_files,
    normalize_table,
)


def write_csv(path: Path, rows: list[list[object]]) -> None:
    pd.DataFrame(rows[1:], columns=rows[0]).to_csv(path, index=False, encoding="utf-8-sig")


def test_normalize_removes_total_row_and_preserves_mgs_metrics(tmp_path):
    path = tmp_path / "创意-投放数据.csv"
    write_csv(
        path,
        [
            ["时间", "投放类型", "计划名称", "笔记ID", "消费", "点击量", "行业商品进店量30日", "店铺访问量(15日)", "行业商品GMV（30日)"],
            ["合计1条记录", "全站", "合计", "-", "100", "10", "5", "5", "300"],
            ["2026-09-01", "全站", "计划A", "note-1", "100", "10", "5", "5", "300"],
        ],
    )

    result = normalize_table(pd.read_csv(path, encoding="utf-8-sig"), path, "creative")

    assert len(result.frame) == 1
    assert result.frame.iloc[0]["spend"] == 100
    assert result.frame.iloc[0]["visits"] == 5
    assert result.frame.iloc[0]["gmv"] == 300
    assert bool(result.frame.iloc[0]["gmv_is_approximate"]) is False


def test_overlapping_snapshots_keep_latest_file(tmp_path):
    old_path = tmp_path / "old.csv"
    new_path = tmp_path / "new.csv"
    header = ["时间", "投放类型", "计划名称", "笔记ID", "消费", "行业商品进店量30日", "行业商品GMV（30日)"]
    write_csv(old_path, [header, ["2026-09-01", "全站", "计划A", "note-1", "100", "5", "200"]])
    time.sleep(0.01)
    write_csv(new_path, [header, ["2026-09-01", "全站", "计划A", "note-1", "140", "7", "350"]])
    os.utime(old_path, (time.time() - 10, time.time() - 10))

    result = ingest_files([old_path, new_path])

    frame = result.frames["creative"]
    assert len(frame) == 1
    assert frame.iloc[0]["spend"] == 140
    assert frame.iloc[0]["source_file"] == "new.csv"


def test_aggregate_recomputes_roi_and_cpuv_from_additive_values():
    frame = pd.DataFrame(
        [
            {"date": "2026-09-01", "point": "全站", "campaign": "A", "note_id": "n1", "spend": 100, "visits": 10, "gmv": 300, "impressions": 1000, "clicks": 100, "interactions": 10},
            {"date": "2026-09-02", "point": "全站", "campaign": "A", "note_id": "n1", "spend": 300, "visits": 5, "gmv": 100, "impressions": 1000, "clicks": 50, "interactions": 5},
        ]
    )
    frame["date"] = pd.to_datetime(frame["date"])

    result = aggregate_metrics(frame, ["point", "campaign"])

    row = result.iloc[0]
    assert row["spend"] == 400
    assert row["visits"] == 15
    assert row["gmv"] == 400
    assert row["roi"] == 1
    assert row["cpuv"] == 400 / 15


def test_audience_roi_without_gmv_is_marked_approximate(tmp_path):
    path = tmp_path / "人群包报表.csv"
    write_csv(
        path,
        [
            ["日期", "人群包ID", "人群包名称", "精准定向", "消费", "店铺访问量(15日)", "店铺成交ROI(30日)"],
            ["20260901", "aud-1", "人群A", "人群A", "100", "10", "3"],
        ],
    )

    result = ingest_files([path])

    row = result.frames["targeting"].iloc[0]
    assert row["gmv"] == 300
    assert bool(row["gmv_is_approximate"]) is True
    assert any("近似" in issue["message"] for issue in result.issues)


def test_diagnosis_identifies_low_quality_mix_shift():
    baseline = pd.DataFrame(
        [
            {"date": "2026-08-25", "point": "高效点位", "spend": 900, "visits": 30, "gmv": 3600, "impressions": 10000, "clicks": 1000},
            {"date": "2026-08-25", "point": "低效点位", "spend": 100, "visits": 5, "gmv": 50, "impressions": 2000, "clicks": 200},
        ]
    )
    current = pd.DataFrame(
        [
            {"date": "2026-09-03", "point": "高效点位", "spend": 500, "visits": 15, "gmv": 2000, "impressions": 7000, "clicks": 700},
            {"date": "2026-09-03", "point": "低效点位", "spend": 900, "visits": 10, "gmv": 450, "impressions": 18000, "clicks": 1800},
        ]
    )
    for frame in (baseline, current):
        frame["date"] = pd.to_datetime(frame["date"])

    reasons = diagnose_roi_decline(current, baseline)

    assert any(reason["code"] == "budget_mix" for reason in reasons)
    assert any(reason["confidence"] in {"高", "中"} for reason in reasons)


def test_dashboard_payload_has_actions_and_evidence():
    frame = pd.DataFrame(
        [
            {"date": pd.Timestamp("2026-09-01"), "point": "全站", "campaign": "计划A", "unit": "单元A", "note_id": "note-1", "note_name": "笔记A", "targeting": "智能定向", "keyword": "", "spend": 1000, "visits": 10, "gmv": 100, "impressions": 10000, "clicks": 500, "interactions": 20, "source_file": "mgs.xlsx", "source_sheet": "日报数据底表", "source_kind": "creative"},
            {"date": pd.Timestamp("2026-09-01"), "point": "信息流", "campaign": "计划B", "unit": "单元B", "note_id": "note-2", "note_name": "笔记B", "targeting": "人群B", "keyword": "", "spend": 1000, "visits": 30, "gmv": 5000, "impressions": 10000, "clicks": 500, "interactions": 20, "source_file": "mgs.xlsx", "source_sheet": "日报数据底表", "source_kind": "creative"},
        ]
    )
    result = build_dashboard_payload({"creative": frame}, start="2026-09-01", end="2026-09-01")

    assert result["kpis"]["roi"] == (5100 / 2000)
    assert result["actions"]
    assert all(action["evidence"]["source_file"] for action in result["actions"])
    assert result["points"]


def test_dashboard_comparison_uses_full_frame_and_keeps_drilldowns():
    frame = pd.DataFrame(
        [
            {"date": pd.Timestamp("2026-08-31"), "point": "全站", "campaign": "旧计划", "note_id": "n1", "spend": 1000, "visits": 40, "gmv": 3000, "impressions": 10000, "clicks": 500, "interactions": 10},
            {"date": pd.Timestamp("2026-09-01"), "point": "全站", "campaign": "新计划", "note_id": "n2", "spend": 1000, "visits": 10, "gmv": 500, "impressions": 10000, "clicks": 500, "interactions": 10},
        ]
    )
    result = build_dashboard_payload(
        {"creative": frame},
        start="2026-09-01",
        end="2026-09-01",
        baseline_start="2026-08-31",
        baseline_end="2026-08-31",
    )

    assert result["baseline_kpis"]["roi"] == 3
    assert any(reason["code"] == "visit_efficiency" for reason in result["reasons"])
    assert len(result["drilldowns"]["creative"]) == 1


def test_dashboard_payload_includes_week_and_day_period_comparisons():
    frame = pd.DataFrame(
        [
            {"date": pd.Timestamp("2026-08-31"), "point": "全站", "campaign": "上周一", "spend": 100, "visits": 5, "gmv": 200, "impressions": 1000, "clicks": 50},
            {"date": pd.Timestamp("2026-09-06"), "point": "全站", "campaign": "上周日", "spend": 200, "visits": 5, "gmv": 400, "impressions": 2000, "clicks": 100},
            {"date": pd.Timestamp("2026-09-07"), "point": "全站", "campaign": "本周一", "spend": 100, "visits": 5, "gmv": 300, "impressions": 1000, "clicks": 50},
        ]
    )

    result = build_dashboard_payload(
        {"creative": frame},
        start="2026-09-01",
        end="2026-09-07",
    )

    comparisons = result["period_comparisons"]
    assert comparisons["anchor_date"] == "2026-09-07"
    assert comparisons["week"]["current"]["start"] == "2026-09-07"
    assert comparisons["week"]["current"]["end"] == "2026-09-07"
    assert comparisons["week"]["previous"]["start"] == "2026-08-31"
    assert comparisons["week"]["previous"]["end"] == "2026-09-06"
    assert comparisons["week"]["current"]["spend"] == 100
    assert comparisons["week"]["previous"]["spend"] == 300
    assert comparisons["week"]["current"]["roi"] == 3
    assert comparisons["week"]["previous"]["roi"] == 2
    assert comparisons["day"]["current"]["gmv"] == 300
    assert comparisons["day"]["previous"]["gmv"] == 400
    assert comparisons["day"]["changes"]["roi"] == 0.5


def test_drilldowns_keep_all_rows_when_action_queue_is_capped():
    rows = []
    for index in range(85):
        rows.append(
            {
                "date": pd.Timestamp("2026-09-01"),
                "point": "全站",
                "campaign": f"计划-{index}",
                "note_id": f"note-{index}",
                "note_name": f"笔记-{index}",
                "spend": 100,
                "visits": 1,
                "gmv": 100,
                "impressions": 1000,
                "clicks": 20,
                "interactions": 1,
            }
        )
    frame = pd.DataFrame(rows)

    result = build_dashboard_payload({"creative": frame}, start="2026-09-01", end="2026-09-01")

    assert len(result["actions"]) == 80
    assert len(result["drilldowns"]["creative"]) == 85


def test_creative_frame_is_also_available_as_note_level_drilldown():
    frame = pd.DataFrame(
        [
            {
                "date": pd.Timestamp("2026-09-01"),
                "point": "全站",
                "campaign": "计划A",
                "note_id": "note-1",
                "note_name": "笔记A",
                "spend": 100,
                "visits": 5,
                "gmv": 300,
                "impressions": 1000,
                "clicks": 100,
                "interactions": 10,
                "source_file": "mgs.xlsx",
                "source_sheet": "日报数据底表",
            },
            {
                "date": pd.Timestamp("2026-09-02"),
                "point": "信息流",
                "campaign": "计划B",
                "note_id": "note-1",
                "note_name": "笔记A",
                "spend": 200,
                "visits": 10,
                "gmv": 100,
                "impressions": 2000,
                "clicks": 150,
                "interactions": 15,
                "source_file": "mgs.xlsx",
                "source_sheet": "日报数据底表",
            },
        ]
    )

    result = build_dashboard_payload({"creative": frame}, start="2026-09-01", end="2026-09-02")

    notes = result["drilldowns"]["note"]
    assert len(notes) == 1
    assert notes[0]["note_id"] == "note-1"
    assert notes[0]["spend"] == 300
    assert notes[0]["gmv"] == 400
    assert notes[0]["roi"] == 400 / 300


def test_note_drilldown_prefers_explicit_note_frame_when_available():
    creative = pd.DataFrame(
        [{"date": pd.Timestamp("2026-09-01"), "point": "全站", "campaign": "计划A", "note_id": "n1", "spend": 100, "visits": 5, "gmv": 300}]
    )
    note = pd.DataFrame(
        [{"date": pd.Timestamp("2026-09-01"), "point": "全站", "campaign": "计划A", "note_id": "n1", "note_name": "笔记A", "spend": 120, "visits": 6, "gmv": 360}]
    )

    result = build_dashboard_payload({"creative": creative, "note": note}, start="2026-09-01", end="2026-09-01")

    assert result["drilldowns"]["note"][0]["spend"] == 120


def test_dashboard_drilldowns_use_one_primary_entity_per_level():
    base = {
        "date": pd.Timestamp("2026-09-01"),
        "point": "全站",
        "spend": 100,
        "visits": 5,
        "gmv": 300,
        "impressions": 1000,
        "clicks": 100,
        "interactions": 10,
    }
    creative = pd.DataFrame([
        {**base, "campaign": "计划A", "note_id": "note-1", "note_name": "笔记一"},
        {**base, "point": "搜索", "campaign": "计划A", "note_id": "note-2", "note_name": "笔记二"},
    ])
    targeting = pd.DataFrame([
        {**base, "campaign": "计划A", "note_id": "note-1", "targeting": "高意向人群"},
        {**base, "campaign": "计划B", "note_id": "note-2", "targeting": "高意向人群"},
    ])
    keyword = pd.DataFrame([
        {**base, "campaign": "搜索计划A", "note_id": "note-1", "keyword": "骨胶原面膜"},
        {**base, "campaign": "搜索计划B", "note_id": "note-2", "keyword": "骨胶原面膜"},
    ])

    result = build_dashboard_payload(
        {"creative": creative, "targeting": targeting, "keyword": keyword},
        start="2026-09-01",
        end="2026-09-01",
    )

    assert len(result["plans"]) == 1
    assert result["plans"][0]["entity_name"] == "计划A"
    assert len(result["drilldowns"]["note"]) == 2
    assert {row["entity_name"] for row in result["drilldowns"]["note"]} == {"note-1", "note-2"}
    assert len(result["drilldowns"]["targeting"]) == 1
    assert result["drilldowns"]["targeting"][0]["entity_name"] == "高意向人群"
    assert len(result["drilldowns"]["keyword"]) == 1
    assert result["drilldowns"]["keyword"][0]["entity_name"] == "骨胶原面膜"
    assert set(result["action_groups"]) == {"plans", "notes", "targeting", "keywords"}


def test_high_roi_with_expensive_visits_is_not_marked_for_scale():
    result = classify_action(spend=1000, visits=10, gmv=5000, active_days=14)

    assert result["action"] == "观察"
    assert "CPUV" in result["reason"]


def test_custom_action_rules_drive_decision_and_reason_text():
    result = classify_action(
        spend=100,
        visits=10,
        gmv=300,
        active_days=4,
        action_rules={
            "high_roi": 9,
            "scale_roi": 8,
            "scale_cpuv": 9,
            "scale_visits": 4,
            "entry_cpuv": 6,
            "entry_roi": 2,
            "test_spend": 50,
            "test_days": 3,
            "pause_roi": 3.5,
            "pause_cpuv": 9,
            "min_action_spend": 20,
        },
    )

    assert result["action"] == "暂停/降预算"
    assert "3.5" in result["reason"]
    assert "1.5" not in result["reason"]


def test_empty_project_action_rules_do_not_inherit_mgs_decision_thresholds():
    frame = pd.DataFrame([
        {
            "date": pd.Timestamp("2026-09-01"),
            "point": "全站",
            "campaign": "待配置项目计划",
            "spend": 1000,
            "visits": 10,
            "gmv": 100,
            "impressions": 1000,
            "clicks": 100,
        }
    ])

    result = build_dashboard_payload(
        {"creative": frame},
        start="2026-09-01",
        end="2026-09-01",
        kpi={"roi_target": 1.2, "cpuv_target": 40},
        action_rules={},
        project={
            "project_id": "new-project",
            "name": "新项目",
            "display_name": "新项目商品",
            "kpi": {"roi_target": 1.2, "cpuv_target": 40},
            "action_rules": {},
            "metric_contract": {},
            "attribution_windows": {},
            "modules": {},
        },
    )

    assert result["action_rules"] == {}
    assert result["plans"][0]["action"] == "待配置"
    assert "动作规则" in result["plans"][0]["reason"]
    assert result["targets"]["roi_target"] == 1.2
    assert "pause_roi" not in result["targets"]


def test_project_diagnosis_does_not_use_mgs_roi_target_when_missing():
    baseline = pd.DataFrame([
        {"date": pd.Timestamp("2026-08-31"), "point": "高效", "spend": 900, "visits": 30, "gmv": 3600, "clicks": 90},
        {"date": pd.Timestamp("2026-08-31"), "point": "待观察", "spend": 100, "visits": 5, "gmv": 100, "clicks": 10},
    ])
    current = pd.DataFrame([
        {"date": pd.Timestamp("2026-09-01"), "point": "高效", "spend": 100, "visits": 4, "gmv": 400, "clicks": 10},
        {"date": pd.Timestamp("2026-09-01"), "point": "待观察", "spend": 900, "visits": 45, "gmv": 1620, "clicks": 90},
    ])

    result = diagnose_roi_decline(current, baseline, kpi={}, action_rules={})

    assert not any(item["code"] == "budget_mix" for item in result)


def test_dashboard_uses_project_kpi_and_metadata_when_provided():
    frame = pd.DataFrame([
        {
            "date": pd.Timestamp("2026-09-01"),
            "point": "全站",
            "campaign": "项目B计划",
            "spend": 100,
            "visits": 10,
            "gmv": 300,
            "impressions": 1000,
            "clicks": 100,
        }
    ])

    result = build_dashboard_payload(
        {"creative": frame},
        start="2026-09-01",
        end="2026-09-01",
        kpi={"roi_target": 4, "cpuv_target": 10},
        project={
            "project_id": "project-b",
            "name": "项目B",
            "display_name": "项目B商品",
            "metric_contract": {"roi": "gmv / spend"},
            "attribution_windows": {"gmv_days": 7},
            "modules": {"规划": True},
        },
    )

    assert result["project_id"] == "project-b"
    assert result["project"] == "项目B · 项目B商品"
    assert result["targets"]["roi_target"] == 4
    assert result["metric_contract"]["roi"] == "gmv / spend"
    assert result["attribution_windows"]["gmv_days"] == 7
    assert result["modules"]["规划"] is True


def test_data_maturity_report_tracks_attribution_window_progress():
    windows = {"gmv_days": 30, "visits_days": 15}
    # 数据截止 2026-09-02：8 天未过窗口一半，23 天过半，43 天已过满 30 天。
    assert data_maturity_report("2026-09-02", windows, today=date(2026, 9, 10))["level"] == "maturing"
    assert data_maturity_report("2026-09-02", windows, today=date(2026, 9, 25))["level"] == "settling"
    assert data_maturity_report("2026-09-02", windows, today=date(2026, 10, 15))["level"] == "mature"
    assert data_maturity_report("", windows, today=date(2026, 9, 10))["level"] == "unknown"
    assert data_maturity_report("2026-09-02", {}, today=date(2026, 9, 10))["level"] == "unknown"


def test_dashboard_payload_exposes_data_maturity():
    frame = pd.DataFrame([
        {
            "date": pd.Timestamp("2026-09-02"), "point": "全站", "campaign": "计划A",
            "note_id": "note-1", "spend": 100, "impressions": 1000, "clicks": 50,
            "visits": 8, "gmv": 300,
        }
    ])
    result = build_dashboard_payload(
        {"creative": frame},
        start="2026-09-02",
        end="2026-09-02",
        project={
            "project_id": "mgs-margys", "name": "MGS", "display_name": "MARGY\'S 骨胶原面膜",
            "metric_contract": {}, "attribution_windows": {"gmv_days": 30, "visits_days": 15},
            "modules": {},
        },
    )
    assert result["as_of_date"] == "2026-09-02"
    assert result["data_maturity"] in {"maturing", "settling", "mature"}
    assert result["data_maturity_detail"]["required_days"] == 30
    assert result["verification_status"] == "local_read_only"
