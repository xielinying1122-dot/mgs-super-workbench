import pandas as pd
import os

# 读取汤臣倍健数据文件
file_path = os.path.expanduser('~/Documents/红书工作/汤臣蛋白粉-5.4-5.10/汤臣蛋白粉日报数据-5.7.xlsx')

# 读取数据底表
df = pd.read_excel(file_path, sheet_name='数据底表')

# 从创意名称中提取信息
def extract_info(creative_name, position):
    if pd.isna(creative_name):
        return None
    parts = str(creative_name).split('-')
    if len(parts) > position:
        return parts[position]
    return None

# 提取达人、广告类型、人群定向
df['达人'] = df['创意名称'].apply(lambda x: extract_info(x, 4))
df['广告类型'] = df['创意名称'].apply(lambda x: extract_info(x, 2))
df['投放模式'] = df['创意名称'].apply(lambda x: extract_info(x, 3))

print("=== 汤臣倍健-MD 聚光投放深度分析 ===")
print(f"数据周期: {df['时间'].min().strftime('%Y-%m-%d')} 至 {df['时间'].max().strftime('%Y-%m-%d')}")
print(f"总消费: {df['消费'].sum():.2f}元")
print()

# 1. 按天趋势分析
print("=== 1. 按天趋势分析 ===")
daily_trend = df.groupby('时间').agg({
    '消费': 'sum',
    '展现量': 'sum',
    '点击量': 'sum',
    '点击率': 'mean',
    '平均点击成本': 'mean',
    '平均千次展现费用': 'mean',
    '互动量': 'sum'
}).reset_index()

for idx, row in daily_trend.iterrows():
    cpe = row['互动量'] / row['消费'] if row['消费'] > 0 else 0
    print(f"{row['时间'].strftime('%Y-%m-%d')}:")
    print(f"  消费: {row['消费']:.2f}元, 展现: {row['展现量']:,.0f}, 点击: {row['点击量']:,.0f}")
    print(f"  CTR: {row['点击率']:.3f}, CPC: {row['平均点击成本']:.2f}元, CPE: {cpe:.2f}元")
    print()

# 2. 按达人深度分析
print("=== 2. 按达人深度分析 ===")
creator_analysis = df.groupby('达人').agg({
    '消费': 'sum',
    '展现量': 'sum',
    '点击量': 'sum',
    '点击率': 'mean',
    '平均点击成本': 'mean',
    '平均千次展现费用': 'mean',
    '互动量': 'sum',
    '时间': 'nunique'  # 投放天数
}).reset_index()

creator_analysis = creator_analysis.dropna(subset=['达人'])
creator_analysis = creator_analysis.sort_values('消费', ascending=False)

print(f"达人数量: {len(creator_analysis)}")
for idx, row in creator_analysis.iterrows():
    cpe = row['互动量'] / row['消费'] if row['消费'] > 0 else 0
    cost_pct = row['消费'] / df['消费'].sum() * 100
    print(f"{row['达人']}:")
    print(f"  消费: {row['消费']:.2f}元 ({cost_pct:.1f}%)")
    print(f"  展现: {row['展现量']:,.0f}, 点击: {row['点击量']:,.0f}")
    print(f"  CTR: {row['点击率']:.3f}, CPC: {row['平均点击成本']:.2f}元")
    print(f"  CPE: {cpe:.2f}元, 投放天数: {row['时间']}")
    print()

# 3. 按广告类型分析
print("=== 3. 按广告类型分析 ===")
ad_type_analysis = df.groupby('广告类型').agg({
    '消费': 'sum',
    '展现量': 'sum',
    '点击量': 'sum',
    '点击率': 'mean',
    '平均点击成本': 'mean',
    '平均千次展现费用': 'mean',
    '互动量': 'sum'
}).reset_index()

for idx, row in ad_type_analysis.iterrows():
    if not pd.isna(row['广告类型']):
        cpe = row['互动量'] / row['消费'] if row['消费'] > 0 else 0
        cost_pct = row['消费'] / df['消费'].sum() * 100
        print(f"{row['广告类型']}:")
        print(f"  消费: {row['消费']:.2f}元 ({cost_pct:.1f}%)")
        print(f"  CTR: {row['点击率']:.3f}, CPC: {row['平均点击成本']:.2f}元, CPE: {cpe:.2f}元")
        print()

# 4. 按人群定向分析
print("=== 4. 按人群定向分析 ===")
crowd_analysis = df.groupby('人群定向').agg({
    '消费': 'sum',
    '展现量': 'sum',
    '点击量': 'sum',
    '点击率': 'mean',
    '平均点击成本': 'mean',
    '平均千次展现费用': 'mean',
    '互动量': 'sum'
}).reset_index()

