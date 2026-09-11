# 聚光自动化 · 当前可用链路

> 最后更新：2026-09-08  | 状态：**MGS 投放分析与 9.7 投流复盘已跑通；账户自动取数仍需 CDP 授权**

## TL;DR

| 链路 | 状态 | 怎么跑 |
|------|------|--------|
| **Excel → 日报**（手动下表 + 自动出报告） | ✅ **跑通** | `python3 juguang_daily.py --latest --save` |
| **MGS 9.7 投流复盘**（总盘 → 点位/定向/关键词/达人/笔记） | ✅ **跑通** | 工作台 `投流复盘` → `导出复盘 Excel` |
| Python 直调 API | ❌ **架构走不通** | 406 风控拦截，需 CSRF 签名头 |
| Chrome 扩展 v1.7 | ⚠️ 调试态 | content.js 有 const 引用 bug，未完成 |
| CDP 自动化（推荐升级方向） | 🟡 待启用 | 需手动加 `--remote-debugging-port` 启 Chrome |
| AppleScript 抓 DOM | 🟡 备选 | 需开启 Chrome → 开发 → 允许 Apple 事件中的 JavaScript |

## MGS 投放分析工作台（当前主入口）

本地地址：`http://127.0.0.1:8765/`

一键启动：

```bash
./run_mgs_workbench.sh
```

工作台是个人本地使用，不开放团队账号、权限管理或云端协作。当前项目在
`config/projects.json` 注册；该文件只保存本机目录和项目口径，不提交到公共仓库。首次从代码仓库
启动时，先复制 `config/projects.example.json` 为 `config/projects.json`，再填写本机目录。新增项目时：

1. 为项目准备独立的 `root_dir` 和 `input_dir`，不要把新客户文件放进 MGS 的数据目录。
2. 复制 `projects.example.json` 中的项目配置，填写唯一的英文 `project_id`、项目名称、主报表前缀和 KPI/归因口径。
3. 首次放入报表后，先看数据质量和日期范围，再确认项目的 ROI、CPUV 字段是否匹配；不完整数据不补造。
4. 页面左侧项目下拉切换项目；切换后输入目录、动作日志、分析阈值和导出文件名都会跟随项目。
5. `modules` 控制每个项目的页面模块。MGS 已开启 `复盘`；新项目先保持复盘、规划、经验库关闭，完成数据质检后再按项目开启。

项目配置最小模板（复制后只改项目自己的值）：

```json
{
  "project_id": "client-product",
  "name": "客户简称",
  "display_name": "客户简称 商品名",
  "root_dir": "~/Documents/红书工作/客户简称",
  "input_dir": "~/Documents/红书工作/客户简称/数据输入",
  "default_source": "~/Documents/红书工作/客户简称",
  "primary_workbook_prefix": "客户简称投放表-",
  "kpi": {
    "roi_target": 1.2,
    "cpuv_target": 40
  },
  "action_rules": {},
  "metric_contract": {
    "primary_total_source": "creative",
    "roi": "gmv / spend",
    "cpuv": "spend / visits",
    "gmv_field": "项目实际 GMV 字段",
    "visits_field": "项目实际进店字段",
    "currency": "CNY"
  },
  "attribution_windows": {
    "gmv_days": 30,
    "visits_days": 15
  },
  "modules": {
    "投放分析": true,
    "日报": true,
    "规划": false,
    "复盘": false,
    "经验库": false
  },
  "review_rules": {}
}
```

`kpi` 只描述项目目标，`action_rules` 才决定系统能否给出候选动作。新项目的
`action_rules` 为空时，页面只展示数据和“待配置”，不会套用 MGS 的阈值。`review_rules`
为空时，达人只会标记为“观察”，不会继承 MGS 的达人阈值。规划和经验库仍作为模块开关
保留；不同项目必须使用独立目录，不把报表混在一起。

### 切换项目和接入其他报表

