import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";

import { buildWorkbook } from "../build_margys_workbook.mjs";


const payload = {
  project: "MARGY'S骨胶原面膜",
  kpi: { monthly_cpuv: 35, monthly_roi: 2.5 },
  sources: {
    note: {
      path: "/tmp/note.csv",
      rows: 2,
      entities: 1,
      date_start: "2026-08-18",
      date_end: "2026-08-31",
      spend: 400,
      visits: 15,
      gmv: 300,
      cpuv: 400 / 15,
      roi: 0.75,
      roi_note: "GMV/消费重算",
    },
  },
  analyses: {
    note: [
      {
        entity_id: "note-1",
        entity_name: "note-1",
        spend: 400,
        visits: 15,
        gmv: 300,
        start_date: "2026-08-18",
        end_date: "2026-08-31",
        active_days: 14,
        cpuv: 400 / 15,
        roi: 0.75,
        decision: "样本不足",
        reason_code: "未到测试门槛",
      },
    ],
  },
};

const outputDir = await fs.mkdtemp(path.join(os.tmpdir(), "margys-workbook-test-"));
const outputPath = path.join(outputDir, "result.xlsx");
await buildWorkbook(payload, outputPath, outputDir);

const stat = await fs.stat(outputPath);
assert.ok(stat.size > 1000, "workbook should be non-empty");
console.log("workbook created", outputPath, stat.size);
