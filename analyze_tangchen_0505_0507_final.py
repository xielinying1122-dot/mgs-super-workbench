import pandas as pd
import os

# 读取清洗后的数据
df = pd.read_csv(os.path.expanduser('~/juguang-automation/data/processed/clean_creative_标准投基础报表_全部营销诉求_创意_2026-05-01-2026-05-07.csv'))

# 筛选5月5日-5月7日
df['date'] = pd.to_datetime(df['date'])
df = df[(df['date'] >= '2026-05-05') & (df['date'] <= '2026-05-07')]

# 提取达人、广告类型、投放模式、人群定向
def extract(creative, pos):
    if pd.isna(creative): return None
    parts = str(creative).split('-')
    return parts[pos] if len(parts) > pos else None

df['达人'] = df['creative'].apply(lambda x: extract(x, 4))
df['广告类型'] = df['creative'].apply(lambda x: extract(x, 2))
df['投放模式'] = df['creative'].apply(lambda x: extract(x, 3))
df['人群定向'] = df['unit'].apply(lambda x: str(x).split('-')[-1] if pd.notna(x) else None)

print("=" * 60)
print("汤臣倍健-MD 聚光投放日报 2026-05-05 至 2026-05-07")
print("=" * 60)

# ========== 1. 按天汇总 ==========
print("\n【一、按天数据】")
print("-" * 60)
daily = df.groupby('date').agg(
    cost=('cost','sum'), impressions=('impressions','sum'),
    clicks=('clicks','sum'), ctr=('ctr','mean'),
    cpc=('cpc','mean'), cpm=('cpm','mean'),
    interactions=('interactions','sum')
).reset_index()

for _, r in daily.iterrows():
    cpe = r['cost']/r['interactions'] if r['interactions']>0 else 0
    print(f"\n{r['date'].strftime('%Y-%m-%d')}:")
    print(f"  消耗¥{r['cost']:.0f}、展现{r['impressions']:,.0f}、点击{r['clicks']:,.0f}")
    print(f"  CTR{r['ctr']:.1%}、CPC¥{r['cpc']:.2f}、CPM¥{r['cpm']:.0f}、CPE¥{cpe:.2f}")

# 环比
if len(daily) >= 2:
    prev, curr = daily.iloc[-2], daily.iloc[-1]
    print(f"\n环比（{prev['date'].strftime('%m.%d')}→{curr['date'].strftime('%m.%d')}）:")
    print(f"  消耗: {curr['cost']/prev['cost']-1:+.1%}")
    print(f"  CTR: {curr['ctr']/prev['ctr']-1:+.1%}")
    print(f"  CPC: {curr['cpc']/prev['cpc']-1:+.1%}")

# ========== 2. 按达人 ==========
print("\n\n【二、按达人数据】")
print("-" * 60)
creator = df.groupby('达人').agg(
    cost=('cost','sum'), impressions=('impressions','sum'),
    clicks=('clicks','sum'), ctr=('ctr','mean'),
    cpc=('cpc','mean'), cpm=('cpm','mean'),
    interactions=('interactions','sum')
).reset_index().sort_values('cost', ascending=False)

for _, r in creator.iterrows():
    pct = r['cost']/df['cost'].sum()*100
    cpe = r['cost']/r['interactions'] if r['interactions']>0 else 0
    print(f"\n{r['达人']}（消耗占比{pct:.1f}%）:")
    print(f"  消耗¥{r['cost']:.0f}、展现{r['impressions']:,.0f}、点击{r['clicks']:,.0f}")
    print(f"  CTR{r['ctr']:.1%}、CPC¥{r['cpc']:.2f}、CPM¥{r['cpm']:.0f}、CPE¥{cpe:.2f}")

# ========== 3. 按广告类型 ==========
print("\n\n【三、按广告类型】")
print("-" * 60)
ad_type = df.groupby('广告类型').agg(
    cost=('cost','sum'), impressions=('impressions','sum'),
    clicks=('clicks','sum'), ctr=('ctr','mean'),
    cpc=('cpc','mean'), cpm=('cpm','mean'),
    interactions=('interactions','sum')
).reset_index().sort_values('cost', ascending=False)

for _, r in ad_type.iterrows():
    pct = r['cost']/df['cost'].sum()*100
    cpe = r['cost']/r['interactions'] if r['interactions']>0 else 0
    print(f"\n{r['广告类型']}（消耗占比{pct:.1f}%）:")
    print(f"  消耗¥{r['cost']:.0f}、展现{r['impressions']:,.0f}、点击{r['clicks']:,.0f}")
    print(f"  CTR{r['ctr']:.1%}、CPC¥{r['cpc']:.2f}、CPM¥{r['cpm']:.0f}、CPE¥{cpe:.2f}")

