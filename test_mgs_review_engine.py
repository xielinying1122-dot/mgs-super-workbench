import pandas as pd

from mgs_review_engine import (
    build_review_payload,
    canonical_note_url,
    classify_performance,
    classify_creator,
    parse_note_match_table,
)


def project_config(**overrides):
    project = {
        "project_id": "mgs-margys",
        "name": "MGS",
        "display_name": "MARGY'S 骨胶原面膜",
        "review_rules": {
            "min_creator_spend": 100,
            "min_creator_visits": 20,
            "min_creator_active_days": 2,
            "min_creator_impressions": 1000,
        },
        "attribution_windows": {"gmv_days": 30, "visits_days": 15},
        "metric_contract": {},
    }
    project.update(overrides)
    return project


def creative_frame():
    return pd.DataFrame(
        [
            {
                "date": pd.Timestamp("2026-09-01"), "point": "信息流", "note_id": "n1",
                "note_name": "笔记一", "creator_name": "达人甲", "spend": 120,
                "impressions": 1200, "clicks": 120, "visits": 20, "gmv": 360,
                "likes": 10, "saves": 5, "comments": 2, "follows": 1, "shares": 1,
            },
            {
                "date": pd.Timestamp("2026-09-02"), "point": "搜索", "note_id": "n1",
                "note_name": "笔记一", "creator_name": "达人甲", "spend": 80,
                "impressions": 800, "clicks": 40, "visits": 10, "gmv": 80,
                "likes": 4, "saves": 2, "comments": 1, "follows": 0, "shares": 0,
            },
            {
                "date": pd.Timestamp("2026-09-02"), "point": "全站", "note_id": "n2",
                "note_name": "笔记二", "creator_name": "达人乙", "spend": 50,
                "impressions": 500, "clicks": 20, "visits": 2, "gmv": 10,
            },
        ]
    )


def test_canonical_note_url_removes_query_and_fragment():
    assert canonical_note_url("n1", "https://www.xiaohongshu.com/explore/n1?xsec_token=secret&foo=1#part") == "https://www.xiaohongshu.com/explore/n1"
    assert canonical_note_url("n1", "") == ""


def test_canonical_note_url_rejects_non_http_links():
    assert canonical_note_url("n1", "javascript:alert(1)") == ""
    assert canonical_note_url("n1", "//www.xiaohongshu.com/explore/n1") == ""
    assert canonical_note_url("n1", "https://evil.example/explore/n1") == ""


def test_parse_note_match_table_accepts_second_row_headers_and_both_sides():
    frame = pd.DataFrame([
        ["说明", "", "", "", "", ""],
        ["笔记ID", "达人名称", "笔记链接", "笔记ID", "达人名称", "笔记链接"],
        ["n1", "达人甲", "https://www.xiaohongshu.com/explore/n1?x=1", "n2", "达人乙", "https://www.xiaohongshu.com/explore/n2"],
        ["n1", "达人甲", "", "n3", "达人丙", ""],
    ])
    parsed = parse_note_match_table(frame, "匹配表.xlsx")
    assert parsed["n1"]["creator_name"] == "达人甲"
    assert parsed["n1"]["note_url"] == "https://www.xiaohongshu.com/explore/n1"
    assert parsed["n1"]["match_source"] == "left"
    assert parsed["n2"]["match_source"] == "right"
    assert parsed["n3"]["note_url"] == ""


def test_parse_note_match_table_locates_right_side_columns_by_header_name():
    """The export's right side is [creator, url, note_id], unlike the left side."""
    frame = pd.DataFrame([
        ["说明", "", "", "", "", ""],
        ["笔记ID", "昵称", "发布链接", "昵称", "发布连接", "笔记ID"],
        ["left-1", "达人甲", "https://www.xiaohongshu.com/explore/left-1?x=1", "达人乙", "https://www.xiaohongshu.com/explore/right-1?x=2", "right-1"],
    ])

    parsed = parse_note_match_table(frame, "匹配表.xlsx")

    assert parsed["right-1"]["creator_name"] == "达人乙"
    assert parsed["right-1"]["note_url"] == "https://www.xiaohongshu.com/explore/right-1"
    assert parsed["right-1"]["match_source"] == "right"


