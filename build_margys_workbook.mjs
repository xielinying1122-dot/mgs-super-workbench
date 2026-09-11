#!/usr/bin/env node

import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";


const SOURCE_LABELS = {
  creative: "创意分析",
  note: "笔记四象限",
  audience: "人群分析",
  keyword: "关键词分析",
};

const STATUS_COLORS = {
  加量: { fill: "#DCFCE7", font: "#166534" },
  观察: { fill: "#FEF3C7", font: "#92400E" },
  暂停: { fill: "#FEE2E2", font: "#991B1B" },
  样本不足: { fill: "#E5E7EB", font: "#374151" },
};

const COLORS = {
  ink: "#17202A",
  green: "#0F766E",
  greenDark: "#115E59",
  coral: "#E76F51",
  line: "#D6DEE3",
  soft: "#F4F7F8",
  white: "#FFFFFF",
  yellow: "#FFF7D6",
};


function applyBase(sheet, usedRange = "A1:Z40") {
  sheet.showGridLines = false;
  sheet.getRange(usedRange).format.font = { name: "Arial", size: 10, color: COLORS.ink };
}

function applyTitle(sheet, range, title, subtitle = "") {
  const titleRange = sheet.getRange(range);
  titleRange.merge();
  titleRange.values = [[title]];
  titleRange.format = {
    fill: COLORS.greenDark,
    font: { bold: true, color: COLORS.white, size: 16 },
    verticalAlignment: "center",
  };
  titleRange.format.rowHeight = 32;
  if (subtitle) {
    const endColumn = range.split(":")[1].replace(/\d+/g, "");
    const subtitleRange = sheet.getRange(`A2:${endColumn}2`);
    subtitleRange.merge();
    subtitleRange.values = [[subtitle]];
    subtitleRange.format = {
      fill: "#EAF3F2",
      font: { color: "#335B59", size: 9 },
      wrapText: true,
      verticalAlignment: "center",
    };
    subtitleRange.format.rowHeight = 28;
  }
}

function headerStyle(range) {
  range.format = {
    fill: COLORS.green,
    font: { bold: true, color: COLORS.white },
    verticalAlignment: "center",
    horizontalAlignment: "center",
    wrapText: true,
    borders: { preset: "inside", style: "thin", color: "#B9C9CC" },
  };
  range.format.rowHeight = 30;
}

function addStatusFormatting(range) {
  for (const [status, colors] of Object.entries(STATUS_COLORS)) {
    range.conditionalFormats.add("containsText", {
      text: status,
      format: { fill: colors.fill, font: { bold: true, color: colors.font } },
    });
  }
}

function asNumber(value) {
  return value === null || value === undefined || Number.isNaN(Number(value)) ? null : Number(value);
}

