"""核对种草 CPE 的分母：interactions 到底把哪些列加进来了。"""
import sys
from pathlib import Path

ROOT = Path("/Users/ouyangyang/juguang-automation")
sys.path.insert(0, str(ROOT / "mgs_workbench"))
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402
from mgs_workbench_engine import ingest_files  # noqa: E402
from mgs_review_engine import DETAIL_INTERACTIONS  # noqa: E402

DATA = Path("/Users/ouyangyang/Documents/红书工作/MGS投流/数据输入")
paths = sorted(p for p in DATA.glob("*.xlsx") if not p.name.startswith(".~"))
frames = ingest_files(paths).frames
creative = frames["creative"]
sd = creative[creative["account"].astype(str).str.contains("种草", na=False)].copy()
sd["date"] = pd.to_datetime(sd["date"], errors="coerce")
day = sd[sd["date"] == pd.Timestamp("2026-09-09")].copy()
print("种草 9/9 行数:", len(day))
print("DETAIL_INTERACTIONS =", DETAIL_INTERACTIONS)

print("\n--- 各行原始列合计 ---")
for col in ["interactions", *DETAIL_INTERACTIONS]:
    if col in day.columns:
        print(f"  {col:<20} 合计 = {pd.to_numeric(day[col], errors='coerce').fillna(0).sum():>10.1f}")

detail_total = day[list(DETAIL_INTERACTIONS)].apply(pd.to_numeric, errors="coerce").fillna(0).sum(axis=1)
raw = pd.to_numeric(day["interactions"], errors="coerce").fillna(0)
mask = (raw == 0) & (detail_total > 0)
print(f"\n互动量为 0 但明细有值的行: {int(mask.sum())} / {len(day)}")
print(f"这些行的 detail_total 合计 = {detail_total[mask].sum():.1f}")
print(f"最终 interactions = {raw[~mask].sum() + detail_total[mask].sum():.1f}")

print("\n--- 被 fallback 顶替的行，明细构成 ---")
sub = day[mask]
for col in DETAIL_INTERACTIONS:
    v = pd.to_numeric(sub[col], errors="coerce").fillna(0).sum()
    if v:
        print(f"  {col:<20} = {v:>10.1f}")
