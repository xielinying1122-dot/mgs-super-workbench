"""复盘分线口径分区的回归测试。

这组测试锁的是「口径隔离」这条底线：每条投放线只能看自己的数字、比自己的
基线，跨线不许加总、不许借阈值、不许借基线。任何一条被放宽，这里就会红。
"""

from __future__ import annotations

import pandas as pd
import pytest

from mgs_review_engine import build_review_payload


def _creative() -> pd.DataFrame:
    """三条线的最小底表：红猫(历史充足) / 红京(只有一天，无历史) / 种草(无成交归因)。"""
    rows = []

    def add(account, date, spend, impressions, clicks, visits, gmv, note_id, point):
        rows.append({
            "account": account,
            "date": date,
            "spend": spend,
            "impressions": impressions,
            "clicks": clicks,
            "visits": visits,
            "gmv": gmv,
            "note_id": note_id,
            "note_name": note_id,
            "creator_name": "达人甲",
            "point": point,
            "interactions": 10,
        })

    # 红猫：基线窗口 09-01~09-03，当期窗口 09-04~09-06
    for day, (spend, imp, clk, vis, gmv) in zip(
        ("2026-09-01", "2026-09-02", "2026-09-03"),
        ((100, 1000, 100, 20, 300), (100, 1000, 100, 20, 300), (100, 1000, 100, 20, 300)),
    ):
        add("红猫", day, spend, imp, clk, vis, gmv, "note-rc-" + day, "信息流")
    for day, (spend, imp, clk, vis, gmv) in zip(
        ("2026-09-04", "2026-09-05", "2026-09-06"),
        # CTR 不变，但点击进店率腰斩 → 瓶颈应落在「点击→进店」
        ((100, 1000, 100, 10, 300), (100, 1000, 100, 10, 300), (100, 1000, 100, 10, 300)),
    ):
        add("红猫", day, spend, imp, clk, vis, gmv, "note-rc-" + day, "信息流")

    # 红京：只有当期，没有可比历史
    add("红京", "2026-09-06", 200, 2000, 100, 5, 100, "note-jd-1", "搜索")

    # 种草：没有 visits / gmv，只有内容效率
    rows.append({
        "account": "种草",
        "date": "2026-09-06",
        "spend": 50,
        "impressions": 5000,
        "clicks": 250,
        "visits": 0,
        "gmv": 0,
        "note_id": "note-sd-1",
        "note_name": "note-sd-1",
        "creator_name": "达人乙",
        "point": "信息流",
        "interactions": 60,
        "seeding_uv": 100,
    })
    return pd.DataFrame(rows)


def _project() -> dict:
    return {
        "project_id": "mgs-test",
        "kpi": {"roi_target": 2.5, "cpuv_target": 35},
        "action_rules": {
            "high_roi": 4, "scale_cpuv": 50, "scale_visits": 5,
            "pause_roi": 1.5, "pause_cpuv": 50, "min_action_spend": 100,
        },
        "attribution_windows": {"gmv_days": 30, "visits_days": 15},
        "report_lines": [
            {"line_id": "redcat", "name": "红猫", "account": "红猫", "type": "cid", "window": "range"},
            {"line_id": "redbook-jd", "name": "红京", "account": "红京", "type": "cid", "window": "range"},
            {
                "line_id": "seeding", "name": "种草", "account": "种草", "type": "seeding",
                "window": "latest_day", "cpuv_basis": "seeding_uv", "cpuv_missing": "reference",
            },
        ],
    }


@pytest.fixture()
def payload() -> dict:
    frames = {"creative": _creative()}
    return build_review_payload(
        frames,
        _project(),
        start="2026-09-04",
        end="2026-09-06",
        partition_frames=frames,
        today=pd.Timestamp("2026-09-11").date(),
    )


def test_every_configured_line_gets_its_own_partition(payload):
    partitions = payload["line_partitions"]
    assert [item["line_id"] for item in partitions] == ["redcat", "redbook-jd", "seeding"]
    assert all(item["isolated"] is True for item in partitions)
    assert payload["scope_isolation"]["line_count"] == 3