crowd_analysis = crowd_analysis.sort_values('消费', ascending=False)
for idx, row in crowd_analysis.iterrows():
    if not pd.isna(row['人群定向']):
        cpe = row['互动量'] / row['消费'] if row['消费'] > 0 else 0
        cost_pct = row['消费'] / df['消费'].sum() * 100
        print(f"{row['人群定向']}:")
        print(f"  消费: {row['消费']:.2f}元 ({cost_pct:.1f}%)")
        print(f"  CTR: {row['点击率']:.3f}, CPC: {row['平均点击成本']:.2f}元, CPE: {cpe:.2f}元")
        print()

# 5. 按投放模式分析
print("=== 5. 按投放模式分析 ===")
mode_analysis = df.groupby('投放模式').agg({
    '消费': 'sum',
    '展现量': 'sum',
    '点击量': 'sum',
    '点击率': 'mean',
    '平均点击成本': 'mean',
    '平均千次展现费用': 'mean',
    '互动量': 'sum'
}).reset_index()

for idx, row in mode_analysis.iterrows():
    if not pd.isna(row['投放模式']):
        cpe = row['互动量'] / row['消费'] if row['消费'] > 0 else 0
        cost_pct = row['消费'] / df['消费'].sum() * 100
        print(f"{row['投放模式']}:")
        print(f"  消费: {row['消费']:.2f}元 ({cost_pct:.1f}%)")
        print(f"  CTR: {row['点击率']:.3f}, CPC: {row['平均点击成本']:.2f}元, CPE: {cpe:.2f}元")
        print()

# 6. 综合优化建议
print("=== 6. 综合优化建议 ===")

# 找出最佳表现组合
best_ctr = crowd_analysis.loc[crowd_analysis['点击率'].idxmax()]
best_cpc = crowd_analysis.loc[crowd_analysis['平均点击成本'].idxmin()]

print(f"最佳CTR人群: {best_ctr['人群定向']} (CTR {best_ctr['点击率']:.3f})")
print(f"最低CPC人群: {best_cpc['人群定向']} (CPC {best_cpc['平均点击成本']:.2f}元)")
print()

# 计算整体效率
total_impressions = df['展现量'].sum()
total_clicks = df['点击量'].sum()
total_cost = df['消费'].sum()
total_interactions = df['互动量'].sum()

print(f"整体效率:")
print(f"  总展现: {total_impressions:,.0f}")
print(f"  总点击: {total_clicks:,.0f}")
print(f"  总消费: {total_cost:.2f}元")
print(f"  总互动: {total_interactions}")
print(f"  整体CTR: {total_clicks/total_impressions:.3f}")
print(f"  整体CPC: {total_cost/total_clicks:.2f}元")
print(f"  整体CPE: {total_cost/total_interactions:.2f}元" if total_interactions > 0 else "  整体CPE: N/A")

# 保存深度分析报告
output_dir = os.path.expanduser('~/juguang-automation/data/processed/')

# 生成深度分析报告
cpe_text = f"{total_cost/total_interactions:.2f}元" if total_interactions > 0 else "N/A"

report = f"""汤臣倍健-MD 聚光投放深度分析报告
数据周期: {df['时间'].min().strftime('%Y-%m-%d')} 至 {df['时间'].max().strftime('%Y-%m-%d')}

一、核心数据汇总
- 总消费: {total_cost:.2f}元
- 总展现: {total_impressions:,.0f}
- 总点击: {total_clicks:,.0f}
- 总互动: {total_interactions}
- 整体CTR: {total_clicks/total_impressions:.3f}
- 整体CPC: {total_cost/total_clicks:.2f}元
- 整体CPE: {cpe_text}

二、最佳表现组合
- 最佳CTR人群: {best_ctr['人群定向']} (CTR {best_ctr['点击率']:.3f})
- 最低CPC人群: {best_cpc['人群定向']} (CPC {best_cpc['平均点击成本']:.2f}元)

三、优化建议
1. 扩大高CTR人群投放: {best_ctr['人群定向']}
2. 控制高CPC人群预算
3. 增加视频流内容投放
4. 测试更多达人分散风险"""

with open(os.path.join(output_dir, 'tangchen_deep_analysis.txt'), 'w', encoding='utf-8') as f:
    f.write(report)

print(f"\n深度分析报告已保存: {os.path.join(output_dir, 'tangchen_deep_analysis.txt')}")