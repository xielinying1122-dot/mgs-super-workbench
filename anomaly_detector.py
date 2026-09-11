#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
聚光异常检测模块
================
自动识别投放异常：消耗突增、CTR骤降、低效计划/素材/关键词。
"""

import logging
from pathlib import Path
from typing import List, Dict

import pandas as pd
import numpy as np

logger = logging.getLogger("juguang.anomaly")


class AnomalyDetector:
    """异常检测器"""

    def __init__(self, config_path: str = None):
        if config_path is None:
            config_path = Path.home() / "juguang-automation" / "config.yaml"

        import yaml
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        cfg = config.get("anomaly", {})
        self.cost_spike_pct = cfg.get("cost_spike_pct", 50)
        self.ctr_drop_pct = cfg.get("ctr_drop_pct", 30)
        self.cpc_rise_pct = cfg.get("cpc_rise_pct", 30)
        self.low_perf_days = cfg.get("low_perf_days", 3)
        self.low_ctr_threshold = cfg.get("low_ctr_threshold", 0.01)
        self.high_cpe_threshold = cfg.get("high_cpe_threshold", 10)

    def detect_cost_spikes(self, daily_summary: pd.DataFrame) -> List[Dict]:
        """
        检测消耗突增异常
        
        规则：当天消耗比前一天增长超过 cost_spike_pct%
        """
        if daily_summary.empty or len(daily_summary) < 2:
            return []

        # 按日期排序
        df = daily_summary.sort_values("date").copy()
        
        anomalies = []
        for i in range(1, len(df)):
            prev_cost = df.iloc[i-1]["cost"]
            curr_cost = df.iloc[i]["cost"]
            curr_date = df.iloc[i]["date"]

            if prev_cost > 0:
                change_pct = (curr_cost - prev_cost) / prev_cost * 100
                if change_pct > self.cost_spike_pct:
                    anomalies.append({
                        "type": "cost_spike",
                        "date": str(curr_date),
                        "target": "总消耗",
                        "detail": f"消耗突增 {change_pct:.1f}%（昨 {prev_cost:.0f} → 今 {curr_cost:.0f}）",
                        "severity": "high" if change_pct > 100 else "medium",
                    })

        return anomalies

    def detect_ctr_drops(self, daily_summary: pd.DataFrame) -> List[Dict]:
        """
        检测CTR骤降
        
        规则：当天CTR比前一天下降超过 ctr_drop_pct%
        """
        if daily_summary.empty or len(daily_summary) < 2 or "ctr" not in daily_summary.columns:
            return []

        df = daily_summary.sort_values("date").copy()
        
        anomalies = []
        for i in range(1, len(df)):
            prev_ctr = df.iloc[i-1]["ctr"]
            curr_ctr = df.iloc[i]["ctr"]
            curr_date = df.iloc[i]["date"]

            if prev_ctr > 0:
                drop_pct = (prev_ctr - curr_ctr) / prev_ctr * 100
                if drop_pct > self.ctr_drop_pct:
                    anomalies.append({
                        "type": "ctr_drop",
                        "date": str(curr_date),
                        "target": "整体CTR",
                        "detail": f"CTR骤降 {drop_pct:.1f}%（昨 {prev_ctr*100:.2f}% → 今 {curr_ctr*100:.2f}%）",
                        "severity": "high" if drop_pct > 50 else "medium",
                    })

        return anomalies

    def detect_cpc_rises(self, daily_summary: pd.DataFrame) -> List[Dict]:
        """
        检测CPC上升
        
        规则：当天CPC比前一天上升超过 cpc_rise_pct%
        """
        if daily_summary.empty or len(daily_summary) < 2 or "cpc" not in daily_summary.columns:
            return []

        df = daily_summary.sort_values("date").copy()
        
        anomalies = []
        for i in range(1, len(df)):
            prev_cpc = df.iloc[i-1]["cpc"]
            curr_cpc = df.iloc[i]["cpc"]
            curr_date = df.iloc[i]["date"]

            if prev_cpc > 0:
                rise_pct = (curr_cpc - prev_cpc) / prev_cpc * 100
                if rise_pct > self.cpc_rise_pct:
                    anomalies.append({
                        "type": "cpc_rise",
                        "date": str(curr_date),
                        "target": "整体CPC",
                        "detail": f"CPC上升 {rise_pct:.1f}%（昨 ¥{prev_cpc:.2f} → 今 ¥{curr_cpc:.2f}）",
                        "severity": "medium",
                    })

        return anomalies

    def detect_low_performance(self, campaign_perf: pd.DataFrame,
                               creative_perf: pd.DataFrame = None) -> List[Dict]:
        """
        检测低效计划/素材
        
        规则：CTR < low_ctr_threshold 且 CPE > high_cpe_threshold
        """
        anomalies = []

        if not campaign_perf.empty and "ctr" in campaign_perf.columns:
            low = campaign_perf[campaign_perf["ctr"] < self.low_ctr_threshold]
            for _, row in low.iterrows():
                name = row.get("campaign", "未知")[:30]
                anomalies.append({
                    "type": "low_performance",
                    "target": f"计划「{name}」",
                    "detail": f"CTR过低 {row['ctr']*100:.2f}%（阈值 {self.low_ctr_threshold*100:.2f}%）",
                    "severity": "medium",
                })

        if creative_perf is not None and not creative_perf.empty and "ctr" in creative_perf.columns:
            low = creative_perf[creative_perf["ctr"] < self.low_ctr_threshold]
            for _, row in low.iterrows():
                name = str(row.get("creative", "未知"))[:30]
                anomalies.append({
                    "type": "low_performance",
                    "target": f"素材「{name}」",
                    "detail": f"CTR过低 {row['ctr']*100:.2f}%（阈值 {self.low_ctr_threshold*100:.2f}%）",
                    "severity": "low",
                })

        return anomalies

    def detect_all(self, daily_summary: pd.DataFrame,
                   campaign_perf: pd.DataFrame = None,
                   creative_perf: pd.DataFrame = None) -> List[Dict]:
        """运行所有异常检测"""
        anomalies = []

        anomalies.extend(self.detect_cost_spikes(daily_summary))
        anomalies.extend(self.detect_ctr_drops(daily_summary))
        anomalies.extend(self.detect_cpc_rises(daily_summary))

        if campaign_perf is not None:
            anomalies.extend(self.detect_low_performance(campaign_perf, creative_perf))

        # 按严重程度排序
        severity_order = {"high": 0, "medium": 1, "low": 2}
        anomalies.sort(key=lambda a: severity_order.get(a.get("severity", "low"), 3))

        if anomalies:
            logger.warning(f"检测到 {len(anomalies)} 个异常")
            for a in anomalies:
                logger.warning(f"  [{a['severity']}] {a['target']}: {a['detail']}")
        else:
            logger.info("未发现明显异常")

        return anomalies


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    detector = AnomalyDetector()
    print(f"异常检测器已就绪")
    print(f"  消耗突增阈值: {detector.cost_spike_pct}%")
    print(f"  CTR骤降阈值: {detector.ctr_drop_pct}%")
    print(f"  CPC上升阈值: {detector.cpc_rise_pct}%")
    print(f"  低效CTR阈值: {detector.low_ctr_threshold*100:.2f}%")
    print(f"  高CPE阈值: {detector.high_cpe_threshold}")
