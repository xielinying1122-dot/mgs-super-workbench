import pandas as pd

from mgs_review_engine import build_review_payload, classify_creator


def project_config(**overrides):
    project = {
        "project_id": "mgs-margys",
        "name": "MGS",
        "review_rules": {
            "min_creator_spend": 100,
            "min_creator_visits": 20,
            "min_creator_active_days": 2,
            "min_creator_impressions": 1000,
        },
        "kpi": {"roi_target": 2.5, "cpuv_target": 35},
        "attribution_windows": {"gmv_days": 30, "visits_days": 15},
    }
    project.update(overrides)
    return project


def test_review_filters_all_breakdown_frames_to_window_and_adds_shares():
    creative = pd.DataFrame([
        {"date": "2026-09-01", "point": "信息流", "creator_name": "达人甲", "note_id": "n1", "note_name": "一", "spend": 100, "visits": 10, "gmv": 300, "impressions": 1000, "clicks": 100, "interactions": 0, "likes": 4},
        {"date": "2026-09-02", "point": "信息流", "creator_name": "达人甲", "note_id": "n1", "note_name": "一", "spend": 100, "visits": 15, "gmv": 300, "impressions": 1000, "clicks": 100, "interactions": 0, "likes": 3},
    ])
    targeting = pd.DataFrame([
        {"date": "2026-08-31", "point": "信息流", "targeting": "旧人群", "spend": 999, "visits": 99, "gmv": 9999},
        {"date": "2026-09-01", "point": "信息流", "targeting": "新人群", "spend": 10, "visits": 1, "gmv": 20},
    ])
    keyword = pd.DataFrame([
        {"date": "2026-09-01", "point": "信息流", "keyword": "面膜", "spend": 20, "visits": 2, "gmv": 60},
        {"date": "2026-09-03", "point": "信息流", "keyword": "未来", "spend": 777, "visits": 7, "gmv": 777},
    ])

    payload = build_review_payload(
        {"creative": creative, "targeting": targeting, "keyword": keyword},
        project_config(), start="2026-09-01", end="2026-09-02",
    )

    assert payload["summary"]["date_start"] == "2026-09-01"
    assert payload["summary"]["date_end"] == "2026-09-02"
    assert payload["summary"]["interactions"] == 7
    assert payload["summary"]["gmv_per_visit"] == 600 / 25
    assert payload["targeting_breakdown"][0]["spend"] == 10
    assert payload["keyword_breakdown"][0]["spend"] == 20
    assert payload["point_breakdown"][0]["spend_share"] == 1
    assert payload["point_breakdown"][0]["gmv_share"] == 1


def test_empty_creator_is_not_ranked_as_a_real_creator():
    creative = pd.DataFrame([
        {"date": "2026-09-01", "point": "信息流", "creator_name": "", "note_id": "n0", "spend": 200, "visits": 20, "gmv": 500, "impressions": 1000},
        {"date": "2026-09-01", "point": "信息流", "creator_name": "达人甲", "note_id": "n1", "spend": 200, "visits": 20, "gmv": 500, "impressions": 1000},
    ])
    payload = build_review_payload({"creative": creative}, project_config(), start="2026-09-01", end="2026-09-01")

    assert [row["creator_name"] for row in payload["creator_reviews"]] == ["达人甲"]
    assert payload["quality"]["unattributed_creator_spend"] == 200


def test_unconfigured_project_does_not_inherit_mgs_creator_thresholds():
    result = classify_creator(
        {"spend": 1000, "visits": 100, "active_days": 10, "impressions": 10000, "roi": 3, "cpuv": 20},
        {"project_id": "other", "kpi": {"roi_target": 2, "cpuv_target": 40}, "review_rules": {}},
    )

    assert result["label"] == "观察"
    assert result["reason"] == "当前项目未配置达人复盘阈值"
    assert result["evidence_level"] == "unknown"


def test_attribution_only_rows_stay_in_review_totals_and_are_flagged():
    creative = pd.DataFrame([
        {
            "date": "2026-09-01", "point": "信息流", "creator_name": "达人甲", "note_id": "paid",
            "spend": 100, "visits": 10, "gmv": 300, "impressions": 1000, "clicks": 100,
        },
        {
            "date": "2026-09-01", "point": "信息流", "creator_name": "达人甲", "note_id": "attribution-only",
            "spend": 0, "visits": 90, "gmv": 900, "impressions": 0, "clicks": 0,
        },
    ])

    payload = build_review_payload(
        {"creative": creative}, project_config(), start="2026-09-01", end="2026-09-01",
    )

    assert payload["summary"]["spend"] == 100
    assert payload["summary"]["visits"] == 100
    assert payload["summary"]["gmv"] == 1200
    assert payload["summary"]["roi"] == 12
    assert payload["summary"]["cpuv"] == 1
    assert payload["quality"]["attribution_only_row_count"] == 1
    assert payload["quality"]["attribution_only_gmv"] == 900
    assert {row["note_id"] for row in payload["note_breakdown"]} == {"paid", "attribution-only"}


def test_paid_row_filter_handles_missing_attribution_columns():
    creative = pd.DataFrame([
        {"date": "2026-09-01", "point": "信息流", "creator_name": "达人甲", "note_id": "n1", "spend": 10},
    ])
    payload = build_review_payload(
        {"creative": creative}, project_config(), start="2026-09-01", end="2026-09-01",
    )
    assert payload["summary"]["spend"] == 10
    assert payload["quality"]["attribution_only_row_count"] == 0


def test_account_scoped_auxiliary_breakdowns_keep_rows_without_account_column():
    creative = pd.DataFrame([
        {"date": "2026-09-01", "account": "红京", "campaign": "计划京", "note_id": "n-j", "spend": 200, "visits": 20, "gmv": 800, "impressions": 1000},
        {"date": "2026-09-01", "account": "红猫", "campaign": "计划猫", "note_id": "n-m", "spend": 100, "visits": 10, "gmv": 300, "impressions": 1000},
    ])
    targeting = pd.DataFrame([
        {"date": "2026-09-01", "campaign": "计划京", "note_id": "n-j", "targeting": "人群京", "spend": 200, "visits": 20, "gmv": 800},
        {"date": "2026-09-01", "campaign": "计划猫", "note_id": "n-m", "targeting": "人群猫", "spend": 100, "visits": 10, "gmv": 300},
    ])

    from mgs_workbench_app import _filter_account_frames
    scoped = _filter_account_frames({"creative": creative, "targeting": targeting}, "红京")

    assert scoped["creative"]["campaign"].tolist() == ["计划京"]
    assert scoped["targeting"]["targeting"].tolist() == ["人群京"]
