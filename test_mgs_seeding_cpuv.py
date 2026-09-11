"""种草 CPUV 口径回归测试。

锁的是「CPUV 的分母跟着投放线自己的归因链路走」这条规则：

- CID 的 CPUV = 消耗 / 进店数（30 日成交归因链路）
- 种草的 CPUV = 消耗 / 小红星站外活跃UV（30 日站外归因链路，与进店量无关）
- 分母为 0（UV 未回传）时 CPUV 是「算不出来」，绝不能显示成 0
- 首页 KPI 卡片按口径切换：种草看 CTR / 互动成本 / 站外活跃UV成本，
  不摆 GMV / ROI / 进店数这些它根本不可归因的指标

背景：种草底表里「行业商品进店量30日」「店铺访问量(15日)」常年为 0，
如果沿用 CID 的 visits 分母，种草 CPUV 永远是 0；而「小红星站外活跃UV(30日归因)」
才是它真正的分母，且是 30 日滚动回传，当天必然不全。
"""

import pandas as pd
import pytest

from mgs_workbench_engine import (
    ALIASES,
    aggregate_metrics,
    build_scope_kpi_cards,
    resolve_cpuv_basis,
    seeding_cpuv_reference,
    uv_return_coverage,
)


def _frame(*rows):
    return pd.DataFrame(list(rows))


def _row(account, day, spend, impressions, clicks, interactions, visits, gmv, uv=0):
    return {
        "date": pd.Timestamp(day),
        "account": account,
        "spend": spend,
        "impressions": impressions,
        "clicks": clicks,
        "interactions": interactions,
        "visits": visits,
        "gmv": gmv,
        "seeding_uv": uv,
    }


# --------------------------------------------------------------------------
# 字段映射与口径解析
# --------------------------------------------------------------------------

def test_seeding_uv_alias_matches_xhs_export_header():
    assert "小红星站外活跃UV(30日归因)" in ALIASES["seeding_uv"]
    # 站外 UV 与进店量是两个字段，不能互相顶替。
    assert "小红星站外活跃UV(30日归因)" not in ALIASES["visits"]
    assert "行业商品进店量30日" not in ALIASES["seeding_uv"]


def test_cpuv_basis_normalizes_unknown_values_to_visits():
    assert resolve_cpuv_basis("seeding_uv") == "seeding_uv"
    assert resolve_cpuv_basis("visits") == "visits"
    # 脏配置不能把 CPUV 分母蒙掉，一律回落到 CID 的进店数。
    assert resolve_cpuv_basis("") == "visits"
    assert resolve_cpuv_basis(None) == "visits"
    assert resolve_cpuv_basis("小红星") == "visits"


# --------------------------------------------------------------------------
# 聚合层
# --------------------------------------------------------------------------

def test_aggregate_metrics_switches_cpuv_denominator():
    frame = _frame(_row("种草", "2026-09-09", 1000, 10000, 500, 20, 10, 0, uv=50))

    by_visits = aggregate_metrics(frame)
    by_uv = aggregate_metrics(frame, cpuv_basis="seeding_uv")

    assert by_visits["cpuv"].iloc[0] == pytest.approx(1000 / 10)
    assert by_uv["cpuv"].iloc[0] == pytest.approx(1000 / 50)
    # 换分母不能动到别的指标。
    assert by_visits["spend"].iloc[0] == by_uv["spend"].iloc[0]
    assert by_visits["roi"].iloc[0] == by_uv["roi"].iloc[0]


def test_aggregate_metrics_without_uv_column_is_zero_not_crash():
    frame = _frame({
        "date": pd.Timestamp("2026-09-09"), "account": "种草",
        "spend": 1000, "impressions": 10000, "clicks": 500,
        "interactions": 20, "visits": 0, "gmv": 0,
    })

    result = aggregate_metrics(frame, cpuv_basis="seeding_uv")

    # 缺列等于分母为 0，CPUV 只能是 0，不能抛异常也不能瞎算。
    assert result["cpuv"].iloc[0] == 0.0


def test_uv_return_coverage_counts_returned_rows():
    frame = _frame(
        _row("种草", "2026-09-08", 1000, 10000, 500, 20, 0, 0, uv=25),
        _row("种草", "2026-09-09", 1000, 10000, 500, 20, 0, 0, uv=0),
        _row("种草", "2026-09-09", 1000, 10000, 500, 20, 0, 0, uv=0),
    )

    coverage = uv_return_coverage(frame)

    assert coverage["rows"] == 3
    assert coverage["rows_with_uv"] == 1
    assert coverage["ratio"] == pytest.approx(1 / 3)


def test_seeding_cpuv_reference_picks_latest_day_with_uv():
    """UV 没回传时，参考值必须落在「最近一次真的算得出来」的那一天。"""
    frame = _frame(
        _row("种草", "2026-09-08", 2694.23, 22351, 1526, 38, 0, 0, uv=25),
        _row("种草", "2026-09-09", 3749.53, 31671, 2021, 78, 0, 0, uv=0),
    )

    reference = seeding_cpuv_reference(frame)

    assert reference["date"] == "2026-09-08"
    # 口径与用户底表一致：当天全部消耗 / 当天回传的全部 UV。
    assert reference["value"] == pytest.approx(2694.23 / 25)
    assert reference["seeding_uv"] == 25
    assert reference["spend"] == pytest.approx(2694.23)


