# 聚光自动化工作台

这是一个本地优先的聚光投放分析工作台，当前包含 MGS 投流分析和投流复盘模块。

## 快速开始

```bash
cp config/projects.example.json config/projects.json
# 编辑 config/projects.json，填写本机项目目录与指标口径
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
./run_mgs_workbench.sh
```

打开 `http://127.0.0.1:8765/`，在左侧项目下拉框切换项目。报表放入当前项目的
`input_dir`，或在页面上传；总盘使用创意/日报明细，定向和关键词用于下钻。

MGS 的“投流复盘”页面支持按日期和点位查看消耗、GMV、ROI、进店 CPUV、达人与笔记拆分，
并导出独立的 9 个 Sheet。内容点评需要用户提供可访问的笔记链接、截图或正文；缺少内容证据时，
系统只评价投放表现，内容质量保持 `unknown`。

本仓库不包含原始报表、Cookie、Token、日志或本机项目配置。首次使用请复制
`config/projects.example.json` 为本机配置；本地配置文件已加入忽略规则。

## 项目切换与复盘

在工作台左侧的“当前项目”下拉框切换项目。每个项目使用独立的 `root_dir` 和 `input_dir`；
切换后数据目录、报表前缀、指标口径、归因窗口和模块开关都会跟随项目变化。接入新的报表时，
先在本机 `config/projects.json` 复制一个项目对象，再把对应的 CSV/XLSX 放入该项目的 `input_dir`，
或使用页面的“上传报表”。

“投流复盘”只在项目的 `modules.复盘` 为 `true` 时显示。它从创意/日报明细生成总盘，再拆到
点位、定向、关键词、达人和笔记，并提供独立的 9 Sheet Excel 导出。定向和关键词仅作下钻，
不会重复加总项目总盘；零消耗但有延迟归因的行只进入数据质量提示。达人内容点评需要可访问的
笔记链接、截图或正文，缺少内容证据时只评价投放表现，内容质量保持 `unknown`。

## 开发检查

```bash
.venv/bin/python -m pytest \
  tests/test_project_registry.py \
  tests/test_mgs_review_engine.py \
  tests/test_mgs_review_edge_cases.py \
  tests/test_mgs_review_api.py \
  tests/test_mgs_workbench_app.py \
  tests/test_mgs_workbench_engine.py \
  tests/test_mgs_workbench_frontend.py -q
```

工作台只在本机 `127.0.0.1` 监听，不向外部服务上传报表，也不会自动修改聚光账户。
