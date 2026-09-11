#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
聚光数据聚合分析模块
===================
从清洗后的数据生成4张透视表：总览 / 广告类型 / 素材表现 / 关键词表现
"""

import logging
from pathlib import Path
from typing import Optional

import pandas as pd
import numpy as np

logger = logging.getLogger("juguang.aggregator")


class Aggregator:
    """数据聚合分析器"""

    def __init__(self, config_path: str = None):
        if config_path is None:
            config_path = Path.home() / "juguang-automation" / "config.yaml"

        import yaml
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        cfg = config.get("aggregate", {})
        self.output_dir = Path(cfg.get("output_dir", "~/juguang-automation/data/processed")).expanduser()
        self.output_tables = cfg.get("output_tables", {})
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def daily_summary(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        按日期汇总核心指标
        
        Returns DataFrame with columns:
        date, cost, impressions, clicks, ctr, cpc, cpe, interactions
        """
        if df.empty:
            return pd.DataFrame()

        # 确保字段存在
        required = ["date", "cost"]
        for col in required:
            if col not in df.columns:
                logger.warning(f"日汇总缺少字段: {col}")
                return pd.DataFrame()

        summary = df.groupby("date").agg({
            "cost": "sum",
            "impressions": "sum" if "impressions" in df.columns else None,
            "clicks": "sum" if "clicks" in df.columns else None,
            "interactions": "sum" if "interactions" in df.columns else None,
        }).reset_index()

        # 过滤掉None聚合
        summary = summary[[c for c in summary.columns if c in summary.columns]]

        # 计算衍生指标
        if "impressions" in summary.columns and "clicks" in summary.columns:
            summary["ctr"] = np.where(
                summary["impressions"] > 0,
                summary["clicks"] / summary["impressions"],
                0
            )
        if "cost" in summary.columns and "clicks" in summary.columns:
            summary["cpc"] = np.where(
                summary["clicks"] > 0,
                summary["cost"] / summary["clicks"],
                0
            )
        if "cost" in summary.columns and "interactions" in summary.columns:
            summary["cpe"] = np.where(
                summary["interactions"] > 0,
                summary["cost"] / summary["interactions"],
                0
            )

        summary = summary.round({
            "cost": 2, "ctr": 4, "cpc": 2, "cpe": 2
        })
        summary = summary.sort_values("date", ascending=False)

        logger.info(f"日汇总: {len(summary)} 天")
        return summary

    def ad_type_summary(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        按广告类型汇总
        
        Returns: ad_type, cost, impressions, clicks, ctr, cpc, cpe
        """
        if df.empty:
            return pd.DataFrame()

        type_col = None
        if "ad_category" in df.columns:
            type_col = "ad_category"
        elif "ad_type" in df.columns:
            type_col = "ad_type"
        else:
            return pd.DataFrame()

        agg_dict = {"cost": "sum"}
        for col in ["impressions", "clicks", "interactions"]:
            if col in df.columns:
                agg_dict[col] = "sum"

        summary = df.groupby(type_col).agg(agg_dict).reset_index()

        if "impressions" in summary.columns and "clicks" in summary.columns:
            summary["ctr"] = np.where(
                summary["impressions"] > 0,
                summary["clicks"] / summary["impressions"],
                0
            )
        if "cost" in summary.columns and "clicks" in summary.columns:
            summary["cpc"] = np.where(
                summary["clicks"] > 0,
                summary["cost"] / summary["clicks"],
                0
            )
        if "cost" in summary.columns and "interactions" in summary.columns:
            summary["cpe"] = np.where(
                summary["interactions"] > 0,
                summary["cost"] / summary["interactions"],
                0
            )

        summary = summary.sort_values("cost", ascending=False)
        summary["cost_pct"] = summary["cost"] / summary["cost"].sum() * 100
        summary = summary.round({"cost": 2, "ctr": 4, "cpc": 2, "cpe": 2, "cost_pct": 1})

        logger.info(f"广告类型汇总: {len(summary)} 种")
        return summary

    def campaign_performance(self, df: pd.DataFrame, top_n: int = 20) -> pd.DataFrame:
        """
        计划表现排名
        
        Returns: campaign, cost, impressions, clicks, ctr, cpc, cpe, rank
        """
        if df.empty:
            return pd.DataFrame()

        campaign_col = None
        for col in ["campaign", "campaignName", "campaign_name", "计划", "计划名称"]:
            if col in df.columns:
                campaign_col = col
                break
        if not campaign_col:
            return pd.DataFrame()

        agg_dict = {"cost": "sum"}
        for col in ["impressions", "clicks", "interactions"]:
            if col in df.columns:
                agg_dict[col] = "sum"

        perf = df.groupby(campaign_col).agg(agg_dict).reset_index()
        perf = perf.rename(columns={campaign_col: "campaign"})

        if "impressions" in perf.columns and "clicks" in perf.columns:
            perf["ctr"] = np.where(
                perf["impressions"] > 0,
                perf["clicks"] / perf["impressions"],
                0
            )
        if "cost" in perf.columns and "clicks" in perf.columns:
            perf["cpc"] = np.where(
                perf["clicks"] > 0,
                perf["cost"] / perf["clicks"],
                0
            )
        if "cost" in perf.columns and "interactions" in perf.columns:
            perf["cpe"] = np.where(
                perf["interactions"] > 0,
                perf["cost"] / perf["interactions"],
                0
            )

        perf["cost_pct"] = perf["cost"] / perf["cost"].sum() * 100
        perf = perf.sort_values("cost", ascending=False)
        perf["rank"] = range(1, len(perf) + 1)
        perf = perf.round({"cost": 2, "ctr": 4, "cpc": 2, "cpe": 2, "cost_pct": 1})

        if len(perf) > top_n:
            perf = perf.head(top_n)

        logger.info(f"计划排名: Top {len(perf)}")
        return perf

    def creative_performance(self, df: pd.DataFrame, top_n: int = 20) -> pd.DataFrame:
        """素材表现排名"""
        if df.empty:
            return pd.DataFrame()

        creative_col = None
        for col in ["creative", "creativeName", "creative_name", "创意", "创意名称"]:
            if col in df.columns:
                creative_col = col
                break
        if not creative_col:
            return pd.DataFrame()

        agg_dict = {"cost": "sum"}
        for col in ["impressions", "clicks", "interactions"]:
            if col in df.columns:
                agg_dict[col] = "sum"

        perf = df.groupby(creative_col).agg(agg_dict).reset_index()
        perf = perf.rename(columns={creative_col: "creative"})

        if "impressions" in perf.columns and "clicks" in perf.columns:
            perf["ctr"] = np.where(
                perf["impressions"] > 0,
                perf["clicks"] / perf["impressions"],
                0
            )
        if "cost" in perf.columns and "clicks" in perf.columns:
            perf["cpc"] = np.where(
                perf["clicks"] > 0,
                perf["cost"] / perf["clicks"],
                0
            )
        if "cost" in perf.columns and "interactions" in perf.columns:
            perf["cpe"] = np.where(
                perf["interactions"] > 0,
                perf["cost"] / perf["interactions"],
                0
            )

        perf["cost_pct"] = perf["cost"] / perf["cost"].sum() * 100
        perf = perf.sort_values("cost", ascending=False)
        perf["rank"] = range(1, len(perf) + 1)
        perf = perf.round({"cost": 2, "ctr": 4, "cpc": 2, "cpe": 2, "cost_pct": 1})

        if len(perf) > top_n:
            perf = perf.head(top_n)

        logger.info(f"素材排名: Top {len(perf)}")
        return perf

    def keyword_performance(self, df: pd.DataFrame, top_n: int = 20) -> pd.DataFrame:
        """关键词表现排名"""
        if df.empty:
            return pd.DataFrame()

        kw_col = None
        for col in ["keyword", "关键词", "搜索词", "query"]:
            if col in df.columns:
                kw_col = col
                break
        if not kw_col:
            return pd.DataFrame()

        agg_dict = {"cost": "sum"}
        for col in ["impressions", "clicks", "interactions"]:
            if col in df.columns:
                agg_dict[col] = "sum"

        perf = df.groupby(kw_col).agg(agg_dict).reset_index()
        perf = perf.rename(columns={kw_col: "keyword"})

        if "impressions" in perf.columns and "clicks" in perf.columns:
            perf["ctr"] = np.where(
                perf["impressions"] > 0,
                perf["clicks"] / perf["impressions"],
                0
            )
        if "cost" in perf.columns and "clicks" in perf.columns:
            perf["cpc"] = np.where(
                perf["clicks"] > 0,
                perf["cost"] / perf["clicks"],
                0
            )

        perf["cost_pct"] = perf["cost"] / perf["cost"].sum() * 100
        perf = perf.sort_values("cost", ascending=False)
        perf["rank"] = range(1, len(perf) + 1)
        perf = perf.round({"cost": 2, "ctr": 4, "cpc": 2, "cost_pct": 1})

        if len(perf) > top_n:
            perf = perf.head(top_n)

        logger.info(f"关键词排名: Top {len(perf)}")
        return perf

    def run_all(self, df: pd.DataFrame, date_str: str = "") -> dict:
        """
        运行所有聚合分析
        
        Returns:
            {
                "daily_summary": DataFrame,
                "ad_type_summary": DataFrame,
                "campaign_performance": DataFrame,
                "creative_performance": DataFrame,
                "keyword_performance": DataFrame,
            }
        """
        results = {}

        results["daily_summary"] = self.daily_summary(df)
        results["ad_type_summary"] = self.ad_type_summary(df)
        results["campaign_performance"] = self.campaign_performance(df)
        results["creative_performance"] = self.creative_performance(df)
        results["keyword_performance"] = self.keyword_performance(df)

        # 保存所有结果表
        date_prefix = f"_{date_str}" if date_str else ""
        for key, tbl_df in results.items():
            if not tbl_df.empty:
                fname = self.output_tables.get(key, f"{key}.csv")
                fname = fname.replace(".csv", f"{date_prefix}.csv")
                path = self.output_dir / fname
                tbl_df.to_csv(path, index=False, encoding="utf-8-sig")
                logger.info(f"保存: {path}")

        return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    agg = Aggregator()
    # 示例：从清洗目录读取数据
    import glob
    csv_files = glob.glob(str(agg.output_dir / "clean_*.csv"))
    if csv_files:
        df = pd.concat([pd.read_csv(f) for f in csv_files], ignore_index=True)
        results = agg.run_all(df)
        print("聚合完成:", list(results.keys()))
    else:
        print("未找到清洗数据")
