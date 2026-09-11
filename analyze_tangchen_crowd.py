import pandas as pd
import os

df = pd.read_csv(os.path.expanduser('~/juguang-automation/data/processed/tangchen_0505_0507_raw_final.csv'))
df['date'] = pd.to_datetime(df['date'])

# 提取人群定向
def safe_extract(s, pos):
    if pd.isna(s): return None
    parts = str(s).split('-')
    return parts[pos] if len(parts) > pos else None

df['crowd'] = df['unit'].apply(lambda x: str(x).split('-')[-1] if pd.notna(x) else None)
df['ad_type'] = df['creative'].apply(lambda x: safe_extract(x, 2))
df['mode'] = df['creative'].apply(lambda x: safe_extract(x, 3))

total_cost = df['cost'].sum()

# 过滤掉非人群的小编号
valid_crowds = ['智能人群','母亲节人群','品牌人群','健身减脂人群','蛋白粉意向人群',
                '高消耗中年','白富美养生人群','爆肝青年人群','爆肝青年',
                '保健品关键词行为','蛋白粉关键词行为']
df_valid = df[df['crowd'].isin(valid_crowds)].copy()

print("=" * 70)
print("汤臣倍健-MD 人群定向深度拆解 5.5-5.7")
print("=" * 70)

# ========== 1. 人群总览 ==========
print("\n【一、人群总览（按消耗排序）】")
print("-" * 70)
crowd_total = df_valid.groupby('crowd').agg(
    cost=('cost','sum'), impressions=('impressions','sum'),
    clicks=('clicks','sum'), interactions=('interactions','sum'),
    likes=('likes','sum'), saves=('saves','sum'), comments=('comments','sum'),
    follows=('follows','sum'), shares=('shares','sum')
).reset_index().sort_values('cost', ascending=False)

for _, r in crowd_total.iterrows():
    pct = r['cost']/total_cost*100
    ctr = r['clicks']/r['impressions']*100 if r['impressions']>0 else 0
    cpc = r['cost']/r['clicks'] if r['clicks']>0 else 0
    cpm = r['cost']/r['impressions']*1000 if r['impressions']>0 else 0
    cpe = r['cost']/r['interactions'] if r['interactions']>0 else 0
    print(f"\n📊 {r['crowd']}（消耗占比{pct:.0f}%）")
    print(f"   消耗¥{r['cost']:,.0f} | 展现{r['impressions']:,.0f} | 点击{r['clicks']:,.0f}")
    print(f"   CTR{ctr:.1f}% | CPC¥{cpc:.2f} | CPM¥{cpm:.0f} | CPE¥{cpe:.2f}")
    print(f"   互动{r['interactions']:.0f}（赞{r['likes']:.0f}、藏{r['saves']:.0f}、评{r['comments']:.0f}、关{r['follows']:.0f}、享{r['shares']:.0f}）")

# ========== 2. 人群×天 ==========
print("\n\n【二、人群×天趋势】")
print("-" * 70)
for crowd_name in crowd_total['crowd'].head(6):
    cdf = df_valid[df_valid['crowd'] == crowd_name]
    print(f"\n📊 {crowd_name}:")
    for date in sorted(cdf['date'].unique()):
        ddf = cdf[cdf['date'] == date]
        cost = ddf['cost'].sum()
        imp = ddf['impressions'].sum()
        clk = ddf['clicks'].sum()
        ctr = clk/imp*100 if imp>0 else 0
        cpc = cost/clk if clk>0 else 0
        cpe = cost/ddf['interactions'].sum() if ddf['interactions'].sum()>0 else 0
        print(f"   {pd.Timestamp(date).strftime('%m.%d')}: 消耗¥{cost:,.0f} | CTR{ctr:.1f}% | CPC¥{cpc:.2f} | CPE¥{cpe:.2f}")

