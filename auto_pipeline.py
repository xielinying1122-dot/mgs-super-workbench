#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
聚光全自动管线
================
通过 CDP（Chrome DevTools Protocol）操控已运行的 Chrome（端口 9222），
在浏览器上下文里调用聚光 API（自带签名/CSRF，避开 Python 直调的 406 风控），
然后串接日报/时报 + 可视化。

前置条件（只做一次）：
  1. Chrome 已带 --remote-debugging-port=9222 启动（你的已经在跑了 ✓）
  2. 该 Chrome 已登录聚光（脚本会检测，没登录会提示）

每天用：
  python3 auto_pipeline.py daily              # 出日报（默认昨天）
  python3 auto_pipeline.py daily --date 2026-05-21
  python3 auto_pipeline.py hourly --hours 8-10
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests
import websocket

CDP_PORT = 9222
CDP_HOST = "localhost"
SELLER_ID = "692556d24b69aa0015fefdd3"

# 用户是代理商（合作伙伴）身份，入口是 partner.xiaohongshu.com
# 登录后通过它跳到 ad.xiaohongshu.com 的具体客户账户操作页
PARTNER_HOME = "https://partner.xiaohongshu.com/"
JUGUANG_HOME = f"https://ad.xiaohongshu.com/aurora/ad/manage/campaigngroup?vSellerId={SELLER_ID}"
DATA_REPORT_PAGE = f"https://ad.xiaohongshu.com/aurora/data/campaign?vSellerId={SELLER_ID}"

RAW_DIR = Path.home() / "juguang-automation" / "data" / "raw"
REPORTS_DIR = Path.home() / "juguang-automation" / "data" / "reports"
RAW_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


# ────────────────────────────────────────────────────────────
# CDP 基础设施
# ────────────────────────────────────────────────────────────

def cdp_check() -> bool:
    try:
        r = requests.get(f"http://{CDP_HOST}:{CDP_PORT}/json/version", timeout=2)
        return r.status_code == 200
    except Exception:
        return False


def cdp_list_tabs() -> list[dict]:
    r = requests.get(f"http://{CDP_HOST}:{CDP_PORT}/json", timeout=5)
    return [t for t in r.json() if t.get("type") == "page"]


def cdp_find_or_open_juguang() -> dict:
    """找到 partner / 聚光 tab，没有就新开。优先 ad.xiaohongshu.com，其次 partner。"""
    page_tabs = [t for t in cdp_list_tabs()]
    # 找已登录的 ad.xiaohongshu.com tab
    for t in page_tabs:
        url = t.get("url", "")
        if "ad.xiaohongshu.com" in url and "redirectTo" not in url and "/login" not in url:
            return t
    # 找 partner tab
    for t in page_tabs:
        url = t.get("url", "")
        if "partner.xiaohongshu.com" in url:
            return t
    # 找重定向中的 tab
    for t in page_tabs:
        url = t.get("url", "")
        if "xiaohongshu.com" in url:
            return t
    # 都没有，新开 partner
    r = requests.put(f"http://{CDP_HOST}:{CDP_PORT}/json/new?{PARTNER_HOME}")
    time.sleep(3)
    return r.json()


class CDPSession:
    def __init__(self, ws_url: str):
        # Chrome 138+ 要求 WebSocket origin 是 null 或允许列表里的。
        # websocket-client 默认会发 "http://localhost:9222" 当 origin，会被拒。
        # 用 header 显式设 origin 为 null 绕开（参考 Chrome DevTools 自己的握手）。
        self.ws = websocket.create_connection(
            ws_url,
            timeout=30,
            origin="null",
            header=["Origin: null"],
        )
        self._id = 0

    def send(self, method: str, params: dict = None) -> dict:
        self._id += 1
        msg_id = self._id
        self.ws.send(json.dumps({"id": msg_id, "method": method, "params": params or {}}))
        while True:
            resp = json.loads(self.ws.recv())
            if resp.get("id") == msg_id:
                return resp

    def eval_js(self, expression: str, await_promise: bool = True) -> dict:
        r = self.send("Runtime.evaluate", {
            "expression": expression,
            "awaitPromise": await_promise,
            "returnByValue": True,
        })
        result = r.get("result", {}).get("result", {})
        if result.get("subtype") == "error":
            raise RuntimeError(f"JS 错误: {result.get('description')}")
        return result.get("value")

    def navigate(self, url: str):
        self.send("Page.enable")
        self.send("Page.navigate", {"url": url})

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass


