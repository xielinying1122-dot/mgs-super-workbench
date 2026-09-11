from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_mixed_workbench_first_screen_has_priority_band_and_action_preview():
    html = (ROOT / "mgs_workbench" / "mgs_workbench_static" / "index.html").read_text(encoding="utf-8")
    app_js = (ROOT / "mgs_workbench" / "mgs_workbench_static" / "app.js").read_text(encoding="utf-8")

    assert 'id="decision-band"' in html
    assert 'id="priority-actions"' in html
    assert 'id="action-counts"' in html
    assert "renderDecisionBand(payload)" in app_js
    assert "priority-actions" in app_js


def test_workbench_auto_refreshes_when_input_files_change():
    html = (ROOT / "mgs_workbench" / "mgs_workbench_static" / "index.html").read_text(encoding="utf-8")
    app_js = (ROOT / "mgs_workbench" / "mgs_workbench_static" / "app.js").read_text(encoding="utf-8")

    assert 'id="refresh-status"' in html
    assert "sourceSignature" in app_js
    assert 'fetch("/api/files' in app_js
    assert "setInterval(checkForSourceChanges" in app_js
    assert "visibilitychange" in app_js


def test_static_assets_are_cache_busted():
    html = (ROOT / "mgs_workbench" / "mgs_workbench_static" / "index.html").read_text(encoding="utf-8")

    assert '/static/styles.css?v=' in html
    assert '/static/app.js?v=' in html


def test_workbench_shows_week_and_day_period_comparisons():
    html = (ROOT / "mgs_workbench" / "mgs_workbench_static" / "index.html").read_text(encoding="utf-8")
    app_js = (ROOT / "mgs_workbench" / "mgs_workbench_static" / "app.js").read_text(encoding="utf-8")

    assert 'id="period-comparisons"' in html
    assert 'id="week-comparison-body"' in html
    assert 'id="day-comparison-body"' in html
    assert "renderPeriodComparisons(payload)" in app_js
    assert "period_comparisons" in app_js


def test_workbench_separates_plan_and_note_action_sections():
    html = (ROOT / "mgs_workbench" / "mgs_workbench_static" / "index.html").read_text(encoding="utf-8")
    app_js = (ROOT / "mgs_workbench" / "mgs_workbench_static" / "app.js").read_text(encoding="utf-8")

    assert 'id="plan-action-list"' in html
    assert 'id="note-action-list"' in html
    assert 'id="targeting-action-list"' in html
    assert 'id="keyword-action-list"' in html
    assert "renderActionSection" in app_js
    assert "action_groups" in app_js
    assert "item.note_id" in app_js
    assert "item.targeting" in app_js
    assert "item.keyword" in app_js


def test_workbench_exposes_local_project_switcher_and_scopes_requests():
    html = (ROOT / "mgs_workbench" / "mgs_workbench_static" / "index.html").read_text(encoding="utf-8")
    app_js = (ROOT / "mgs_workbench" / "mgs_workbench_static" / "app.js").read_text(encoding="utf-8")

    assert 'id="project-select"' in html
    assert 'id="project-chip-name"' in html
    assert 'id="metric-contract-note"' in html
    assert 'fetch("/api/projects")' in app_js
    assert 'fetch("/api/projects/select"' in app_js
    assert "project_id" in app_js


def test_workbench_renders_project_specific_metric_contract():
    app_js = (ROOT / "mgs_workbench" / "mgs_workbench_static" / "app.js").read_text(encoding="utf-8")

    assert "renderProjectContext(payload)" in app_js
    assert "metric_contract" in app_js
    assert "attribution_windows" in app_js


def test_workbench_uses_project_windows_and_roi_floor_without_mgs_literals():
    html = (ROOT / "mgs_workbench" / "mgs_workbench_static" / "index.html").read_text(encoding="utf-8")
    app_js = (ROOT / "mgs_workbench" / "mgs_workbench_static" / "app.js").read_text(encoding="utf-8")

    assert "PERSONAL / PERFORMANCE DESK" in html
    assert "targets.pause_roi" in app_js
    assert "windowDays" in app_js
    assert "ROI · 30日" not in app_js
    assert "ROI 口径 · 30日归因" not in app_js
    assert "value < 1.5" not in app_js


def test_review_module_has_project_gated_navigation_and_dashboard_regions():
    html = (ROOT / "mgs_workbench" / "mgs_workbench_static" / "index.html").read_text(encoding="utf-8")
    app_js = (ROOT / "mgs_workbench" / "mgs_workbench_static" / "app.js").read_text(encoding="utf-8")

    assert 'id="review-nav"' in html
    assert 'data-view="review"' in html
    assert 'id="view-review"' in html
    assert 'id="review-export"' in html
    assert 'id="review-quality"' in html
    assert 'id="review-creator-list"' in html
    assert 'id="review-daily-chart"' in html
    assert 'id="review-point-chart"' in html
    assert 'id="review-creator-chart"' in html
    assert "reviewEnabled" in app_js
    assert "loadReview" in app_js
    assert "renderReview" in app_js


def test_review_dashboard_surfaces_evidence_and_content_quality_boundary():
    html = (ROOT / "mgs_workbench" / "mgs_workbench_static" / "index.html").read_text(encoding="utf-8")
    app_js = (ROOT / "mgs_workbench" / "mgs_workbench_static" / "app.js").read_text(encoding="utf-8")

    assert "互动高不等于 GMV 高" in html
    assert "evidence_level" in app_js
    assert "content_quality_status" in app_js
    assert "note_link_coverage" in app_js
    assert "/api/export/review-xlsx" in app_js


def test_action_page_previews_rows_instead_of_rendering_every_action():
    app_js = (ROOT / "mgs_workbench" / "mgs_workbench_static" / "app.js").read_text(encoding="utf-8")
    css = (ROOT / "mgs_workbench" / "mgs_workbench_static" / "styles.css").read_text(encoding="utf-8")

    # 动作可能上百条，默认必须切片预览，否则整页会被拉到上万像素。
    assert "ACTION_PREVIEW_LIMIT" in app_js
    assert "actions.slice(0, ACTION_PREVIEW_LIMIT)" in app_js
    assert "action-more" in app_js
    assert "actionExpanded" in app_js
    assert ".action-more" in css


def test_account_control_renders_dashboard_scope_and_isolated_hint():
    html = (ROOT / "mgs_workbench" / "mgs_workbench_static" / "index.html").read_text(encoding="utf-8")
    app_js = (ROOT / "mgs_workbench" / "mgs_workbench_static" / "app.js").read_text(encoding="utf-8")
    css = (ROOT / "mgs_workbench" / "mgs_workbench_static" / "styles.css").read_text(encoding="utf-8")

    # 控件是「投放口径」而不是裸的账户下拉：默认只算 CID，种草要显式切换。
    assert 'id="account-filter"' in html
    assert 'id="scope-hint"' in html
    assert "投放口径" in html
    assert "payload.scope_options" in app_js
    assert "payload.scope_value" in app_js
    assert "已隔离" in app_js and "未隔离" in app_js
    assert ".control-hint.scope-hint" in css