# ========== 3. 人群×广告类型 ==========
print("\n\n【三、人群×广告类型】")
print("-" * 70)
for crowd_name in crowd_total['crowd'].head(6):
    cdf = df_valid[df_valid['crowd'] == crowd_name]
    print(f"\n📊 {crowd_name}:")
    for ad in cdf.groupby('ad_type').agg(cost=('cost','sum')).sort_values('cost',ascending=False).index:
        adf = cdf[cdf['ad_type'] == ad]
        cost = adf['cost'].sum()
        imp = adf['impressions'].sum()
        clk = adf['clicks'].sum()
        ctr = clk/imp*100 if imp>0 else 0
        cpc = cost/clk if clk>0 else 0
        cpe = cost/adf['interactions'].sum() if adf['interactions'].sum()>0 else 0
        pct = cost/cdf['cost'].sum()*100
        print(f"   {ad}({pct:.0f}%): 消耗¥{cost:,.0f} | CTR{ctr:.1f}% | CPC¥{cpc:.2f} | CPE¥{cpe:.2f}")

# ========== 4. 人群×投放模式 ==========
print("\n\n【四、人群×投放模式】")
print("-" * 70)
for crowd_name in crowd_total['crowd'].head(6):
    cdf = df_valid[df_valid['crowd'] == crowd_name]
    print(f"\n📊 {crowd_name}:")
    for mode in cdf.groupby('mode').agg(cost=('cost','sum')).sort_values('cost',ascending=False).index:
        mdf = cdf[cdf['mode'] == mode]
        cost = mdf['cost'].sum()
        imp = mdf['impressions'].sum()
        clk = mdf['clicks'].sum()
        ctr = clk/imp*100 if imp>0 else 0
        cpc = cost/clk if clk>0 else 0
        cpe = cost/mdf['interactions'].sum() if mdf['interactions'].sum()>0 else 0
        pct = cost/cdf['cost'].sum()*100
        print(f"   {mode}({pct:.0f}%): 消耗¥{cost:,.0f} | CTR{ctr:.1f}% | CPC¥{cpc:.2f} | CPE¥{cpe:.2f}")

# ========== 5. 人群分层评估 ==========
print("\n\n【五、人群分层评估】")
print("-" * 70)

print("\n🟢 高效人群（CTR高 + CPC低）— 建议加大预算：")
for _, r in crowd_total.iterrows():
    ctr = r['clicks']/r['impressions']*100 if r['impressions']>0 else 0
    cpc = r['cost']/r['clicks'] if r['clicks']>0 else 0
    if ctr > 10 and cpc < 1.8:
        cpe = r['cost']/r['interactions'] if r['interactions']>0 else 0
        print(f"   ✅ {r['crowd']}: CTR{ctr:.1f}%、CPC¥{cpc:.2f}、消耗¥{r['cost']:,.0f}")

print("\n🟡 潜力人群（CTR高但消耗低）— 建议测试放量：")
for _, r in crowd_total.iterrows():
    ctr = r['clicks']/r['impressions']*100 if r['impressions']>0 else 0
    if ctr > 10 and r['cost'] < 1000:
        print(f"   🔶 {r['crowd']}: CTR{ctr:.1f}%、消耗¥{r['cost']:,.0f}")

print("\n🔴 低效人群（CTR低 + CPC高）— 建议优化或收缩：")
for _, r in crowd_total.iterrows():
    ctr = r['clicks']/r['impressions']*100 if r['impressions']>0 else 0
    cpc = r['cost']/r['clicks'] if r['clicks']>0 else 0
    if ctr < 8 and r['cost'] > 500:
        cpe = r['cost']/r['interactions'] if r['interactions']>0 else 0
        print(f"   ⚠️ {r['crowd']}: CTR{ctr:.1f}%、CPC¥{cpc:.2f}、消耗¥{r['cost']:,.0f}")

# 保存
out = os.path.expanduser('~/juguang-automation/data/processed/')
crowd_total.to_csv(f'{out}tangchen_0505_0507_人群深度拆解.csv', index=False, encoding='utf-8-sig')
print(f"\n\n人群拆解数据已保存: {out}tangchen_0505_0507_人群深度拆解.csv")
