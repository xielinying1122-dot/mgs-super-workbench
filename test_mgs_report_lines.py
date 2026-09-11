"""投放线日报回归测试。

这些用例锁的是「多条投放线不能互相污染」：
- 每段只用自己的账户数据算 KPI，不出现三段相加
- 种草走单日 + 独立指标组，不套 CID 的 GMV/ROI 与止损阈值
- 没有数据的线直接跳过，不能用 0 冒充
"""

import pandas as pd
import pytest

from mgs_workbench_app import _make_merged_report
from mgs_workbench_engine import build_report_lines, summarize_report_line


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
        # 小红星站外活跃 UV：种草线的 CPUV 分母，跟 CID 的进店量是两条归因链路。
        "seeding_uv": uv,
    }


def _frame(*rows):
    return pd.DataFrame(list(rows))


CID_LINES = [
    {"line_id": "redcat", "name": "红猫", "account": "红猫", "type": "cid"},
    {"line_id": "redbook", "name": "红京", "account": "红京", "type": "cid"},
]

SEEDING_LINE = {
    "line_id": "seeding",
    "name": "种草",
    "account": "种草",
    "type": "seeding",
    "heading": "种草昨日数据",
    "metrics": ["spend", "impressions", "clicks", "ctr", "cpc", "cpm", "cpe", "cpuv"],
    "labels": {"ctr": "CTR", "cpc": "CPC", "cpuv": "CPUV"},
}

PAYLOAD = {
    "project_name": "MGS",
    "as_of_date": "2026-09-09",
    "date_range": {"start": "2026-09-09", "end": "2026-09-09"},
    "attribution_windows": {"gmv_days": 30},
}


def test_report_lines_keep_each_account_isolated():
    frame = _frame(
        _row("红猫", "2026-09-09", 1000, 10000, 600, 20, 50, 3000),
        _row("红京", "2026-09-09", 500, 5000, 300, 10, 10, 500),
        _row("种草", "2026-09-09", 2000, 20000, 1200, 40, 20, 0),
    )
    lines = build_report_lines({"creative": frame}, [*CID_LINES, SEEDING_LINE])
    by_id = {line["line_id"]: line for line in lines}

    assert by_id["redcat"]["metrics"]["spend"] == 1000
    assert by_id["redbook"]["metrics"]["spend"] == 500
    assert by_id["seeding"]["metrics"]["spend"] == 2000
    # 任一段都不能是三条线之和，否则日报会凭空放大消耗。
    assert by_id["redcat"]["metrics"]["spend"] != 3500
    assert by_id["seeding"]["metrics"]["spend"] != 3500


def test_seeding_line_uses_latest_day_only_and_reports_day_over_day():
    frame = _frame(
        _row("种草", "2026-09-08", 1000, 10000, 300, 20, 10, 0),
        _row("种草", "2026-09-09", 2000, 20000, 1200, 40, 20, 0),
    )
    line = summarize_report_line(frame, SEEDING_LINE)

    assert line["start"] == "2026-09-09"
    assert line["end"] == "2026-09-09"
    assert line["metrics"]["spend"] == 2000
    assert line["previous"]["end"] == "2026-09-08"
    assert line["changes"]["spend"] == pytest.approx(1.0)


def test_month_to_date_window_converges_to_each_line_own_data():
    frame = _frame(
        _row("红猫", "2026-08-20", 5000, 50000, 3000, 100, 200, 15000),
        _row("红猫", "2026-09-01", 400, 4000, 200, 8, 20, 1000),
        _row("红猫", "2026-09-09", 1000, 10000, 600, 20, 50, 3000),
        _row("红京", "2026-09-08", 800, 8000, 400, 15, 15, 700),
        _row("红京", "2026-09-09", 900, 9000, 450, 16, 16, 800),
    )
    lines = build_report_lines(
        {"creative": frame},
        [
            {"line_id": "redcat", "name": "红猫", "account": "红猫", "type": "cid", "window": "month_to_date"},
            {"line_id": "redbook", "name": "红京", "account": "红京", "type": "cid", "window": "month_to_date"},
        ],
    )
    by_id = {line["line_id"]: line for line in lines}

    # 红猫 8 月那 5000 消耗必须被月度窗口排除，否则日报会虚报本月累计。
    assert by_id["redcat"]["start"] == "2026-09-01"
    assert by_id["redcat"]["metrics"]["spend"] == 1400
    # 红京 9/8 才起投，窗口自然收敛到自己的实际起投日，不会被补成 9/1。
    assert by_id["redbook"]["start"] == "2026-09-08"
    assert by_id["redbook"]["metrics"]["spend"] == 1700


