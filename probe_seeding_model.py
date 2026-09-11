"""用真实 MGS 数据跑一遍种草考核模型，检查输出是否如实。"""
import json
import sys
from pathlib import Path

ROOT = Path("/Users/ouyangyang/juguang-automation")
sys.path.insert(0, str(ROOT / "mgs_workbench"))
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402
from mgs_workbench_engine import ingest_files  # noqa: E402
from mgs_review_engine import build_review_payload  # noqa: E402

DATA = Path("/Users/ouyangyang/Documents/红书工作/MGS投流/数据输入")
paths = sorted(p for p in DATA.glob("*.xlsx") if not p.name.startswith(".~"))
print("读入文件:", [p.name for p in paths])
result = ingest_files(paths)
frames = result.frames
print("frames:", {k: v.shape for k, v in frames.items()})
print("issues:", result.issues[:3])

projects = json.loads((ROOT / "config" / "projects.json").read_text(encoding="utf-8"))
project = projects["projects"][0]
payload = build_review_payload(frames, project, start=None, end=None,
                               partition_frames=frames, today=pd.Timestamp("2026-09-11").date())

print("\n=== scope_isolation ===")
print(json.dumps(payload.get("scope_isolation", {}), ensure_ascii=False)[:400])

for part in payload.get("line_partitions", []):
    print("\n" + "=" * 70)
    print(f"投放线: {part['name']}  类型={part['type']}  窗口={part['start']}~{part['end']}")
    print("  metrics:", json.dumps({k: v for k, v in (part.get("metrics") or {}).items()}, ensure_ascii=False))
    if part["type"] == "seeding":
        a = part.get("assessment") or {}
        print("  模型:", a.get("model_label"), "| 基线来源:", a.get("baseline_source"))
        print("  --- 内容效率 ---")
        for item in a.get("efficiency", []):
            print(f"    {item['label']:>4} 当期={item['value']} 基线={item['baseline']} "
                  f"alpha={item['alpha']} 判档={item['status']} 说明={item['note']}")
        o = a.get("offsite") or {}
        print("  --- 站外归因 --- 成熟度:", o.get("maturity"))
        print("    ", o.get("note"))
        for item in o.get("items", []):
            print(f"     {item['label']} = {item['value']}")
        s = a.get("structure") or {}
        print("  --- 结构对比 ---  线内整体:", json.dumps(s.get("overall"), ensure_ascii=False),
              "| 门槛:", json.dumps(s.get("rules"), ensure_ascii=False))
        for block in s.get("blocks", []):
            print(f"    [{block['label']}] 单元 {block['count']} 个 / 达标 {block['eligible_count']} 个")
            for row in block.get("top", [])[:5]:
                print(f"       {row['name'][:22]:<24} 消耗{row['spend']:>9.2f} CTR={row['ctr']} "
                      f"CPC={row['cpc']} CPE={row['cpe']}")
        print("  --- 内容层建议 ---")
        for act in a.get("actions", []):
            print(f"    [{act['layer']}] {act['action']} → {act['object']}")
            print(f"       依据：{act['reason']}")
        print("  结论:", a.get("conclusion"))
    else:
        f = part.get("funnel") or {}
        print("  漏斗基线来源:", f.get("baseline_source"), "| 瓶颈:", f.get("bottleneck_label"))
        print("  结论:", f.get("conclusion"))
