#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
聚光日报生成模块
================
从聚合数据自动生成日报初稿。
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger("juguang.report")


class ReportGenerator:
    """日报生成器"""

    def __init__(self, config_path: str = None):
        if config_path is None:
            config_path = Path.home() / "juguang-automation" / "config.yaml"

        import yaml
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        cfg = config.get("report", {})
        self.template_dir = Path(cfg.get("template_dir", "~/juguang-automation/templates")).expanduser()
        self.output_dir = Path(cfg.get("output_dir", "~/juguang-automation/data/reports")).expanduser()
        self.template_file = cfg.get("template_file", "daily_report.txt")
        self.project_name = cfg.get("project_name", "")
        self.month_budget = cfg.get("month_budget", 0)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _fmt_money(self, val) -> str:
        """格式化金额"""
        if pd.isna(val) or val is None:
            return "¥0"
        return f"¥{val:,.2f}"

    def _fmt_pct(self, val) -> str:
        """格式化百分比"""
        if pd.isna(val) or val is None:
            return "0.00%"
        return f"{val*100:.2f}%"

    def _fmt_number(self, val) -> str:
        """格式化数字"""
        if pd.isna(val) or val is None:
            return "0"
        return f"{val:,.0f}"

    def _calc_mom(self, curr, prev) -> str:
        """计算环比变化"""
        if prev is None or prev == 0 or curr is None:
            return "→ 无环比数据"
        change = (curr - prev) / prev * 100
        arrow = "↑" if change > 0 else ("↓" if change < 0 else "→")
        return f"{arrow} {change:+.2f}%"

    def generate(self, daily_summary: pd.DataFrame,
                 ad_type_summary: pd.DataFrame,
                 campaign_perf: pd.DataFrame,
                 creative_perf: pd.DataFrame,
                 keyword_perf: pd.DataFrame = None,
                 anomalies: list = None,
                 date: str = None) -> str:
        """
        生成日报文本
        
        Args:
            daily_summary: 日汇总DataFrame
            ad_type_summary: 广告类型汇总
            campaign_perf: 计划表现
            creative_perf: 素材表现
            keyword_perf: 关键词表现
            anomalies: 异常列表 [{"type": "cost_spike", "target": "...", "detail": "..."}, ...]
            date: 日期 YYYY-MM-DD
        
        Returns:
            日报文本
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        date_dt = datetime.strptime(date, "%Y-%m-%d")
        date_cn = date_dt.strftime("%m月%d日")
        weekday = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][date_dt.weekday()]

        lines = []
        lines.append("=" * 50)
        lines.append(f"【聚光投放日报】{date_cn} {weekday}")
        lines.append(f"项目：{self.project_name or '请配置项目名称'}")
        lines.append(f"数据日期：{date}")
        lines.append("=" * 50)

        # 一、核心数据
        lines.append("")
        lines.append("一、核心数据")
        lines.append("-" * 20)

        if not daily_summary.empty:
            today = daily_summary[daily_summary["date"] == date]
            if not today.empty:
                row = today.iloc[0]
                lines.append(f"  总消耗：{self._fmt_money(row.get('cost', 0))}")
                lines.append(f"  总展现：{self._fmt_number(row.get('impressions', 0))}")
                lines.append(f"  总点击：{self._fmt_number(row.get('clicks', 0))}")
                lines.append(f"  CTR：{self._fmt_pct(row.get('ctr', 0))}")
                lines.append(f"  CPC：{self._fmt_money(row.get('cpc', 0))}")
                if "cpe" in row.index:
                    lines.append(f"  CPE：{self._fmt_money(row.get('cpe', 0))}")

                # 环比
                yesterday = (date_dt - timedelta(days=1)).strftime("%Y-%m-%d")
                yest_data = daily_summary[daily_summary["date"] == yesterday]
                if not yest_data.empty:
                    yest = yest_data.iloc[0]
                    lines.append("")
                    lines.append("  【环比昨日】")
                    lines.append(f"  消耗：{self._calc_mom(row.get('cost'), yest.get('cost'))}")
                    lines.append(f"  CTR：{self._calc_mom(row.get('ctr'), yest.get('ctr'))}")
                    lines.append(f"  CPC：{self._calc_mom(row.get('cpc'), yest.get('cpc'))}")
            else:
                lines.append(f"  ⚠️ 未找到 {date} 的数据")
        else:
            lines.append("  ⚠️ 暂无数据")

        # 月度预算进度
        if self.month_budget > 0 and not daily_summary.empty:
            month_start = date_dt.replace(day=1).strftime("%Y-%m-%d")
            month_data = daily_summary[daily_summary["date"] >= month_start]
            month_cost = month_data["cost"].sum() if not month_data.empty else 0
            progress = month_cost / self.month_budget * 100
            days_passed = date_dt.day
            days_total = (date_dt.replace(month=date_dt.month % 12 + 1, day=1) - timedelta(days=1)).day
            time_progress = days_passed / days_total * 100
            lines.append(f"  月度消耗：{self._fmt_money(month_cost)} / {self._fmt_money(self.month_budget)} ({progress:.1f}%)")
            lines.append(f"  时间进度：{time_progress:.1f}% {'⚠️ 超速' if progress > time_progress else '✓ 正常'}")

        # 二、分广告类型
        lines.append("")
        lines.append("二、分广告类型表现")
        lines.append("-" * 20)

        if not ad_type_summary.empty:
            for _, row in ad_type_summary.iterrows():
                ad_type = row.get("ad_category", row.get("ad_type", "未知"))
                lines.append(f"  【{ad_type}】")
                lines.append(f"    消耗：{self._fmt_money(row.get('cost'))} ({row.get('cost_pct', 0):.1f}%)")
                lines.append(f"    CTR：{self._fmt_pct(row.get('ctr'))}")
                lines.append(f"    CPC：{self._fmt_money(row.get('cpc'))}")
                if "cpe" in row.index:
                    lines.append(f"    CPE：{self._fmt_money(row.get('cpe'))}")
        else:
            lines.append("  暂无分类型数据")

        # 三、Top 计划
        lines.append("")
        lines.append("三、消耗Top 5 计划")
        lines.append("-" * 20)

        if not campaign_perf.empty:
            for _, row in campaign_perf.head(5).iterrows():
                name = row.get("campaign", "")[:30]
                lines.append(f"  {row.get('rank', '?')}. {name}")
                lines.append(f"     消耗：{self._fmt_money(row.get('cost'))} | CTR：{self._fmt_pct(row.get('ctr'))} | CPC：{self._fmt_money(row.get('cpc'))}")
        else:
            lines.append("  暂无计划数据")

        # 四、Top 素材
        lines.append("")
        lines.append("四、消耗Top 5 素材")
        lines.append("-" * 20)

        if not creative_perf.empty:
            for _, row in creative_perf.head(5).iterrows():
                name = str(row.get("creative", ""))[:30]
                lines.append(f"  {row.get('rank', '?')}. {name}")
                lines.append(f"     消耗：{self._fmt_money(row.get('cost'))} | CTR：{self._fmt_pct(row.get('ctr'))} | CPC：{self._fmt_money(row.get('cpc'))}")
        else:
            lines.append("  暂无素材数据")

        # 五、关键词表现
        if keyword_perf is not None and not keyword_perf.empty:
            lines.append("")
            lines.append("五、关键词Top 5")
            lines.append("-" * 20)
            for _, row in keyword_perf.head(5).iterrows():
                kw = row.get("keyword", "")[:20]
                lines.append(f"  {row.get('rank', '?')}. {kw} → 消耗：{self._fmt_money(row.get('cost'))} | CTR：{self._fmt_pct(row.get('ctr'))}")

        # 六、异常识别
        lines.append("")
        lines.append("六、异常识别")
        lines.append("-" * 20)

        if anomalies:
            for a in anomalies:
                lines.append(f"  ⚠️ {a.get('target', '')}: {a.get('detail', '')}")
        else:
            lines.append("  ✓ 未发现明显异常")

        # 七、今日建议
        lines.append("")
        lines.append("七、今日建议")
        lines.append("-" * 20)
        lines.append("  （此处需人工填写判断）")
        lines.append("  1. 继续放量：")
        lines.append("  2. 暂停观察：")
        lines.append("  3. 关键词优化：")

        lines.append("")
        lines.append("=" * 50)
        lines.append(f"自动生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}")
        lines.append("=" * 50)

        return "\n".join(lines)

    def save(self, report: str, date: str = None) -> str:
        """保存日报"""
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        date_compact = date.replace("-", "")
        path = self.output_dir / f"日报_{date_compact}.txt"
        path.write_text(report, encoding="utf-8")
        logger.info(f"日报已保存: {path}")
        return str(path)

    def generate_and_save(self, daily_summary: pd.DataFrame,
                          ad_type_summary: pd.DataFrame,
                          campaign_perf: pd.DataFrame,
                          creative_perf: pd.DataFrame,
                          keyword_perf: pd.DataFrame = None,
                          anomalies: list = None,
                          date: str = None) -> tuple:
        """生成并保存日报"""
        report = self.generate(
            daily_summary, ad_type_summary, campaign_perf,
            creative_perf, keyword_perf, anomalies, date
        )
        path = self.save(report, date)
        return report, path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    gen = ReportGenerator()
    print(f"日报生成器已就绪")
    print(f"项目：{gen.project_name or '未配置'}")
    print(f"输出目录：{gen.output_dir}")