def test_build_review_payload_aggregates_creators_by_point_without_double_counting_other_frames():
    payload = build_review_payload(
        {"creative": creative_frame(),
         "targeting": pd.DataFrame([{"date": pd.Timestamp("2026-09-01"), "targeting": "人群A", "spend": 999, "visits": 99, "gmv": 9999}]),
         "keyword": pd.DataFrame([{"date": pd.Timestamp("2026-09-01"), "keyword": "面膜", "spend": 888, "visits": 88, "gmv": 8888}])},
        project_config(), start="2026-09-01", end="2026-09-02",
    )
    assert payload["summary"]["spend"] == 250
    assert len(payload["creator_breakdown"]) == 3
    assert {row["point"] for row in payload["creator_breakdown"] if row["creator_name"] == "达人甲"} == {"信息流", "搜索"}
    assert payload["creator_reviews"][0]["evidence_level"] in {"derived", "observed"}
    assert payload["attribution_windows"] == {"gmv_days": 30, "visits_days": 15}


def test_classify_creator_marks_insufficient_sample_as_observation():
    result = classify_creator({"spend": 50, "visits": 30, "active_days": 3, "impressions": 500, "roi": 4, "cpuv": 2}, project_config())
    assert result["label"] == "观察"
    assert result["evidence_level"] == "derived"


def test_performance_classification_returns_actionable_labels():
    project = project_config(
        kpi={"roi_target": 2.5, "cpuv_target": 35},
        action_rules={
            "high_roi": 4,
            "scale_cpuv": 50,
            "scale_visits": 20,
            "pause_roi": 1.5,
            "pause_cpuv": 50,
            "min_action_spend": 100,
        },
    )

    winner = classify_performance({"spend": 500, "visits": 25, "roi": 4.5, "cpuv": 20}, project)
    loser = classify_performance({"spend": 300, "visits": 2, "roi": 0.5, "cpuv": 150}, project)
    small = classify_performance({"spend": 30, "visits": 1, "roi": 0, "cpuv": 30}, project)

    assert winner["label"] == "优质·可复用"
    assert winner["action"] == "小步放量"
    assert loser["label"] == "淘汰候选"
    assert loser["action"] == "降预算/暂停"
    assert small["label"] == "观察"


def test_review_payload_labels_targeting_keywords_and_notes_and_builds_directions():
    project = project_config(
        kpi={"roi_target": 2.5, "cpuv_target": 35},
        action_rules={
            "high_roi": 4,
            "scale_cpuv": 50,
            "scale_visits": 20,
            "pause_roi": 1.5,
            "pause_cpuv": 50,
            "min_action_spend": 100,
        },
    )
    creative = pd.DataFrame([
        {"date": "2026-09-01", "point": "信息流", "creator_name": "达人甲", "note_id": "优质笔记", "note_name": "优质笔记", "spend": 500, "visits": 25, "gmv": 2500, "impressions": 5000, "clicks": 200},
        {"date": "2026-09-01", "point": "信息流", "creator_name": "达人乙", "note_id": "低效笔记", "note_name": "低效笔记", "spend": 300, "visits": 2, "gmv": 100, "impressions": 3000, "clicks": 100},
    ])
    targeting = pd.DataFrame([
        {"date": "2026-09-01", "targeting": "优质人群", "spend": 500, "visits": 25, "gmv": 2500, "impressions": 5000},
        {"date": "2026-09-01", "targeting": "低效人群", "spend": 300, "visits": 2, "gmv": 100, "impressions": 3000},
    ])
    keyword = pd.DataFrame([
        {"date": "2026-09-01", "keyword": "低效词", "spend": 300, "visits": 2, "gmv": 100, "impressions": 3000},
    ])

    payload = build_review_payload(
        {"creative": creative, "targeting": targeting, "keyword": keyword},
        project, start="2026-09-01", end="2026-09-01",
    )

    assert {row["targeting"]: row["label"] for row in payload["targeting_breakdown"]}["低效人群"] == "淘汰候选"
    assert payload["keyword_breakdown"][0]["action"] == "降预算/暂停"
    assert {row["note_id"]: row["label"] for row in payload["note_breakdown"]}["优质笔记"] == "优质·可复用"
    assert payload["adjustment_directions"]
    assert payload["decision_summary"]["loser_count"] >= 1
    assert payload["goodcases"] and payload["badcases"]
    assert payload["knowledge_hits"]
    assert payload["keyword_breakdown"][0]["keyword_category"] == "待分类"


