import json

import pytest

from project_registry import ProjectRegistry, ProjectRegistryError


def write_registry(path, projects):
    path.write_text(json.dumps({"version": 1, "projects": projects}), encoding="utf-8")


def project(project_id, root):
    return {
        "project_id": project_id,
        "name": project_id.upper(),
        "display_name": f"{project_id} 项目",
        "root_dir": str(root),
        "input_dir": str(root / "输入"),
        "default_source": str(root),
        "kpi": {"roi_target": 3},
        "metric_contract": {"roi": "gmv / spend"},
        "attribution_windows": {"gmv_days": 30},
        "modules": {"投放分析": True, "规划": False},
    }


def test_registry_resolves_multiple_local_projects(tmp_path):
    registry_path = tmp_path / "projects.json"
    alpha = project("alpha", tmp_path / "alpha")
    alpha["action_rules"] = {"pause_roi": 0.8, "test_days": 5}
    write_registry(registry_path, [alpha, project("beta", tmp_path / "beta")])

    registry = ProjectRegistry(registry_path)

    assert [item.project_id for item in registry.projects] == ["alpha", "beta"]
    assert registry.get("beta").input_dir == (tmp_path / "beta" / "输入").resolve()
    assert registry.get("alpha").public_dict()["modules"]["规划"] is False
    assert registry.get("alpha").action_rules["pause_roi"] == 0.8


def test_registry_resolves_review_rules(tmp_path):
    registry_path = tmp_path / "projects.json"
    alpha = project("alpha", tmp_path / "alpha")
    alpha["review_rules"] = {
        "min_creator_spend": 100,
        "min_creator_visits": 20,
        "min_creator_active_days": 2,
        "min_creator_impressions": 1000,
    }
    write_registry(registry_path, [alpha])

    registry = ProjectRegistry(registry_path)

    assert registry.get("alpha").review_rules == {
        "min_creator_spend": 100,
        "min_creator_visits": 20,
        "min_creator_active_days": 2,
        "min_creator_impressions": 1000,
    }
    assert registry.get("alpha").public_dict()["review_rules"] == alpha["review_rules"]


def test_mgs_enables_review_module():
    registry = ProjectRegistry("config/projects.example.json")

    assert registry.get("example-project").modules["复盘"] is False


def test_registry_rejects_duplicate_or_invalid_project_ids(tmp_path):
    registry_path = tmp_path / "projects.json"
    write_registry(registry_path, [project("alpha", tmp_path / "one"), project("alpha", tmp_path / "two")])

    with pytest.raises(ProjectRegistryError, match="重复"):
        ProjectRegistry(registry_path)

    write_registry(registry_path, [project("not valid", tmp_path / "one")])

    with pytest.raises(ProjectRegistryError, match="不合法"):
        ProjectRegistry(registry_path)