工作台左侧的“当前项目”下拉框就是项目切换入口。切换后，输入目录、主报表前缀、指标
口径、动作规则、复盘阈值和导出文件名都会跟随所选项目；页面不会把上一个项目的文件
自动带入当前项目。接入新项目时，在本机的 `config/projects.json` 复制一个项目对象，改完唯一的
`project_id`、目录、主报表前缀和口径，再把对应的 CSV/XLSX 放入该项目的 `input_dir`，或
在页面点击“上传报表”。上传后在“数据与来源”确认报表类型，点击“生成分析”。

切换后建议按这个顺序检查：项目名称 → 数据目录 → 文件类型 → 日期范围 → KPI/归因字段。
如果页面没有显示“投流复盘”，说明该项目的 `modules.复盘` 没有开启；不要为了显示页面
直接复制 MGS 的 `review_rules`，先确认该项目的字段和归因窗口。

每天使用：

1. 从聚光导出创意/日报、定向、人群包或关键词报表。
2. 放入当前项目配置的 `input_dir`，或在页面点击“上传报表”。
3. 打开“数据与来源”，确认报表类型后点击“生成分析”。
4. 先看点位和“今日动作”，再下钻到计划、笔记、定向、关键词；执行后用“记录执行”留痕。
5. 需要交付日报时下载“日报文字”或“Excel 分析包”；MGS 的周/阶段复盘在“投流复盘”页面单独下载“复盘 Excel”。

工作台支持桌面、平板和手机宽度。上传文件会先进入类型确认，不会覆盖原始文件，也不会自动修改聚光账户。

固定判断纪律：

- 总览只用创意/日报表汇总，定向和关键词只做下钻，避免重复加总消费。
- ROI=汇总 GMV/汇总消耗；进店 CPUV=汇总消耗/汇总店铺访问量（15日）。
- 高出价、高点击或低 CPC 不能单独证明高 GMV；放量至少同时核对 ROI、进店 CPUV 和有效进店量。
- 灵犀只提供人群/内容候选，最终要回聚光用同笔记、同预算、同出价验证；工作台只生成候选动作，不自动修改账户。
- 内容质量不能由消耗、互动或 ROI 反推；没有可访问笔记链接、截图或正文时，内容点评保持 `unknown`。

参考：