def test_partition_metrics_are_not_summed_across_lines(payload):
    redcat = next(item for item in payload["line_partitions"] if item["line_id"] == "redcat")
    # 红猫当期 3 天 × 100 = 300，红京的 200 不许被加进来
    assert redcat["metrics"]["spend"] == pytest.approx(300.0)
    assert redcat["metrics"]["gmv"] == pytest.approx(900.0)
    assert redcat["metrics"]["roi"] == pytest.approx(3.0)


def test_seeding_line_keeps_its_own_cpuv_denominator_and_produces_no_actions(payload):
    seeding = next(item for item in payload["line_partitions"] if item["line_id"] == "seeding")
    assert seeding["cpuv_basis"] == "seeding_uv"
    assert seeding["cpuv_basis_label"] == "小红星站外活跃UV（30日归因）"
    assert seeding["kpi"]["roi_target"] is None  # 不继承 CID 的 ROI 目标
    assert seeding["produces_actions"] is False  # 不产止损/放量动作
    assert seeding["actions"]["total"] == 0
    # 种草不再套 CID 的漏斗，换成独立的「内容效率」考核模型
    assert seeding["funnel"] is None
    assessment = seeding["assessment"]
    assert assessment["model"] == "seeding_content_efficiency"
    assert assessment["baseline_source"] == "none"
    assert [item["key"] for item in assessment["efficiency"]] == ["ctr", "cpc", "cpe"]
    # 无历史时三项都只能「暂不判定」，不许借其他线的基线
    assert all(item["status"] == "unknown" for item in assessment["efficiency"])
    assert all(item["baseline"] is None for item in assessment["efficiency"])
    assert assessment["offsite"]["available"] is True


def test_seeding_structure_gate_blocks_tiny_units(payload):
    """样本不达门槛的达人/定向/模式不进榜，免得几十元消耗的笔记被读成高效。"""
    seeding = next(item for item in payload["line_partitions"] if item["line_id"] == "seeding")
    blocks = seeding["assessment"]["structure"]["blocks"]
    creator_block = next(block for block in blocks if block["dimension"] == "creator_name")
    assert creator_block["count"] == 1
    assert creator_block["eligible_count"] == 0  # 消耗 50 < 种草门槛 100
    assert creator_block["top"] == []
    assert seeding["assessment"]["actions"] == []
    assert seeding["assessment"]["produces_actions"] is False


def test_seeding_efficiency_is_direction_aware():
    """CPC/CPE 越低越好：成本降了要判「优于基线」，不能因为比值小于 1 就判弱。"""
    from mgs_review_engine import _seeding_efficiency

    baseline = {"ctr": 0.05, "cpc": 2.0, "cpe": 2.0}
    entries = {item["key"]: item for item in _seeding_efficiency({"ctr": 0.05, "cpc": 1.0, "cpe": 2.0}, baseline)}
    assert entries["ctr"]["status"] == "healthy"  # 持平
    assert entries["cpc"]["status"] == "healthy"  # 成本腰斩 → 更好
    assert entries["cpe"]["status"] == "healthy"

    worse = {
        item["key"]: item
        for item in _seeding_efficiency({"ctr": 0.025, "cpc": 4.0, "cpe": 4.0}, baseline)
    }
    assert worse["ctr"]["status"] == "weak"  # CTR 跌一半
    assert worse["cpc"]["status"] == "weak"  # 成本翻倍
    assert worse["cpe"]["status"] == "weak"


