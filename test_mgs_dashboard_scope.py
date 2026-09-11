"""主看板投放口径隔离回归测试。

锁的是「主看板默认只算 CID，种草不污染 CID 口径」这条规则：

- 默认档 = ``report_lines`` 里 ``type=cid`` 的账户（红猫 + 红京），不含种草
- 显式切到「全部账户」时才把 CID 与种草合并计算
- 单独看种草时不套 CID 的止损/放量规则，一条待执行动作都不产出
- 没有投放线配置的项目保持旧行为：默认不过滤，但显式选账户仍然收窄

背景：种草的 ROI / CPUV 与 CID 不是同一套归因（内容效率 vs 30 日成交），
混算会让 ROI 被压低、CPUV 被抬高，进而对 CID 计划误发止损信号。
"""

import io
import json

import pandas as pd
import pytest
from fastapi.testclient import TestClient

import mgs_workbench_engine as engine
from mgs_workbench_app import create_app


CID_LINES = [
    {"line_id": "redcat", "name": "红猫", "account": "红猫", "type": "cid"},
    {"line_id": "redbook", "name": "红京", "account": "红京", "type": "cid"},
]

SEEDING_LINE = {"line_id": "seeding", "name": "种草", "account": "种草", "type": "seeding"}

ALL_LINES = [*CID_LINES, SEEDING_LINE]

KPI = {"roi_target": 2.5, "roi_stretch": 3.0, "cpuv_target": 35.0, "cpuv_stretch": 30.0}
ACTION_RULES = {
    "high_roi": 4.0,
    "scale_roi": 2.0,
    "scale_cpuv": 50.0,
    "scale_visits": 20.0,
    "entry_cpuv": 20.0,
    "entry_roi": 1.0,
    "test_spend": 800.0,
    "test_days": 14.0,
    "pause_roi": 1.5,
    "pause_cpuv": 50.0,
    "min_action_spend": 100.0,
    "roi_alert": 1.0,
}


# --------------------------------------------------------------------------
# 口径解析
# --------------------------------------------------------------------------

def test_default_scope_is_cid_only():
    scope = engine.resolve_dashboard_scope(None, ALL_LINES)

    assert scope["type"] == "cid"
    assert scope["accounts"] == ["红猫", "红京"]
    assert "种草" not in scope["accounts"]
    assert scope["isolated"] is True


@pytest.mark.parametrize("requested", [None, "", "   "])
def test_blank_selection_keeps_cid_default(requested):
    assert engine.resolve_dashboard_scope(requested, ALL_LINES)["type"] == "cid"


def test_all_scope_includes_every_line():
    scope = engine.resolve_dashboard_scope(engine.DASHBOARD_SCOPE_ALL, ALL_LINES)

    assert scope["type"] == "all"
    assert scope["accounts"] == ["红猫", "红京", "种草"]
    assert scope["isolated"] is False


def test_single_cid_account_scope():
    scope = engine.resolve_dashboard_scope("红京", ALL_LINES)

    assert scope["type"] == "cid"
    assert scope["accounts"] == ["红京"]


def test_seeding_account_resolves_to_seeding_scope():
    scope = engine.resolve_dashboard_scope("种草", ALL_LINES)

    assert scope["type"] == "seeding"
    assert scope["accounts"] == ["种草"]
    assert scope["note"]


def test_unknown_account_is_treated_as_single_scope():
    scope = engine.resolve_dashboard_scope("新账户", ALL_LINES)

    assert scope["type"] == "single"
    assert scope["accounts"] == ["新账户"]
    assert scope["isolated"] is False


def test_project_without_report_lines_keeps_legacy_behaviour():
    """没有投放线配置时默认不过滤，这正是旧版本的行为。"""
    assert engine.resolve_dashboard_scope(None, [])["type"] == "all"
    assert engine.resolve_dashboard_scope(None, [])["accounts"] == []


def test_project_without_report_lines_still_narrows_explicit_account():
    """显式选账户必须继续生效，否则单账户日报导出会串数据。"""
    scope = engine.resolve_dashboard_scope("红猫", [])

    assert scope["type"] == "single"
    assert scope["accounts"] == ["红猫"]


def test_report_line_accounts_ignores_entries_without_account():
    lines = [{"type": "cid", "account": " "}, {"type": "cid", "account": "红猫"}, {"type": "seeding", "account": "种草"}]

    assert engine.report_line_accounts(lines, ("cid",)) == ["红猫"]
    assert engine.report_line_accounts(lines, ("seeding",)) == ["种草"]


def test_scope_options_marks_the_default_and_each_line():
    options = engine.scope_options(ALL_LINES)
    values = [item["value"] for item in options]

    assert values[0] == ""  # 默认档 = CID
    assert engine.DASHBOARD_SCOPE_ALL in values
    assert "红猫" in values and "种草" in values
    assert all(item["label"] for item in options)


def test_scope_options_without_configuration():
    assert engine.scope_options([]) == [{"value": "", "label": "全部账户"}]


# --------------------------------------------------------------------------
# 动作抑制
# --------------------------------------------------------------------------

def _creative_frame(*rows):
    frame = pd.DataFrame(list(rows))
    frame["date"] = pd.to_datetime(frame["date"])
    frame["report_mode"] = "single"
    return frame


def _row(account, campaign, spend, visits, gmv):
    return {
        "date": "2026-09-01",
        "account": account,
        "campaign": campaign,
        "note_id": f"{campaign}-note",
        "point": "信息流",
        "spend": spend,
        "impressions": 1000.0,
        "clicks": 50.0,
        "interactions": 10.0,
        "visits": visits,
        "gmv": gmv,
    }