function createOverview(workbook, payload) {
  const sheet = workbook.worksheets.add("总览");
  applyBase(sheet, "A1:J24");
  applyTitle(
    sheet,
    "A1:J1",
    "MARGY'S 骨胶原面膜 · 投放决策底稿",
    "候选动作由规则自动生成，账户操作必须由投手人工确认。不同报表时间范围可能不同，不得跨表相加消费。",
  );

  sheet.getRange("A4:J4").values = [["数据源", "时间范围", "明细行", "对象数", "消费", "进店量", "进店CPUV", "GMV", "ROI", "口径备注"]];
  headerStyle(sheet.getRange("A4:J4"));
  const sourceOrder = ["creative", "note", "audience", "keyword"].filter((key) => payload.sources[key]);
  const rows = sourceOrder.map((key) => {
    const source = payload.sources[key];
    return [
      SOURCE_LABELS[key],
      `${source.date_start} 至 ${source.date_end}`,
      source.rows,
      source.entities,
      asNumber(source.spend),
      asNumber(source.visits),
      asNumber(source.cpuv),
      asNumber(source.gmv),
      asNumber(source.roi),
      source.roi_note,
    ];
  });
  if (rows.length) sheet.getRangeByIndexes(4, 0, rows.length, 10).values = rows;
  const last = 4 + rows.length;
  sheet.getRange(`C5:I${last}`).format.horizontalAlignment = "right";
  sheet.getRange(`C5:D${last}`).format.numberFormat = "0";
  sheet.getRange(`E5:E${last}`).format.numberFormat = "0.00";
  sheet.getRange(`F5:F${last}`).format.numberFormat = "0";
  sheet.getRange(`G5:I${last}`).format.numberFormat = "0.00";
  sheet.getRange(`A5:J${last}`).format.borders = { preset: "inside", style: "thin", color: COLORS.line };

  const noteSource = payload.sources.note || payload.sources.creative;
  const status = noteSource && noteSource.cpuv < payload.kpi.monthly_cpuv && noteSource.roi > payload.kpi.monthly_roi ? "达标" : "未同时达标";
  const summaryRow = last + 3;
  sheet.getRange(`A${summaryRow}:J${summaryRow}`).merge();
  sheet.getRange(`A${summaryRow}`).values = [["当前判断"]];
  sheet.getRange(`A${summaryRow}:J${summaryRow}`).format = { fill: COLORS.coral, font: { bold: true, color: COLORS.white, size: 12 } };
  sheet.getRange(`A${summaryRow + 1}:J${summaryRow + 1}`).merge();
  sheet.getRange(`A${summaryRow + 1}`).values = [[
    `以${payload.sources.note ? "笔记表" : "创意表"}本期口径看，月目标CPU V<${payload.kpi.monthly_cpuv}、ROI>${payload.kpi.monthly_roi}：${status}。请先确认导出日期与30日归因窗口，再执行候选动作。`,
  ]];
  sheet.getRange(`A${summaryRow + 1}:J${summaryRow + 1}`).format = { fill: "#FFF1ED", wrapText: true, font: { color: "#7C2D12" } };
  sheet.getRange(`A${summaryRow + 1}:J${summaryRow + 1}`).format.rowHeight = 42;

  const rulesRow = summaryRow + 4;
  sheet.getRange(`A${rulesRow}:J${rulesRow}`).merge();
  sheet.getRange(`A${rulesRow}`).values = [["固定规则"]];
  sheet.getRange(`A${rulesRow}:J${rulesRow}`).format = { fill: COLORS.green, font: { bold: true, color: COLORS.white } };
  const rules = [
    ["测试", "14天内无差别测试，单条消费<800元时不因低效直接误杀"],
    ["转化放量", "ROI>2且进店CPUV<50；或ROI>4时暂不看CPUV"],
    ["进店放量", "进店>20、CPUV<20、ROI>1"],
    ["衰退淘汰", "历史稳定笔记需用近7天切片判断：ROI<1.5且CPUV>30"],
  ];
  sheet.getRangeByIndexes(rulesRow, 0, rules.length, 2).values = rules;
  sheet.getRange(`A${rulesRow + 1}:B${rulesRow + rules.length}`).format = { wrapText: true, borders: { preset: "inside", style: "thin", color: COLORS.line } };

  sheet.getRange("A:J").format.columnWidth = 14;
  sheet.getRange("A:A").format.columnWidth = 14;
  sheet.getRange("B:B").format.columnWidth = 23;
  sheet.getRange("J:J").format.columnWidth = 26;
  sheet.freezePanes.freezeRows(4);
  return sheet;
}

function createAnalysisSheet(workbook, payload, kind) {
  const sheetName = SOURCE_LABELS[kind];
  const sheet = workbook.worksheets.add(sheetName);
  const source = payload.sources[kind];
  const data = payload.analyses[kind] || [];
  const last = Math.max(5, 4 + data.length);
  applyBase(sheet, `A1:N${last}`);
  applyTitle(
    sheet,
    "A1:N1",
    `${sheetName} · 候选动作`,
    `来源：${source.path}；时间：${source.date_start} 至 ${source.date_end}；CPUV=汇总消费/汇总进店量，ROI=汇总GMV/汇总消费。`,
  );
  const headers = ["ID", "名称", "开始日期", "结束日期", "活跃天数", "消费", "进店量", "进店CPUV", "GMV", "ROI", "候选动作", "规则原因", "人工确认", "投手备注"];
  sheet.getRange("A4:N4").values = [headers];
  headerStyle(sheet.getRange("A4:N4"));

  const rows = data.map((row) => [
    row.entity_id,
    row.entity_name,
    row.start_date,
    row.end_date,
    row.active_days,
    asNumber(row.spend),
    asNumber(row.visits),
    asNumber(row.cpuv),
    asNumber(row.gmv),
    asNumber(row.roi),
    row.decision,
    row.reason_code,
    "待确认",
    "",
  ]);
  if (rows.length) sheet.getRangeByIndexes(4, 0, rows.length, headers.length).values = rows;
  sheet.getRange(`A5:N${last}`).format.borders = { preset: "inside", style: "thin", color: COLORS.line };
  sheet.getRange(`C5:D${last}`).format.numberFormat = "yyyy-mm-dd";
  sheet.getRange(`E5:E${last}`).format.numberFormat = "0";
  sheet.getRange(`F5:F${last}`).format.numberFormat = "0.00";
  sheet.getRange(`G5:G${last}`).format.numberFormat = "0";
  sheet.getRange(`H5:J${last}`).format.numberFormat = "0.00";
  sheet.getRange(`K5:K${last}`).format.horizontalAlignment = "center";
  sheet.getRange(`M5:N${last}`).format.fill = COLORS.yellow;
  sheet.getRange(`M5:M${last}`).dataValidation = { rule: { type: "list", values: ["待确认", "同意", "改为观察", "改为暂停", "改为加量"] } };
  addStatusFormatting(sheet.getRange(`K5:K${last}`));
  const table = sheet.tables.add(`A4:N${last}`, true, `${kind.charAt(0).toUpperCase()}${kind.slice(1)}DecisionTable`);
  table.style = "TableStyleMedium2";
  table.showBandedRows = true;
  sheet.freezePanes.freezeRows(4);
  sheet.freezePanes.freezeColumns(2);

  const widths = [24, 28, 12, 12, 10, 12, 10, 12, 13, 10, 12, 18, 14, 30];
  widths.forEach((width, index) => { sheet.getRangeByIndexes(0, index, 1, 1).format.columnWidth = width; });
  sheet.getRange(`B5:B${last}`).format.wrapText = true;
  sheet.getRange(`L5:N${last}`).format.wrapText = true;
  return sheet;
}