def test_seeding_totals_view_is_independent_of_top_window(payload):
    """种草的全程累计视图：不随顶部窗口收窄，CID 线没有这个视图（不混口径）。"""
    seeding = next(item for item in payload["line_partitions"] if item["line_id"] == "seeding")
    totals = seeding["totals"]
    assert totals is not None
    # 顶部窗口是 09-04~09-06，但种草累计必须覆盖该线自己的整段数据
    assert totals["start"] == "2026-09-06" and totals["end"] == "2026-09-06"
    assert totals["metrics"]["spend"] == pytest.approx(50.0)
    assert totals["metrics"]["impressions"] == pytest.approx(5000.0)
    assert totals["metrics"]["seeding_uv"] == pytest.approx(100.0)
    # 累计视图刻意不设基线（数据首日之前无历史），效率只给绝对值
    assert totals["assessment"]["baseline_source"] == "none"
    assert totals["assessment"]["model"] == "seeding_content_efficiency"
    redcat = next(item for item in payload["line_partitions"] if item["line_id"] == "redcat")
    assert redcat["totals"] is None


def test_seeding_totals_rescale_when_the_line_has_multiple_days():
    """多种草日时累计视图要把整段加总，而不是只算最后一天。"""
    frames = {"creative": _creative()}
    extra = pd.DataFrame([{
        "account": "种草", "date": "2026-09-05", "spend": 150, "impressions": 9000,
        "clicks": 450, "visits": 0, "gmv": 0, "note_id": "note-sd-0",
        "note_name": "note-sd-0", "creator_name": "达人乙", "point": "信息流",
        "interactions": 90, "seeding_uv": 30,
    }])
    frames["creative"] = pd.concat([frames["creative"], extra], ignore_index=True)
    result = build_review_payload(
        frames, _project(), start="2026-09-04", end="2026-09-06",
        partition_frames=frames, today=pd.Timestamp("2026-09-11").date(),
    )
    seeding = next(item for item in result["line_partitions"] if item["line_id"] == "seeding")
    totals = seeding["totals"]
    assert totals["start"] == "2026-09-05" and totals["end"] == "2026-09-06"
    assert totals["metrics"]["spend"] == pytest.approx(200.0)
    assert totals["metrics"]["seeding_uv"] == pytest.approx(130.0)
    assert totals["metrics"]["cpe"] == pytest.approx(200.0 / 150)


def test_line_without_history_never_borrows_another_lines_baseline(payload):
    redbook = next(item for item in payload["line_partitions"] if item["line_id"] == "redbook-jd")
    assert redbook["funnel"]["baseline_source"] == "none"
    assert redbook["funnel"]["bottleneck"] == ""
    assert all(stage["baseline"] is None for stage in redbook["funnel"]["stages"])
    assert "不用其他投放线的数字代替" in redbook["funnel"]["conclusion"]


def test_bottleneck_is_located_against_the_lines_own_baseline(payload):
    redcat = next(item for item in payload["line_partitions"] if item["line_id"] == "redcat")
    funnel = redcat["funnel"]
    assert funnel["baseline_source"] == "self_history"
    # CTR 前后不变，点击进店率从 20% 掉到 10% → 瓶颈必须在「点击→进店」
    assert funnel["bottleneck"] == "click_to_visit"
    click_stage = next(stage for stage in funnel["stages"] if stage["key"] == "click_to_visit")
    assert click_stage["status"] == "bottleneck"
    assert click_stage["ratio"] == pytest.approx(0.5)
    ctr_stage = next(stage for stage in funnel["stages"] if stage["key"] == "impression_to_click")
    assert ctr_stage["status"] == "healthy"


def test_conclusion_does_not_claim_all_stages_healthy_when_a_watch_exists(payload):
    redcat = next(item for item in payload["line_partitions"] if item["line_id"] == "redcat")
    funnel = redcat["funnel"]
    has_watch = any(stage["status"] == "watch" for stage in funnel["stages"])
    if has_watch:
        assert "各环节均不低于" not in funnel["conclusion"]


def test_legacy_keys_are_untouched(payload):
    for key in (
        "summary", "daily_trend", "point_breakdown", "targeting_breakdown",
        "keyword_breakdown", "creator_breakdown", "creator_totals",
        "note_breakdown", "creator_reviews", "adjustment_directions",
        "decision_summary", "goodcases", "badcases", "knowledge_hits", "quality",
    ):
        assert key in payload, key