# ────────────────────────────────────────────────────────────
# 登录态检测
# ────────────────────────────────────────────────────────────

def ensure_logged_in() -> CDPSession:
    if not cdp_check():
        print("❌ CDP 端口 9222 不可达。请用以下命令启动 Chrome：", file=sys.stderr)
        print('   /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome \\', file=sys.stderr)
        print(f'       --remote-debugging-port={CDP_PORT} \\', file=sys.stderr)
        print('       --user-data-dir="$HOME/Library/Application Support/Google/ChromeDebug" &', file=sys.stderr)
        sys.exit(1)

    tab = cdp_find_or_open_juguang()
    session = CDPSession(tab["webSocketDebuggerUrl"])

    current_url = session.eval_js("window.location.href")
    print(f"📍 当前 tab：{current_url[:80]}", file=sys.stderr)

    # 检查登录态：尝试访问一个需要登录的 API
    check_js = """
    fetch('https://ad.xiaohongshu.com/api/leona/rtb/account/balance?vSellerId=""" + SELLER_ID + """', {
        credentials: 'include',
        headers: {'Content-Type': 'application/json'}
    })
    .then(r => ({status: r.status, ok: r.ok}))
    .catch(e => ({error: e.message}))
    """
    result = session.eval_js(check_js)
    if not isinstance(result, dict):
        result = {"raw": str(result)}

    if result.get("status") == 200:
        print("✅ 已登录聚光（账户 API 200）", file=sys.stderr)
        return session

    # 没登录 - 强制跳转到 partner 登录页让用户登录
    print(f"⚠️  未登录聚光合作伙伴（账户 API 返回 {result})", file=sys.stderr)
    print("", file=sys.stderr)
    print("👉 请在已打开的 Chrome 里完成登录：", file=sys.stderr)
    print(f"   1. partner 入口：{PARTNER_HOME}", file=sys.stderr)
    print("   2. 登录后选「蔡司眼镜」客户账户进入", file=sys.stderr)
    print(f"   3. 进入后地址会跳到：{JUGUANG_HOME}", file=sys.stderr)
    print("   4. 然后重新跑：python3 auto_pipeline.py check", file=sys.stderr)
    session.navigate(PARTNER_HOME)
    # 把 Chrome 窗口前置
    subprocess.run(["osascript", "-e",
                    'tell application "Google Chrome" to activate'],
                   capture_output=True, check=False)
    session.close()
    sys.exit(2)


# ────────────────────────────────────────────────────────────
# API 调用（在浏览器上下文跑 fetch，绕开签名问题）
# ────────────────────────────────────────────────────────────

def fetch_report_data(session: CDPSession, start_date: str, end_date: str,
                      dimensions: list[str], metrics: list[str],
                      page_size: int = 500) -> list[dict]:
    """通过浏览器 fetch 聚光数据报表 API。"""
    js = f"""
    (async () => {{
        const results = [];
        let page = 1;
        const maxPages = 20;
        while (page <= maxPages) {{
            const resp = await fetch(
                'https://ad.xiaohongshu.com/api/leona/rtb/data/report?vSellerId={SELLER_ID}',
                {{
                    method: 'POST',
                    credentials: 'include',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{
                        startDate: '{start_date}',
                        endDate: '{end_date}',
                        dimensions: {json.dumps(dimensions)},
                        metrics: {json.dumps(metrics)},
                        page: page,
                        pageSize: {page_size},
                    }}),
                }}
            );
            const text = await resp.text();
            let data;
            try {{ data = JSON.parse(text); }} catch(e) {{ return {{error: 'parse', status: resp.status, raw: text.substring(0,500)}}; }}
            const items = data?.data?.list || data?.data?.records || data?.list || [];
            if (items.length === 0) break;
            results.push(...items);
            if (items.length < {page_size}) break;
            page++;
        }}
        return {{success: true, count: results.length, items: results}};
    }})()
    """
    return session.eval_js(js)


def fetch_data_for_date(session: CDPSession, target_date: str, granularity: str = "daily") -> dict:
    """
    抓取 target_date 当天的数据。
    granularity: daily | hourly
    """
    if granularity == "hourly":
        dims = ["hour", "campaign_id", "campaign_name", "creative_id", "creative_name"]
    else:
        dims = ["date", "campaign_id", "campaign_name", "creative_id", "creative_name"]
    metrics = ["cost", "impression", "click", "ctr", "cpc", "cpm", "interaction"]

    print(f"📡 调用聚光 API（{granularity}, {target_date}）...", file=sys.stderr)
    result = fetch_report_data(session, target_date, target_date, dims, metrics)
    return result


