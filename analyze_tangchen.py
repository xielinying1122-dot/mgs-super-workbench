import pandas as pd
import os

# 读取汤臣倍健数据文件
file_path = os.path.expanduser('~/Documents/红书工作/汤臣蛋白粉-5.4-5.10/汤臣蛋白粉日报数据-5.7.xlsx')

# 读取数据底表
df = pd.read_excel(file_path, sheet_name='数据底表')
print(f'数据底表形状: {df.shape}')
print(f'列名: {list(df.columns)}')

# 查看日期范围
print(f'日期范围: {df["时间"].min()} 至 {df["时间"].max()}')

# 查看创意名称格式
print(f'创意名称示例:')
for i, name in enumerate(df['创意名称'].head(5)):
    print(f'  {i+1}. {name}')

# 查看是否有达人信息
if '达人' in df.columns:
    print(f'达人列存在，达人数量: {df["达人"].nunique()}')
    print(f'达人列表: {df["达人"].unique()[:10]}')
else:
    print('达人列不存在，需要从创意名称中提取达人信息')
    
    # 从创意名称中提取达人信息
    # 创意名称格式: "0505-汤臣蛋白粉-信息流-点互-李_玲慧_-品牌人群"
    def extract_creator(creative_name):
        if pd.isna(creative_name):
            return None
        parts = str(creative_name).split('-')
        if len(parts) >= 5:
            return parts[4]  # 达人信息在第5个位置
        return None
    
    df['达人'] = df['创意名称'].apply(extract_creator)
    print(f'提取的达人数量: {df["达人"].nunique()}')
    print(f'达人列表: {df["达人"].unique()[:10]}')

# 数据汇总
print(f'\n=== 数据汇总 ===')
print(f'总消费: {df["消费"].sum():.2f}元')
print(f'总展现: {df["展现量"].sum():,.0f}')
print(f'总点击: {df["点击量"].sum():,.0f}')
print(f'平均CTR: {df["点击率"].mean():.3f}')
print(f'平均CPC: {df["平均点击成本"].mean():.2f}元')

# 按天汇总
print(f'\n=== 按天汇总 ===')
daily_summary = df.groupby('时间').agg({
    '消费': 'sum',
    '展现量': 'sum',
    '点击量': 'sum',
    '点击率': 'mean',
    '平均点击成本': 'mean',
    '平均千次展现费用': 'mean',
    '互动量': 'sum'
}).reset_index()

for idx, row in daily_summary.iterrows():
    print(f"{row['时间']}: 消费{row['消费']:.2f}元, 展现{row['展现量']:,.0f}, 点击{row['点击量']:,.0f}, CTR{row['点击率']:.3f}, CPC{row['平均点击成本']:.2f}元")

# 按达人汇总
print(f'\n=== 按达人汇总 ===')
creator_summary = df.groupby('达人').agg({
    '消费': 'sum',
    '展现量': 'sum',
    '点击量': 'sum',
    '点击率': 'mean',
    '平均点击成本': 'mean',
    '平均千次展现费用': 'mean',
    '互动量': 'sum'
}).reset_index()

# 按消费排序
creator_summary = creator_summary.sort_values('消费', ascending=False)
print(f'达人数量: {len(creator_summary)}')
print('TOP10达人:')
for idx, row in creator_summary.head(10).iterrows():
    print(f"  {row['达人']}: 消费{row['消费']:.2f}元, CTR{row['点击率']:.3f}, CPC{row['平均点击成本']:.2f}元")

# 按天+达人汇总
print(f'\n=== 按天+达人汇总 ===')
daily_creator_summary = df.groupby(['时间', '达人']).agg({
    '消费': 'sum',
    '展现量': 'sum',
    '点击量': 'sum',
    '点击率': 'mean',
    '平均点击成本': 'mean',
    '平均千次展现费用': 'mean',
    '互动量': 'sum'
}).reset_index()

# 保存结果
output_dir = os.path.expanduser('~/juguang-automation/data/processed/')
os.makedirs(output_dir, exist_ok=True)

# 保存按天汇总
daily_summary.to_csv(os.path.join(output_dir, 'tangchen_daily_summary.csv'), index=False, encoding='utf-8-sig')
print(f'\n按天汇总已保存: {os.path.join(output_dir, "tangchen_daily_summary.csv")}')

# 保存按达人汇总
creator_summary.to_csv(os.path.join(output_dir, 'tangchen_creator_summary.csv'), index=False, encoding='utf-8-sig')
print(f'按达人汇总已保存: {os.path.join(output_dir, "tangchen_creator_summary.csv")}')

# 保存按天+达人汇总
daily_creator_summary.to_csv(os.path.join(output_dir, 'tangchen_daily_creator_summary.csv'), index=False, encoding='utf-8-sig')
print(f'按天+达人汇总已保存: {os.path.join(output_dir, "tangchen_daily_creator_summary.csv")}')

print(f'\n数据处理完成！')