def test_review_payload_matches_creator_to_best_targeting_and_sorts_by_spend():
    project = project_config(
        kpi={"roi_target": 2.5, "cpuv_target": 35},
        action_rules={"high_roi": 4, "scale_cpuv": 50, "scale_visits": 20, "pause_roi": 1.5, "pause_cpuv": 50, "min_action_spend": 100},
    )
    creative = pd.DataFrame([
        {"date": "2026-09-01", "point": "信息流", "campaign": "计划甲", "note_id": "n1", "creator_name": "达人甲", "spend": 200, "visits": 10, "gmv": 600, "impressions": 1000},
        {"date": "2026-09-01", "point": "信息流", "campaign": "计划乙", "note_id": "n2", "creator_name": "达人乙", "spend": 300, "visits": 20, "gmv": 900, "impressions": 1000},
    ])
    targeting = pd.DataFrame([
        {"date": "2026-09-01", "campaign": "计划甲", "note_id": "n1", "creator_name": "", "targeting": "人群A", "spend": 200, "visits": 10, "gmv": 400, "impressions": 1000},
        {"date": "2026-09-01", "campaign": "计划甲", "note_id": "n1", "creator_name": "", "targeting": "人群B", "spend": 120, "visits": 10, "gmv": 720, "impressions": 1000},
        {"date": "2026-09-01", "campaign": "计划乙", "note_id": "n2", "creator_name": "", "targeting": "人群C", "spend": 500, "visits": 20, "gmv": 1500, "impressions": 1000},
    ])

    payload = build_review_payload({"creative": creative, "targeting": targeting}, project, start="2026-09-01", end="2026-09-01")
    rows = payload["creator_targeting_breakdown"]

    assert [row["creator_name"] for row in rows] == ["达人乙", "达人甲"]
    assert next(row for row in rows if row["creator_name"] == "达人甲")["targeting"] == "人群B"
    assert [row["creator_name"] for row in payload["creator_reviews"]] == ["达人乙", "达人甲"]


def test_review_maturity_is_computed_from_as_of_date():
    from datetime import date

    windows = {"gmv_days": 30, "visits_days": 15}
    recent = build_review_payload({"creative": creative_frame()}, project_config(), today=date(2026, 9, 10))
    # 数据截止 2026-09-02，距今天 8 天，仍处 30 天 GMV 归因窗的前段。
    assert recent["data_maturity"] == "maturing"
    assert recent["data_maturity_detail"]["remaining_days"] == 22
    assert recent["data_maturity_detail"]["required_days"] == 30

    settling = build_review_payload({"creative": creative_frame()}, project_config(), today=date(2026, 9, 25))
    assert settling["data_maturity"] == "settling"

    mature = build_review_payload({"creative": creative_frame()}, project_config(), today=date(2026, 10, 15))
    assert mature["data_maturity"] == "mature"


def test_review_maturity_is_unknown_without_configured_window():
    from datetime import date

    payload = build_review_payload({"creative": creative_frame()}, project_config(attribution_windows={}), today=date(2026, 9, 10))
    assert payload["data_maturity"] == "unknown"
    assert payload["data_maturity_detail"]["reason"] == "归因窗口未配置"