def test_seeding_cpuv_reference_is_empty_when_uv_never_returned():
    frame = _frame(_row("种草", "2026-09-09", 3749.53, 31671, 2021, 78, 0, 0, uv=0))

    assert seeding_cpuv_reference(frame) == {}


# --------------------------------------------------------------------------
# 首页卡片：按口径切换
# --------------------------------------------------------------------------

SEEDING_KPIS = {
    "spend": 3749.53,
    "impressions": 31671,
    "clicks": 2021,
    "interactions": 78,
    "ctr": 2021 / 31671,
    "cpc": 3749.53 / 2021,
    "cpm": 3749.53 / 31671 * 1000,
    "cpe": 3749.53 / 78,
    "cpuv": 107.77,
    "seeding_uv": 25,
    "cpuv_ready": True,
    "cpuv_denominator": 25,
    "uv_coverage": {"rows": 146, "rows_with_uv": 20, "ratio": 20 / 146},
}


def test_seeding_cards_replace_cid_metrics():
    cards = build_scope_kpi_cards("seeding", SEEDING_KPIS, {"cpuv_target": None})
    keys = [card["key"] for card in cards]

    assert keys == ["spend", "impressions", "ctr", "cpc", "cpe", "cpuv"]
    # GMV / ROI / 进店数在种草口径里不可归因，绝不能出现在首页。
    for forbidden in ("gmv", "roi", "visits"):
        assert forbidden not in keys


def test_cid_scope_keeps_frontend_cards_untouched():
    # CID 档不下发卡片，前端继续用手写的那四张，保证它的数值与警告零变化。
    assert build_scope_kpi_cards("cid", SEEDING_KPIS, {}) == []
    assert build_scope_kpi_cards("", SEEDING_KPIS, {}) == []
    assert build_scope_kpi_cards("全部", SEEDING_KPIS, {}) == []


def test_seeding_cpuv_card_marks_pending_when_uv_not_returned():
    kpis = {**SEEDING_KPIS, "cpuv": 0.0, "seeding_uv": 0, "cpuv_ready": False,
            "cpuv_denominator": 0, "uv_coverage": {"rows": 146, "rows_with_uv": 0, "ratio": 0.0}}

    cards = build_scope_kpi_cards("seeding", kpis, {"cpuv_target": None})
    cpuv = next(card for card in cards if card["key"] == "cpuv")

    assert cpuv["ready"] is False
    # 关键：显示成破折号而不是 0.00，否则会被读成「成本为零」。
    assert cpuv["display"] == "—"
    assert cpuv["tone"] == "warn"
    assert "未回传" in cpuv["note"]
    assert "0/146" in cpuv["note"]


def test_seeding_cpuv_card_never_uses_cid_target():
    cards = build_scope_kpi_cards("seeding", SEEDING_KPIS, {"cpuv_target": None})
    cpuv = next(card for card in cards if card["key"] == "cpuv")

    # 种草没配目标就不判定，不能借 CID 的 35 来给 good/bad。
    assert cpuv["tone"] == ""
    assert "目标" not in cpuv["note"]


def test_seeding_cpuv_card_uses_its_own_target_when_configured():
    cards = build_scope_kpi_cards("seeding", SEEDING_KPIS, {"cpuv_target": 50})
    cpuv = next(card for card in cards if card["key"] == "cpuv")

    assert cpuv["tone"] == "bad"
    assert "目标 < 50" in cpuv["note"]

    lenient = build_scope_kpi_cards("seeding", SEEDING_KPIS, {"cpuv_target": 200})
    assert next(card for card in lenient if card["key"] == "cpuv")["tone"] == "good"


def test_seeding_ctr_card_is_formatted_as_percentage():
    cards = build_scope_kpi_cards("seeding", SEEDING_KPIS, {})
    ctr = next(card for card in cards if card["key"] == "ctr")

    # 保留两位小数：6.38% 与 6.83% 的差别就是投放优劣的判据。
    assert ctr["display"] == "6.38%"
    assert ctr["format"] == "pct2"


def test_seeding_cpuv_card_quotes_last_computable_day_as_reference():
    kpis = {**SEEDING_KPIS, "cpuv": 0.0, "seeding_uv": 0, "cpuv_ready": False,
            "cpuv_denominator": 0, "uv_coverage": {"rows": 146, "rows_with_uv": 0, "ratio": 0.0}}
    reference = {"date": "2026-09-08", "value": 2694.23 / 25, "seeding_uv": 25, "spend": 2694.23}

    cards = build_scope_kpi_cards("seeding", kpis, {}, reference=reference)
    cpuv = next(card for card in cards if card["key"] == "cpuv")

    # 参考值必须带日期，否则会被当成当天的 CPUV。
    assert cpuv["display"] == "—"
    assert "09-08" in cpuv["note"]
    assert "107.77" in cpuv["note"]
