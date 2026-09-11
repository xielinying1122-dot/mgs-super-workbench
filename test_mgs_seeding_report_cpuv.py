"""文字日报里「种草 CPUV」的口径回归测试。

锁住三件事：
1. 种草 CPUV = 当日消耗 ÷ 当日小红星站外活跃UV（30日归因），不是进店成本；
2. UV 当日必然回传不全，CPUV 算不出来时这一行也必须留着（显「—」+ 最近可算日），
   不能整行消失、更不能拿 0 冒充；
3. CID 段的进店成本不受影响，两个口径不许互相借分母。
"""

import pandas as pd
import pytest

from mgs_workbench_app import _make_merged_report, _seeding_section
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
        # 小红星站外活跃 UV：种草线 CPUV 的分母，跟 CID 的进店量是两条归因链路。
        "seeding_uv": uv,
    }


def _frame(*rows):
    return pd.DataFrame(list(rows))


SEEDING_LINE = {
    "line_id": "seeding",
    "name": "种草",
    "account": "种草",
    "type": "seeding",
    "window": "latest_day",
    "heading": "种草昨日数据",
    "metrics": ["spend", "impressions", "clicks", "ctr", "cpc", "cpm", "cpe", "cpuv"],
    "labels": {"ctr": "CTR", "cpc": "CPC", "cpuv": "CPUV"},
}

CID_LINE = {"line_id": "redcat", "name": "红猫", "account": "红猫", "type": "cid", "window": "month_to_date"}

PAYLOAD = {
    "project_name": "MGS",
    "as_of_date": "2026-09-09",
    "date_range": {"start": "2026-09-09", "end": "2026-09-09"},
    "attribution_windows": {"gmv_days": 30},
}


def test_seeding_cpuv_row_stays_when_uv_not_returned():
    """UV 未回传：CPUV 行必须在，给「—」+ 最近可算日，不能消失也不能写 0。"""
    frame = _frame(
        _row("种草", "2026-09-08", 2694.23, 22351, 1526, 38, 0, 0, uv=25),
        _row("种草", "2026-09-09", 3749.53, 31671, 2021, 78, 0, 0, uv=0),
    )
    line = summarize_report_line(frame, SEEDING_LINE)

    assert line["end"] == "2026-09-09"
    assert line["cpuv_computable"] is False
    assert line["cpuv_reference"]["date"] == "2026-09-08"
    assert line["cpuv_reference"]["value"] == pytest.approx(2694.23 / 25)

    text = "\n".join(_seeding_section(line))
    assert "CPUV：" in text
    assert "107.77" in text
    # 最近可算日必须带日期，否则读日报的人会把它当成今天的数。
    assert "09/08" in text
    assert "CPUV：0" not in text


def test_seeding_cpuv_uses_seeding_uv_not_visits():
    """种草 CPUV 的分母是站外活跃 UV，不是进店数。"""
    frame = _frame(_row("种草", "2026-09-09", 2000, 20000, 1200, 40, 20, 0, uv=25))
    line = summarize_report_line(frame, SEEDING_LINE)

    assert line["cpuv_basis"] == "seeding_uv"
    assert line["cpuv_computable"] is True
    assert line["metrics"]["cpuv"] == pytest.approx(80.0)  # 2000 / 25

    text = "\n".join(_seeding_section(line))
    assert "CPUV：80.00" in text
    # 2000 / 20(进店数) = 100，绝不能出现在 CPUV 这一行上（CPM 是 100.00 属正常）。
    assert "CPUV：100.00" not in text
    assert "CPM：100.00" in text


def test_cid_line_keeps_visits_basis():
    """CID 段照旧用进店成本，不许被种草的 UV 口径带跑。"""
    frame = _frame(_row("红猫", "2026-09-09", 1000, 10000, 600, 20, 50, 3000, uv=2500))
    lines = build_report_lines({"creative": frame}, [CID_LINE])
    line = lines[0]

    assert line["cpuv_basis"] == "visits"
    assert line["metrics"]["cpuv"] == pytest.approx(20.0)  # 1000 / 50


def test_merged_report_keeps_two_cpuv_bases_apart():
    frame = _frame(
        _row("红猫", "2026-09-09", 1000, 10000, 600, 20, 50, 3000),
        _row("种草", "2026-09-09", 2000, 20000, 1200, 40, 0, 0, uv=0),
    )
    summaries = build_report_lines({"creative": frame}, [CID_LINE, SEEDING_LINE])
    text = _make_merged_report(PAYLOAD, summaries, {})

    # CID 段：进店成本照旧。
    assert "进店成本：20.00" in text
    # 种地段：CPUV 独立一行，且写明与 CID 不可比。
    assert "CPUV：—" in text
    assert "小红星站外活跃UV" in text
    assert "不可比" in text
    # 种草段的三段相加式污染不许出现（消耗只能是各自的数）。
    assert "消耗：2,000.00" in text
    assert "消耗：1,000.00" in text
    assert "消耗：3,000.00" not in text


def test_seeding_section_does_not_invent_cpuv_when_not_configured():
    """配置里没有 CPUV 这一项时，不许硬塞一行出来。"""
    line = {
        "heading": "种草昨日数据",
        "metrics_display": [{"key": "spend", "label": "消耗", "value": 100.0, "has_data": True}],
        "metrics": {},
        "cpuv_computable": False,
    }
    blocks = _seeding_section(line)
    assert "消耗：100.00" in "\n".join(blocks)
    assert not any(block.startswith("CPUV") for block in blocks)
    assert "CPUV" not in "\n".join(blocks)


def test_seeding_cpuv_row_has_data_but_no_reference_is_still_printed():
    """全周期 UV 都是 0（分母一次都没回传）时，也要留行并说明算不出来。"""
    frame = _frame(_row("种草", "2026-09-09", 3749.53, 31671, 2021, 78, 0, 0, uv=0))
    line = summarize_report_line(frame, SEEDING_LINE)

    assert line["cpuv_computable"] is False
    assert line["cpuv_reference"] == {}

    text = "\n".join(_seeding_section(line))
    assert "CPUV：—" in text
    assert "暂时算不出来" in text
    assert "CPUV：0" not in text


def test_cpuv_missing_blank_switch_drops_the_reference_line():
    """cpuv_missing=blank 时只留「—」，不给最近可算日。"""
    frame = _frame(
        _row("种草", "2026-09-08", 2694.23, 22351, 1526, 38, 0, 0, uv=25),
        _row("种草", "2026-09-09", 3749.53, 31671, 2021, 78, 0, 0, uv=0),
    )
    line = summarize_report_line(frame, {**SEEDING_LINE, "cpuv_missing": "blank"})
    text = "\n".join(_seeding_section(line))

    assert "CPUV：—（站外活跃UV未回传，暂时算不出来）" in text
    assert "107.77" not in text


def test_seeding_note_switches_with_uv_availability():
    """口径注要在「已回传」和「未回传」两种状态下都给到分母定义。"""
    returned = _frame(_row("种草", "2026-09-09", 2000, 20000, 1200, 40, 0, 0, uv=25))
    missing = _frame(_row("种草", "2026-09-09", 2000, 20000, 1200, 40, 0, 0, uv=0))

    returned_text = "\n".join(_seeding_section(summarize_report_line(returned, SEEDING_LINE)))
    missing_text = "\n".join(_seeding_section(summarize_report_line(missing, SEEDING_LINE)))

    assert "当日消耗÷当日小红星站外活跃UV" in returned_text
    assert "当日消耗÷当日小红星站外活跃UV" in missing_text
    assert "回传不全" in missing_text