def test_seeding_scope_produces_no_cid_actions():
    """种草 ROI 为 0 会触发 CID 止损，这类假信号必须被拦掉。"""
    frame = _creative_frame(
        _row("种草", "种草-计划A", 5000.0, 0.0, 0.0),
        _row("种草", "种草-计划B", 4000.0, 0.0, 0.0),
    )

    payload = engine.build_dashboard_payload(
        {"creative": frame},
        kpi=KPI,
        action_rules=ACTION_RULES,
        scope={"type": "seeding", "accounts": ["种草"]},
    )

    assert payload["actions"] == []
    assert payload["points"] == []
    assert payload["plans"] == []
    assert all(rows == [] for rows in payload["action_groups"].values())


def test_seeding_scope_neutralises_drilldown_action_labels():
    frame = _creative_frame(_row("种草", "种草-计划A", 5000.0, 0.0, 0.0))

    payload = engine.build_dashboard_payload(
        {"creative": frame},
        kpi=KPI,
        action_rules=ACTION_RULES,
        scope={"type": "seeding", "accounts": ["种草"]},
    )

    rows = payload["drilldowns"]["creative"]
    assert rows, "明细仍需保留，只是不再带 CID 动作结论"
    assert all(item["action"] == "仅观察" for item in rows)
    assert all(not item["budget_change"] for item in rows)


def test_cid_scope_keeps_actions():
    frame = _creative_frame(_row("红猫", "红猫-计划A", 5000.0, 0.0, 0.0))

    payload = engine.build_dashboard_payload(
        {"creative": frame},
        kpi=KPI,
        action_rules=ACTION_RULES,
        scope={"type": "cid", "accounts": ["红猫"]},
    )

    assert payload["actions"], "CID 口径下止损动作必须照常产出"


def test_payload_echoes_scope():
    payload = engine.build_dashboard_payload(
        {"creative": _creative_frame(_row("红猫", "红猫-计划A", 100.0, 10.0, 300.0))},
        kpi=KPI,
        action_rules=ACTION_RULES,
        scope={"type": "cid", "accounts": ["红猫"]},
    )

    assert payload["scope"]["type"] == "cid"


# --------------------------------------------------------------------------
# 端到端：真实项目配置下的默认口径
# --------------------------------------------------------------------------

CSV_HEADER = "时间,投放类型,计划名称,消费,行业商品进店量30日,行业商品GMV（30日),下载账户"
CSV_ROWS = [
    "2026-09-01,全站,红猫计划,100,10,300,红猫",
    "2026-09-01,全站,红京计划,200,20,800,红京",
    "2026-09-01,全站,种草计划,50,0,0,种草",
]


def _write_registry(root, input_dir, lines):
    registry = {
        "version": 1,
        "projects": [
            {
                "project_id": "scope-proj",
                "name": "SCOPE",
                "display_name": "口径测试项目",
                "root_dir": str(root),
                "input_dir": str(input_dir),
                "default_source": str(root),
                "workspace_dir": str(root),
                "primary_workbook_prefix": "SCOPE-",
                "kpi": dict(KPI),
                "action_rules": dict(ACTION_RULES),
                "metric_contract": {"primary_total_source": "creative"},
                "attribution_windows": {"gmv_days": 30, "visits_days": 15},
                "report_lines": lines,
                "modules": {"投放分析": True, "日报": True, "复盘": True},
            }
        ],
    }
    path = root / "projects.json"
    path.write_text(json.dumps(registry, ensure_ascii=False), encoding="utf-8")
    return path


def _client(tmp_path, lines):
    input_dir = tmp_path / "in"
    input_dir.mkdir(parents=True, exist_ok=True)
    registry_path = _write_registry(tmp_path, input_dir, lines)
    app = create_app(input_dir=input_dir, default_source=None, registry_path=registry_path, project_id="scope-proj")
    client = TestClient(app)
    content = "\n".join([CSV_HEADER, *CSV_ROWS]).encode("utf-8")
    uploaded = client.post("/api/upload", files={"files": ("日报.csv", io.BytesIO(content), "text/csv")})
    assert uploaded.status_code == 200
    return client


def _analyze(client, account_id=None):
    body = {"start": "2026-09-01", "end": "2026-09-01", "compare": False}
    if account_id is not None:
        body["account_id"] = account_id
    response = client.post("/api/analyze", json=body)
    assert response.status_code == 200
    return response.json()


def test_dashboard_default_excludes_seeding(tmp_path):
    client = _client(tmp_path, ALL_LINES)

    payload = _analyze(client)

    assert payload["scope"]["type"] == "cid"
    assert payload["kpis"]["spend"] == pytest.approx(300.0)


def test_dashboard_all_scope_includes_seeding(tmp_path):
    client = _client(tmp_path, ALL_LINES)

    payload = _analyze(client, engine.DASHBOARD_SCOPE_ALL)

    assert payload["scope"]["type"] == "all"
    assert payload["kpis"]["spend"] == pytest.approx(350.0)


def test_dashboard_seeding_scope_alone(tmp_path):
    client = _client(tmp_path, ALL_LINES)

    payload = _analyze(client, "种草")

    assert payload["scope"]["type"] == "seeding"
    assert payload["kpis"]["spend"] == pytest.approx(50.0)
    assert payload["actions"] == []


def test_dashboard_without_report_lines_keeps_legacy_scope(tmp_path):
    client = _client(tmp_path, [])

    payload = _analyze(client)

    assert payload["scope"]["type"] == "all"
    assert payload["kpis"]["spend"] == pytest.approx(350.0)
    assert payload["scope_options"] == [{"value": "", "label": "全部账户"}]