# ────────────────────────────────────────────────────────────
# 把 API 返回转成 Excel 兼容格式（让 juguang_daily.py / juguang_hourly.py 复用）
# ────────────────────────────────────────────────────────────

def api_items_to_csv(items: list[dict], out_path: Path, granularity: str = "daily") -> Path:
    """把 API 返回的 items 转成跟聚光手动导出 CSV 同结构的文件。"""
    import csv

    # API 字段 → Excel 列名映射（实际跑通后可能要调整）
    col_map_common = {
        "date": "时间",
        "hour": "小时",
        "campaign_name": "计划名称",
        "campaign_id": "计划ID",
        "creative_name": "创意名称",
        "creative_id": "创意ID",
        "cost": "消费",
        "impression": "展现量",
        "click": "点击量",
        "ctr": "点击率",
        "cpc": "平均点击成本",
        "cpm": "平均千次展现费用",
        "interaction": "互动量",
    }

    if not items:
        out_path.write_text("", encoding="utf-8")
        return out_path

    # 先扫描所有 key 决定输出列
    all_keys = set()
    for item in items:
        all_keys.update(item.keys())

    cols = [col_map_common.get(k, k) for k in all_keys]
    api_cols = list(all_keys)

    with out_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for item in items:
            row = [item.get(k, "") for k in api_cols]
            w.writerow(row)

    return out_path


# ────────────────────────────────────────────────────────────
# 串接日报/时报脚本
# ────────────────────────────────────────────────────────────

def run_daily(target_date: str, project: str):
    session = ensure_logged_in()
    try:
        result = fetch_data_for_date(session, target_date, granularity="daily")
        if not result or not result.get("success"):
            print(f"❌ API 调用失败：{result}", file=sys.stderr)
            sys.exit(3)

        items = result["items"]
        print(f"✅ 拿到 {len(items)} 条记录", file=sys.stderr)

        csv_path = RAW_DIR / f"api_daily_{project}_{target_date}.csv"
        api_items_to_csv(items, csv_path, granularity="daily")
        print(f"📁 落盘：{csv_path}", file=sys.stderr)

        # 调 juguang_daily.py
        cmd = [
            "python3", str(Path(__file__).parent / "juguang_daily.py"),
            str(csv_path),
            "--date", target_date,
            "--project", project,
            "--save", "--viz",
        ]
        subprocess.run(cmd, check=False)
    finally:
        session.close()


def run_hourly(target_date: str, hours_spec: str, project: str):
    session = ensure_logged_in()
    try:
        result = fetch_data_for_date(session, target_date, granularity="hourly")
        if not result or not result.get("success"):
            print(f"❌ API 调用失败：{result}", file=sys.stderr)
            sys.exit(3)

        items = result["items"]
        print(f"✅ 拿到 {len(items)} 条记录", file=sys.stderr)

        csv_path = RAW_DIR / f"api_hourly_{project}_{target_date}.csv"
        api_items_to_csv(items, csv_path, granularity="hourly")
        print(f"📁 落盘：{csv_path}", file=sys.stderr)

        cmd = [
            "python3", str(Path(__file__).parent / "juguang_hourly.py"),
            str(csv_path),
            "--hours", hours_spec,
            "--date", target_date,
            "--project", project,
        ]
        subprocess.run(cmd, check=False)
    finally:
        session.close()


# ────────────────────────────────────────────────────────────
# CLI
# ────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="聚光全自动管线（CDP + 自动出报）")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_daily = sub.add_parser("daily", help="出日报")
    p_daily.add_argument("--date", help="目标日期 YYYY-MM-DD，默认昨天")
    p_daily.add_argument("--project", default="蔡司眼镜")

    p_hourly = sub.add_parser("hourly", help="出时报")
    p_hourly.add_argument("--hours", default="8-10", help="时段 例: 8-10")
    p_hourly.add_argument("--date", help="目标日期 YYYY-MM-DD，默认今天")
    p_hourly.add_argument("--project", default="蔡司眼镜")

    p_check = sub.add_parser("check", help="只检查登录态")

    args = parser.parse_args()

    if args.cmd == "check":
        ensure_logged_in()
        print("✅ 一切就绪。", file=sys.stderr)
        return

    if args.cmd == "daily":
        target = args.date or (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        run_daily(target, args.project)
    elif args.cmd == "hourly":
        target = args.date or datetime.now().strftime("%Y-%m-%d")
        run_hourly(target, args.hours, args.project)


if __name__ == "__main__":
    main()
