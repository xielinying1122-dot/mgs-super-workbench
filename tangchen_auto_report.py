#!/usr/bin/env python3
"""汤臣倍健-MD 自动日报生成脚本
从聚光导出的清洗数据中读取最新一天数据，输出文字日报。
用法: python3 tangchen_auto_report.py [--date 2026-05-07]
"""
import pandas as pd
import os
import sys
import glob
from datetime import datetime, timedelta

# 数据目录
PROCESSED = os.path.expanduser('~/juguang-automation/data/processed/')
RAW = os.path.expanduser('~/juguang-automation/data/raw/')

def safe_extract(s, pos):
    if pd.isna(s): return None
    parts = str(s).split('-')
    return parts[pos] if len(parts) > pos else None

def find_latest_data():
    """找到最新的清洗后数据文件"""
    # 优先查找已处理的最终数据
    final_file = os.path.join(PROCESSED, 'tangchen_0505_0507_raw_final.csv')
    if os.path.exists(final_file):
        return final_file
    # 查找聚光清洗后的文件
    pattern = os.path.join(PROCESSED, 'clean_creative_*.csv')
    files = glob.glob(pattern)
    if not files:
        # 尝试从raw目录找xlsx并清洗
        raw_pattern = os.path.join(RAW, '*.xlsx')
        raw_files = glob.glob(raw_pattern)
        if raw_files:
            os.system(f'cd ~/juguang-automation && .venv/bin/python main.py --mode clean')
            files = glob.glob(pattern)
    if not files:
        return None
    files.sort(key=os.path.getmtime, reverse=True)
    return files[0]

def generate_report(date_str=None):
    data_file = find_latest_data()
    if not data_file:
        return "⚠️ 未找到汤臣倍健数据文件，请先导出聚光数据"

    df = pd.read_csv(data_file)
    df['date'] = pd.to_datetime(df['date'])

    # 如果指定日期，只取该日
    if date_str:
        target = pd.Timestamp(date_str)
        df_day = df[df['date'] == target].copy()
        if df_day.empty:
            return f"⚠️ 数据中没有 {date_str} 的记录"
    else:
        # 取最新一天
        latest = df['date'].max()
        df_day = df[df['date'] == latest].copy()
        date_str = latest.strftime('%Y-%m-%d')

    # 提取字段
    df_day['crowd'] = df_day['unit'].apply(lambda x: str(x).split('-')[-1] if pd.notna(x) else None)
    df_day['ad_type'] = df_day['creative'].apply(lambda x: safe_extract(x, 2))
    df_day['mode'] = df_day['creative'].apply(lambda x: safe_extract(x, 3))
    df_day['creator'] = df_day['creative'].apply(lambda x: safe_extract(x, 4))

    total_cost = df_day['cost'].sum()
    total_imp = df_day['impressions'].sum()
    total_clk = df_day['clicks'].sum()
    total_int = df_day['interactions'].sum()

    if total_imp == 0:
        return f"⚠️ {date_str} 数据为空"

    ctr = total_clk / total_imp * 100
    cpc = total_cost / total_clk if total_clk > 0 else 0
    cpm = total_cost / total_imp * 1000
    cpe = total_cost / total_int if total_int > 0 else 0

    # 人群TOP5
    valid_crowds = ['智能人群','母亲节人群','品牌人群','健身减脂人群',
                    '蛋白粉意向人群','高消耗中年','白富美养生人群',
                    '爆肝青年人群','保健品关键词行为','蛋白粉关键词行为']
    df_valid = df_day[df_day['crowd'].isin(valid_crowds)]
    crowd_stats = df_valid.groupby('crowd').agg(
        cost=('cost','sum'), impressions=('impressions','sum'),
        clicks=('clicks','sum'), interactions=('interactions','sum')
    ).reset_index().sort_values('cost', ascending=False).head(5)

    crowd_lines = []
    for _, r in crowd_stats.iterrows():
        pct = r['cost'] / total_cost * 100
        c = r['clicks'] / r['impressions'] * 100 if r['impressions'] > 0 else 0
        cp = r['cost'] / r['clicks'] if r['clicks'] > 0 else 0
        crowd_lines.append(f"  {r['crowd']}: 消耗{r['cost']:.0f}({pct:.0f}%)、CTR{c:.1f}%、CPC{cp:.2f}")

    # 广告类型
    ad_stats = df_day.groupby('ad_type').agg(
        cost=('cost','sum'), impressions=('impressions','sum'),
        clicks=('clicks','sum'), interactions=('interactions','sum')
    ).reset_index().sort_values('cost', ascending=False)

    ad_lines = []
    for _, r in ad_stats.iterrows():
        if pd.notna(r['ad_type']):
            pct = r['cost'] / total_cost * 100
            c = r['clicks'] / r['impressions'] * 100 if r['impressions'] > 0 else 0
            cp = r['cost'] / r['clicks'] if r['clicks'] > 0 else 0
            ad_lines.append(f"  {r['ad_type']}: 消耗{r['cost']:.0f}({pct:.0f}%)、CTR{c:.1f}%、CPC{cp:.2f}")

    # 达人
    creator_stats = df_day.groupby('creator').agg(
        cost=('cost','sum'), impressions=('impressions','sum'),
        clicks=('clicks','sum'), interactions=('interactions','sum')
    ).reset_index().sort_values('cost', ascending=False)

    creator_lines = []
    for _, r in creator_stats.iterrows():
        if pd.notna(r['creator']):
            pct = r['cost'] / total_cost * 100
            c = r['clicks'] / r['impressions'] * 100 if r['impressions'] > 0 else 0
            creator_lines.append(f"  {r['creator']}: 消耗{r['cost']:.0f}({pct:.0f}%)、CTR{c:.1f}%")

    report = f"""【汤臣倍健-MD投放日报-{date_str}】

👉常规种草维度：
消耗{total_cost:.0f}、展现{total_imp:.0f}、点击{total_clk:.0f}、CTR{ctr:.1f}%、CPC{cpc:.2f}、CPM{cpm:.0f}、CPE{cpe:.2f}

👉人群定向：
{chr(10).join(crowd_lines)}

👉广告类型：
{chr(10).join(ad_lines)}

👉达人表现：
{chr(10).join(creator_lines)}"""

    return report

if __name__ == '__main__':
    date_arg = None
    if len(sys.argv) > 2 and sys.argv[1] == '--date':
        date_arg = sys.argv[2]
    print(generate_report(date_arg))
