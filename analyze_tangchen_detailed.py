import pandas as pd
import os

# 读取汤臣倍健数据文件
file_path = os.path.expanduser('~/Documents/红书工作/汤臣蛋白粉-5.4-5.10/汤臣蛋白粉日报数据-5.7.xlsx')

# 读取数据底表
df = pd.read_excel(file_path, sheet_name='数据底表')

# 从创意名称中提取达人信息
def extract_creator(creative_name):
    if pd.isna(creative_name):
        return None
    parts = str(creative_name).split('-')
    if len(parts) >= 5:
        return parts[4]  # 达人信息在第5个位置
    return None

df['达人'] = df['创意名称'].apply(extract_creator)

# 创建详细的日报数据
print("=== 汤臣倍健-MD 聚光投放日报 ===")
print(f"数据周期: {df['时间'].min().strftime('%Y-%m-%d')} 至 {df['时间'].max().strftime('%Y-%m-%d')}")
print(f"总消费: {df['消费'].sum():.2f}元")
print()

# 按天详细分析
print("=== 按天详细分析 ===")
daily_data = []
for date in sorted(df['时间'].unique()):
    date_df = df[df['时间'] == date]
    
    daily_stats = {
        '日期': date.strftime('%Y-%m-%d'),
        '消费': date_df['消费'].sum(),
        '展现量': date_df['展现量'].sum(),
        '点击量': date_df['点击量'].sum(),
        '点击率': date_df['点击率'].mean(),
        '平均点击成本': date_df['平均点击成本'].mean(),
        '平均千次展现费用': date_df['平均千次展现费用'].mean(),
        '互动量': date_df['互动量'].sum(),
        '达人数量': date_df['达人'].nunique()
    }
    daily_data.append(daily_stats)
    
    print(f"{date.strftime('%Y-%m-%d')}:")
    print(f"  消费: {daily_stats['消费']:.2f}元")
    print(f"  展现: {daily_stats['展现量']:,.0f}")
    print(f"  点击: {daily_stats['点击量']:,.0f}")
    print(f"  CTR: {daily_stats['点击率']:.3f}")
    print(f"  CPC: {daily_stats['平均点击成本']:.2f}元")
    print(f"  CPM: {daily_stats['平均千次展现费用']:.2f}元")
    print(f"  互动量: {daily_stats['互动量']}")
    print(f"  达人数量: {daily_stats['达人数量']}")
    print()

# 按达人详细分析
print("=== 按达人详细分析 ===")
creator_data = []
# 过滤掉NaN值并排序
creators = [c for c in df['达人'].unique() if not pd.isna(c)]
for creator in sorted(creators):
        
    creator_df = df[df['达人'] == creator]
    
    creator_stats = {
        '达人': creator,
        '消费': creator_df['消费'].sum(),
        '展现量': creator_df['展现量'].sum(),
        '点击量': creator_df['点击量'].sum(),
        '点击率': creator_df['点击率'].mean(),
        '平均点击成本': creator_df['平均点击成本'].mean(),
        '平均千次展现费用': creator_df['平均千次展现费用'].mean(),
        '互动量': creator_df['互动量'].sum(),
        '投放天数': creator_df['时间'].nunique()
    }
    creator_data.append(creator_stats)
    
    print(f"达人: {creator}")
    print(f"  消费: {creator_stats['消费']:.2f}元 ({creator_stats['消费']/df['消费'].sum()*100:.1f}%)")
    print(f"  展现: {creator_stats['展现量']:,.0f}")
    print(f"  点击: {creator_stats['点击量']:,.0f}")
    print(f"  CTR: {creator_stats['点击率']:.3f}")
    print(f"  CPC: {creator_stats['平均点击成本']:.2f}元")
    print(f"  CPM: {creator_stats['平均千次展现费用']:.2f}元")
    print(f"  互动量: {creator_stats['互动量']}")
    print(f"  投放天数: {creator_stats['投放天数']}")
    print()

# 按天+达人详细分析
print("=== 按天+达人详细分析 ===")
daily_creator_data = []
for date in sorted(df['时间'].unique()):
    date_str = date.strftime('%Y-%m-%d')
    date_df = df[df['时间'] == date]
    
    # 过滤掉NaN值并排序
    creators = [c for c in date_df['达人'].unique() if not pd.isna(c)]
    for creator in sorted(creators):
            
        creator_df = date_df[date_df['达人'] == creator]
        
        stats = {
            '日期': date_str,
            '达人': creator,
            '消费': creator_df['消费'].sum(),
            '展现量': creator_df['展现量'].sum(),
            '点击量': creator_df['点击量'].sum(),
            '点击率': creator_df['点击率'].mean(),
            '平均点击成本': creator_df['平均点击成本'].mean(),
            '平均千次展现费用': creator_df['平均千次展现费用'].mean(),
            '互动量': creator_df['互动量'].sum()
        }
        daily_creator_data.append(stats)
        
        print(f"{date_str} - {creator}:")
        print(f"  消费: {stats['消费']:.2f}元")
        print(f"  CTR: {stats['点击率']:.3f}, CPC: {stats['平均点击成本']:.2f}元")

# 保存详细数据
output_dir = os.path.expanduser('~/juguang-automation/data/processed/')
os.makedirs(output_dir, exist_ok=True)

# 保存按天数据
daily_df = pd.DataFrame(daily_data)
daily_df.to_csv(os.path.join(output_dir, 'tangchen_daily_detailed.csv'), index=False, encoding='utf-8-sig')

# 保存按达人数据
creator_df = pd.DataFrame(creator_data)
creator_df.to_csv(os.path.join(output_dir, 'tangchen_creator_detailed.csv'), index=False, encoding='utf-8-sig')

# 保存按天+达人数据
daily_creator_df = pd.DataFrame(daily_creator_data)
daily_creator_df.to_csv(os.path.join(output_dir, 'tangchen_daily_creator_detailed.csv'), index=False, encoding='utf-8-sig')

print(f"\n=== 数据文件已保存 ===")
print(f"按天详细数据: {os.path.join(output_dir, 'tangchen_daily_detailed.csv')}")
print(f"按达人详细数据: {os.path.join(output_dir, 'tangchen_creator_detailed.csv')}")
print(f"按天+达人详细数据: {os.path.join(output_dir, 'tangchen_daily_creator_detailed.csv')}")

# 生成文字日报
print(f"\n=== 汤臣倍健-MD 聚光投放日报 ===")
print(f"数据周期: {df['时间'].min().strftime('%Y-%m-%d')} 至 {df['时间'].max().strftime('%Y-%m-%d')}")
print()
print("👉常规种草维度：")
latest_date = daily_data[-1]
print(f"消耗{latest_date['消费']:.0f}、展现{latest_date['展现量']:,.0f}、点击{latest_date['点击量']:,.0f}、CTR{latest_date['点击率']:.1%}、CPC{latest_date['平均点击成本']:.2f}、CPM{latest_date['平均千次展现费用']:.2f}、CPE{latest_date['互动量']/latest_date['消费'] if latest_date['消费'] > 0 else 0:.2f}")
print()
print("数据表现情况&今日动作：")
print("1、投放数据分析")
print("2、优化调整动作")