function createReadme(workbook, payload) {
  const sheet = workbook.worksheets.add("使用说明");
  applyBase(sheet, "A1:H12");
  applyTitle(sheet, "A1:H1", "半自动流程 · 每日使用说明", "这份工作簿不连接也不修改聚光账户。");
  const steps = [
    ["1", "人工确认账户", "在合作伙伴平台进入 XG-MARGYS MONTE-CARLO，核对 seller_id 与项目。"],
    ["2", "人工导出", "分别导出创意/笔记、人群包、关键词；保持同一日期与归因窗口。"],
    ["3", "自动校验", "字段、合计行、日期、明细总额任一不一致就停止。"],
    ["4", "自动分析", "先汇总消费、进店、GMV，再重算 CPUV 与 ROI，生成候选动作。"],
    ["5", "投手复核", "在“人工确认”和“投手备注”列记录最终决定、原因和观察期。"],
    ["6", "人工执行", "回聚光操作加量、暂停、预算和出价；自动化不执行账户写操作。"],
  ];
  sheet.getRange("A4:C4").values = [["步骤", "环节", "执行标准"]];
  headerStyle(sheet.getRange("A4:C4"));
  sheet.getRangeByIndexes(4, 0, steps.length, 3).values = steps;
  sheet.getRange("A5:C10").format = { wrapText: true, borders: { preset: "inside", style: "thin", color: COLORS.line } };
  sheet.getRange("A:A").format.columnWidth = 8;
  sheet.getRange("B:B").format.columnWidth = 18;
  sheet.getRange("C:C").format.columnWidth = 65;
  sheet.freezePanes.freezeRows(4);
  return sheet;
}

export async function buildWorkbook(payload, outputPath, previewDir = null) {
  const workbook = Workbook.create();
  createOverview(workbook, payload);
  for (const kind of ["note", "audience", "keyword", "creative"]) {
    if (payload.sources[kind]) createAnalysisSheet(workbook, payload, kind);
  }
  createReadme(workbook, payload);
  await fs.mkdir(path.dirname(outputPath), { recursive: true });

  if (previewDir) {
    await fs.mkdir(previewDir, { recursive: true });
    for (const sheetName of ["总览", "笔记四象限", "人群分析", "关键词分析", "创意分析", "使用说明"].filter((name) => {
      try { workbook.worksheets.getItem(name); return true; } catch { return false; }
    })) {
      const preview = await workbook.render({ sheetName, autoCrop: "all", scale: 1, format: "png" });
      await fs.writeFile(path.join(previewDir, `${sheetName}.png`), new Uint8Array(await preview.arrayBuffer()));
    }
  }

  const output = await SpreadsheetFile.exportXlsx(workbook);
  await output.save(outputPath);
  return workbook;
}

export async function verifyWorkbook(workbook) {
  const summary = await workbook.inspect({
    kind: "table",
    range: "总览!A1:J24",
    include: "values,formulas",
    tableMaxRows: 24,
    tableMaxCols: 10,
    maxChars: 10000,
  });
  const formulaErrors = await workbook.inspect({
    kind: "match",
    searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
    options: { useRegex: true, maxResults: 300 },
    summary: "final formula error scan",
    maxChars: 5000,
  });
  return { summary: summary.ndjson, formulaErrors: formulaErrors.ndjson };
}

async function main() {
  const [jsonPath, outputPath, previewDir] = process.argv.slice(2);
  if (!jsonPath || !outputPath) {
    console.error("Usage: node build_margys_workbook.mjs <analysis.json> <output.xlsx> [preview-dir]");
    process.exit(2);
  }
  const payload = JSON.parse(await fs.readFile(jsonPath, "utf8"));
  const workbook = await buildWorkbook(payload, outputPath, previewDir || null);
  const verification = await verifyWorkbook(workbook);
  console.log(verification.summary);
  console.log(verification.formulaErrors);
  console.log(outputPath);
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  await main();
}