# ========== 4. 按人群定向 ==========
print("\n\n【四、按人群定向】")
print("-" * 60)
crowd = df.groupby('人群定向').agg(
    cost=('cost','sum'), impressions=('impressions','sum'),
    clicks=('clicks','sum'), ctr=('ctr','mean'),
    cpc=('cpc','mean'), cpm=('cpm','mean'),
    interactions=('interactions','sum')
).reset_index().sort_values('cost', ascending=False)

for _, r in crowd.iterrows():
    if not pd.isna(r['人群定向']):
        pct = r['cost']/df['cost'].sum()*100
        cpe = r['cost']/r['interactions'] if r['interactions']>0 else 0
        print(f"\n{r['人群定向']}（消耗占比{pct:.1f}%）:")
        print(f"  消耗¥{r['cost']:.0f}、展现{r['impressions']:,.0f}、点击{r['clicks']:,.0f}")
        print(f"  CTR{r['ctr']:.1%}、CPC¥{r['cpc']:.2f}、CPM¥{r['cpm']:.0f}、CPE¥{cpe:.2f}")

# ========== 5. 按投放模式 ==========
print("\n\n【五、按投放模式】")
print("-" * 60)
mode = df.groupby('投放模式').agg(
    cost=('cost','sum'), impressions=('impressions','sum'),
    clicks=('clicks','sum'), ctr=('ctr','mean'),
    cpc=('cpc','mean'), cpm=('cpm','mean'),
    interactions=('interactions','sum')
).reset_index().sort_values('cost', ascending=False)

for _, r in mode.iterrows():
    pct = r['cost']/df['cost'].sum()*100
    cpe = r['cost']/r['interactions'] if r['interactions']>0 else 0
    print(f"\n{r['投放模式']}（消耗占比{pct:.1f}%）:")
    print(f"  消耗¥{r['cost']:.0f}、展现{r['impressions']:,.0f}、点击{r['clicks']:,.0f}")
    print(f"  CTR{r['ctr']:.1%}、CPC¥{r['cpc']:.2f}、CPM¥{r['cpm']:.0f}、CPE¥{cpe:.2f}")

# ========== 6. 按达人x天 ==========
print("\n\n【六、按达人x天】")
print("-" * 60)
ct = df.groupby(['date','达人']).agg(
    cost=('cost','sum'), impressions=('impressions','sum'),
    clicks=('clicks','sum'), ctr=('ctr','mean'),
    cpc=('cpc','mean'), interactions=('interactions','sum')
).reset_index()

for _, r in ct.iterrows():
    print(f"  {r['date'].strftime('%m.%d')} {r['达人']}: 消耗¥{r['cost']:.0f}、CTR{r['ctr']:.1%}、CPC¥{r['cpc']:.2f}")

# ========== 7. 总汇总 ==========
print("\n\n【七、5.5-5.7总汇总】")
print("-" * 60)
total_cpe = df['cost'].sum()/df['interactions'].sum() if df['interactions'].sum()>0 else 0
print(f"总消耗: ¥{df['cost'].sum():,.0f}")
print(f"总展现: {df['impressions'].sum():,.0f}")
print(f"总点击: {df['clicks'].sum():,.0f}")
print(f"总互动: {df['interactions'].sum():,.0f}")
print(f"整体CTR: {df['clicks'].sum()/df['impressions'].sum():.1%}")
print(f"整体CPC: ¥{df['cost'].sum()/df['clicks'].sum():.2f}")
print(f"整体CPE: ¥{total_cpe:.2f}")
print(f"整体CPM: ¥{df['cost'].sum()/df['impressions'].sum()*1000:.0f}")

# 保存数据
out = os.path.expanduser('~/juguang-automation/data/processed/')
daily.to_csv(f'{out}tangchen_0505_0507_daily_final.csv', index=False, encoding='utf-8-sig')
creator.to_csv(f'{out}tangchen_0505_0507_creator_final.csv', index=False, encoding='utf-8-sig')
crowd.to_csv(f'{out}tangchen_0505_0507_crowd_final.csv', index=False, encoding='utf-8-sig')
ad_type.to_csv(f'{out}tangchen_0505_0507_adtype_final.csv', index=False, encoding='utf-8-sig')
ct.to_csv(f'{out}tangchen_0505_0507_creator_daily_final.csv', index=False, encoding='utf-8-sig')
df.to_csv(f'{out}tangchen_0505_0507_raw_final.csv', index=False, encoding='utf-8-sig')
print(f"\n数据已保存到 {out}")