def test_seeding_block_never_borrows_cid_gmv_or_roi():
    frame = _frame(
        _row("红猫", "2026-09-09", 1000, 10000, 600, 20, 50, 3000),
        _row("种草", "2026-09-09", 2000, 20000, 1200, 40, 20, 0, uv=50),
    )
    lines = build_report_lines({"creative": frame}, [*CID_LINES[:1], SEEDING_LINE])
    text = _make_merged_report(PAYLOAD, lines, {})

    assert "种草昨日数据" in text
    assert "CPUV：" in text and "CPM：" in text and "CPE：" in text
    # 种草 CPUV = 消耗 / 小红星站外活跃UV，不是 CID 的消耗 / 进店数。
    assert "CPUV：40.00" in text

    seeding_block = text.split("种草昨日数据")[1].split("数据表现情况")[0]
    # 种草没有外链成交归因，不能出现 CID 的 GMV / ROI 行。
    assert "店铺成交ROI" not in seeding_block
    assert "GMV" not in seeding_block


def test_seeding_cpuv_never_poses_as_zero_when_uv_not_returned():
    """UV 未回传时分母为 0，CPUV 是「算不出来」而不是「等于 0」。

    这一行必须留着（读日报的人要知道这个指标存在、只是今天算不出来），
    呈现方式是「—」，绝不能退化成 0。
    """
    frame = _frame(
        _row("红猫", "2026-09-09", 1000, 10000, 600, 20, 50, 3000),
        _row("种草", "2026-09-09", 2000, 20000, 1200, 40, 20, 0, uv=0),
    )
    lines = build_report_lines({"creative": frame}, [*CID_LINES[:1], SEEDING_LINE])
    seeding = {line["line_id"]: line for line in lines}["seeding"]

    assert seeding["cpuv_basis"] == "seeding_uv"
    assert seeding["cpuv_ready"] is False
    assert seeding["cpuv_computable"] is False
    assert seeding["metrics"]["seeding_uv"] == 0

    text = _make_merged_report(PAYLOAD, lines, {})
    seeding_block = text.split("种草昨日数据")[1].split("数据表现情况")[0]
    assert "CPUV：—" in seeding_block
    assert "CPUV：0" not in seeding_block
    assert "0.00\n" not in seeding_block.split("CPUV")[1]


def test_cid_line_keeps_visit_based_cpuv():
    """CID 线的 CPUV 分母必须仍是进店数，不能被种草口径改写。"""
    frame = _frame(
        _row("红猫", "2026-09-09", 1000, 10000, 600, 20, 50, 3000, uv=999),
    )
    line = summarize_report_line(frame, CID_LINES[0])

    assert line["cpuv_basis"] == "visits"
    assert line["metrics"]["cpuv"] == pytest.approx(1000 / 50)
    assert line["cpuv_denominator"] == 50


def test_cid_block_still_labels_gmv_with_configured_window():
    frame = _frame(_row("红猫", "2026-09-09", 1000, 10000, 600, 20, 50, 3000))
    lines = build_report_lines({"creative": frame}, CID_LINES[:1])
    text = _make_merged_report(PAYLOAD, lines, {})

    assert "店铺成交GMV（30日）：3,000.00" in text
    assert "店铺成交ROI（30日）：3.00" in text


def test_lines_without_data_are_skipped_instead_of_printing_zeros():
    frame = _frame(_row("红猫", "2026-09-09", 1000, 10000, 600, 20, 50, 3000))
    lines = build_report_lines({"creative": frame}, [*CID_LINES[:1], SEEDING_LINE])
    text = _make_merged_report(PAYLOAD, lines, {})

    assert "红猫" in text
    # 种植草还没导出时，不能凭空打印一段 0。
    assert "种草昨日数据" not in text


def test_actions_are_labelled_per_line_and_seeding_is_excluded():
    frame = _frame(
        _row("红猫", "2026-09-09", 1000, 10000, 600, 20, 50, 3000),
        _row("红京", "2026-09-09", 500, 5000, 300, 10, 10, 500),
        _row("种草", "2026-09-09", 2000, 20000, 1200, 40, 20, 0),
    )
    lines = build_report_lines({"creative": frame}, [*CID_LINES, SEEDING_LINE])
    text = _make_merged_report(
        PAYLOAD,
        lines,
        {
            "redcat": [{"action": "加预算", "kind": "creative", "entity_name": "计划A", "reason": "ROI达标", "budget_change": "+20%"}],
            "redbook": [{"action": "暂停/降预算", "kind": "targeting", "entity_name": "智能定向", "reason": "ROI偏低", "budget_change": "停止新增"}],
            # 即使上游误传种草动作，也不能进日报：CID 阈值与种草 CPUV 不是一个量级。
            "seeding": [{"action": "暂停/降预算", "kind": "creative", "entity_name": "种草计划", "reason": "CPUV>50", "budget_change": "停止新增"}],
        },
    )

    assert "【红猫】" in text
    assert "【红京】" in text
    assert "【种草】" not in text


def test_merged_report_states_when_no_line_has_data():
    empty = pd.DataFrame(columns=["date", "account", "spend", "impressions", "clicks", "interactions", "visits", "gmv"])
    lines = build_report_lines({"creative": empty}, CID_LINES)
    text = _make_merged_report(PAYLOAD, lines, {})

    assert "没有可用的投放线数据" in text
