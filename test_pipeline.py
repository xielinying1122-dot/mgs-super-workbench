#!/usr/bin/env python3
"""测试聚光自动化流水线"""
import sys, os, logging
os.chdir(os.path.expanduser("~/juguang-automation"))
sys.path.insert(0, ".")

logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
logger = logging.getLogger("test")

import pandas as pd
from data_cleaner import DataCleaner
from aggregator import Aggregator
from anomaly_detector import AnomalyDetector
from report_generator import ReportGenerator

# 读取数据
raw = os.path.expanduser("~/juguang-automation/data/raw/夸克开学季小红书投放日报0915-不对客.xlsx")
df = pd.read_excel(raw, sheet_name="创意-投放数据")
logger.info(f"读取: {len(df)}条 | 日期: {df['时间'].min().date()}~{df['时间'].max().date()}")

# 清洗
cleaner = DataCleaner()
clean_df = cleaner.clean(df)
logger.info(f"清洗后: {len(clean_df)}条")

# 聚合
agg = Aggregator()
target = "2025-09-14"
results = agg.run_all(clean_df, target)

# 异常
detector = AnomalyDetector()
anomalies = detector.detect_all(
    results["daily_summary"], results["campaign_performance"], results["creative_performance"])

# 日报
gen = ReportGenerator()
gen.project_name = "夸克扫描王"
gen.month_budget = 3000000
report, path = gen.generate_and_save(
    results["daily_summary"], results["ad_type_summary"],
    results["campaign_performance"], results["creative_performance"],
    results.get("keyword_performance"), anomalies, target)

# 输出摘要
print("\n" + "="*60)
daily = results["daily_summary"]
today = daily[daily["date"] == target]
if not today.empty:
    r = today.iloc[0]
    print(f"日期: {target}")
    print(f"消费: ¥{r['cost']:,.2f} | 展现: {r['impressions']:,.0f} | 点击: {r['clicks']:,.0f}")
    print(f"CTR: {r['ctr']*100:.2f}% | CPC: ¥{r['cpc']:.2f} | CPE: ¥{r['cpe']:.2f}")

print(f"\n广告类型:")
for _, row in results["ad_type_summary"].iterrows():
    t = row.get('ad_category', row.get('ad_type', '?'))
    print(f"  {t}: ¥{row['cost']:,.0f} ({row['cost_pct']:.0f}%) CTR {row['ctr']*100:.1f}%")

print(f"\nTop3 计划:")
for _, row in results["campaign_performance"].head(3).iterrows():
    print(f"  {row['rank']}. {str(row['campaign'])[:50]} | ¥{row['cost']:,.0f} CTR {row['ctr']*100:.1f}%")

print(f"\n异常: {len(anomalies)}个")
for a in anomalies:
    print(f"  [{a['severity']}] {a['target']}: {a['detail']}")

print(f"\n日报: {path}")
print("="*60)