- [聚光投放产品资料（信息流与智能定向）](https://fe-video-qc.xhscdn.com/fe-platform/5d013a20d7c3ef6f581dcd33f31933284139756e.pdf)
- [聚光搜索投放产品资料](https://fe-video-qc.xhscdn.com/fe-platform/0ef6f3f3c5c691d02d79c338558b271af7a4a43b.pdf)

## MGS 9.7 投流复盘（已跑通）

当前复盘窗口为 **2026-09-01 至 2026-09-07**，数据截至 2026-09-07。真实 9.7 原始字段
按消耗复盘口径汇总为：消耗 `31516.08`、GMV `84130.29`、ROI `2.6694`、进店 `786`、CPUV
`40.0968`；达人点评行 `48`，笔记拆分行 `123`，笔记链接覆盖率 `95.85%`，未匹配
`3` 个笔记 ID。零消耗但带延迟归因的 152 行（GMV `19027.69`、进店 `214`）只进入数据质量提示，
不计入按消耗总盘。复盘使用当前 9.7 文件中的“行业商品 GMV（30日）”和“店铺访问量（15日）”字段。

使用路径：

1. 左侧选择 `MGS / MARGY'S 骨胶原面膜`，把分析窗口设为需要复盘的日期。
2. 点击“生成分析”，再进入“投流复盘”；点位筛选会同步作用于复盘页面。
3. 先看总盘消耗、GMV、ROI、CPUV 和每日趋势，再看点位；定向和关键词是拆解层，
   不回加到总盘。
4. 在“优质达人候选”查看标签和证据，在“笔记与链接状态”打开规范化链接。
5. 点击“导出复盘 Excel”，得到 9 个 Sheet：`复盘首页`、`复盘趋势`、`点位复盘`、
   `定向复盘`、`关键词复盘`、`达人复盘`、`达人点评`、`笔记链接`、`复盘数据质量`。

复盘的判断边界：总盘只读创意/日报明细；定向、关键词仅作层级比较；GMV 使用 30 日归因，
进店使用 15 日归因。达人标签是 `优质·可复用`、`有效·需优化`、`观察`、`不建议复用`，
并同时显示样本是否充足。`observed` 表示原始表或公开笔记直接可见，`derived` 表示由原始
字段计算，`hypothesis` 表示待测试判断，`unknown` 表示证据不足。当前 API 的验证状态为
`local_read_only`、数据成熟度为 `maturing`；这不等同于后端已核验。

达人内容点评需要用户提供可访问的笔记链接、截图或正文。系统会把链接规范化并去掉
`xsec_token` 等临时查询参数；没有内容证据时只评价媒体效率和商业结果，内容质量保持
`unknown`，不会因为互动高就认定内容优质。

---

## 一、立刻能用的路径：juguang_daily.py

### 完整工作流

```bash
# 1. 在聚光后台手动下载「创意-数据报表」xlsx
#    导出后浏览器会自动保存到 ~/Downloads/创意-数据报表下载*.xlsx

# 2. 把它放到 raw 目录（或留在 Downloads 也行，脚本会自动找）
mv ~/Downloads/创意-数据报表下载*.xlsx ~/juguang-automation/data/raw/

# 3. 一键出日报
cd ~/juguang-automation
python3 juguang_daily.py --latest --save

# 输出会同时打印到屏幕 + 保存到 data/reports/日报_<项目>_<日期>.txt
```

### 高级用法

```bash
# 指定文件
python3 juguang_daily.py ~/Downloads/创意-数据报表下载.xlsx

# 指定项目名（默认蔡司眼镜）
python3 juguang_daily.py --latest --project "汤臣倍健-MD"

# 指定日期（默认 Excel 里的最新日期）
python3 juguang_daily.py --latest --date 2026-05-13

# 不保存只输出
python3 juguang_daily.py --latest
```

### 日报包含

1. **整体**：消耗 / CTR / CPC / CPM / CPE + 环比
2. **按广告形式拆**：Feeds / SEM（基于计划名称里的"信息流/搜索"关键词）
3. **按账户类型拆**：达人 / 官号（基于"点互/点点"关键词）
4. **Top 5 消耗计划**
5. **Top 5 高潜创意**（按点击量）
6. **人工补充槽位**：异常原因、今日动作、客户关注点

### 跟旧版的差异

| 维度 | 旧版 `daily_report.py` | 新版 `juguang_daily.py` |
|------|----------------------|------------------------|
| Feeds/SEM 判断 | 依赖"广告类型"列（已不存在） | 用计划名称关键词 |
| 文件 pattern | `创意-投放数据*.xlsx` | 兼容 3 种命名 |
| 互动量列 | 假设一定有 | 兼容缺失 |
| 配置 | 外部 JSON | 命令行参数 |
| 依赖 | pandas + openpyxl + json | pandas + openpyxl |

---

## 二、为什么 Python 直调 API 走不通

```
python3 juguang_client.py
→ ERROR 406 Client Error: Not Acceptable
```

**原因**：聚光后端要求每个 POST 携带 `X-S` / `X-T` / `X-S-Common` 这类签名头（小红书风控通用机制）。
这些头是浏览器侧动态生成的（前端 JS 里有签名算法，已混淆压缩），Python `requests` 无法生成有效签名。

**方法论**：除非你愿意：
- 逆向小红书的 JS 签名算法（耗时高、难度大、易随版本失效）
- 或者用浏览器代为发请求（CDP / Chrome 扩展）

**推荐方案**：CDP（下一节）

---

## 三、CDP 升级路径（推荐）

`cdp_export.py` 已经写好。要让它跑通，**你只需要做一次 Chrome 启动配置**：

### Step 1：关掉所有 Chrome 实例

```bash
osascript -e 'quit app "Google Chrome"'
sleep 2
```

### Step 2：用 debug port 启动 Chrome

```bash
# 启动一个专门的 Chrome 实例（不影响日常 Chrome 资料）
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
    --remote-debugging-port=18800 \
    --user-data-dir="$HOME/.chrome-juguang-profile" \
    https://ad.xiaohongshu.com/aurora/ad/manage/campaigngroup &
```

> 第一次启动会要求你**重新登录聚光**（这个 profile 是独立的）。登录后退出，重新跑上面命令时就是已登录态。

### Step 3：跑 CDP 自动化

```bash
cd ~/juguang-automation
pip3 install websocket-client    # 缺这个依赖（requirements.txt 里没写）
python3 cdp_export.py
```

### Step 4：观察输出

如果看到 `API Results: {"campaign":{"status":200,"count":N,"hasData":true}, ...}` 就跑通了。
如果 status 是 200 但 count=0，说明日期范围里没数据，**API 通了**——把 cdp_export.py 改成实际想要的日期范围。

### 自动化封装思路

跑通 CDP 后，写一个 wrapper：
```
auto_pipeline.sh
├── 调 cdp_export.py 下载 Excel 到 data/raw/
└── 调 juguang_daily.py --latest --save 出日报
```
就是真正的全自动了。

---

## 四、Chrome 扩展 v1.7 现状

`~/hermes-projects/juguang-data-exporter/` 是个**未完成的 MV3 扩展**。

### 当前状态
- popup.html / popup.js：UI 完整，能选日期范围、勾选数据类型
- content.js v1.7：仍是**调试模式**——尝试 snake_case / camelCase 两种 API 字段格式，把结果打印到页面右上角，提示"截图发我"
- **有 bug**：content.js 第 93 行的 `items` 在 if 块外引用，会 ReferenceError

### 不修了的原因
CDP 方案是**更干净**的路线——不用维护扩展、不用每次 Chrome 升级担心兼容、调试更容易。
扩展里能做的，CDP 都能做，而且 CDP 能跑 Python 复杂逻辑。

如果你真要修这个扩展，重点是：
1. 删掉 v1.7 的调试代码
2. 锁定一种正确的 API 字段格式（实测发现 `start_date`/`startDate` 哪个对就用哪个）
3. 加 keyword 类型的导出（目前只导出 campaign/unit/creative 三类）
4. 把"截图发我"那段删了

---

## 五、文件位置速查

| 用途 | 路径 |
|------|------|
| 主用脚本（**就用这个**） | `~/juguang-automation/juguang_daily.py` |
| 输入 Excel 目录 | `~/juguang-automation/data/raw/` |
| 输出日报目录 | `~/juguang-automation/data/reports/` |
| CDP 自动化（待启用） | `~/juguang-automation/cdp_export.py` |
| API 客户端（已停用） | `~/juguang-automation/juguang_client.py` |
| Chrome 扩展（未完成） | `~/hermes-projects/juguang-data-exporter/` |
| 配置（Cookie，已过期） | `~/juguang-automation/config.yaml` |
| 数据/规划文档 | `~/Documents/红书工作/00-谢林颖-小红书投流工作系统/` |

---

## 六、下一步建议（按 ROI 排序）

1. **现在就用**：每天从聚光手动下 Excel，跑 `juguang_daily.py --latest --save`——立刻拥有"自动出日报"
2. **本周做**：按"三、CDP 升级"启用 debug Chrome，跑通 `cdp_export.py`，下 Excel 这步也自动化
3. **下周做**：写 `auto_pipeline.sh` 串起来；加飞书推送
4. **未来**：DMP 人群洞察 / 异常检测 / 多账号管理——已有半成品代码（`dmp_analyzer.py` / `anomaly_detector.py` / `campaign_manager.py`），但都基于 API 直调，要先 CDP 通了才有意义

---

## 七、调试 tips

| 问题 | 排查 |
|------|------|
| `juguang_daily.py` 报"找不到日期" | Excel 里的日期可能跟你预期不一致，用 `--date YYYY-MM-DD` 看可用日期列表 |
| CSV 列名报错 | 聚光改了字段名，看 `print(df.columns)` 对一下 |
| CDP 连不上 18800 | Chrome 没用 `--remote-debugging-port=18800` 启 |
| CDP 拿到 200 但 count=0 | API 通了但日期没数据，改 cdp_export.py 里的日期范围 |
| CDP 拿到 200 但 hasData=false | API 字段名变了，进 Chrome 的 Network 看真实请求 |
