# 聚光自动化 - 完整解决方案

## 🎯 问题

1. **Python直调API失败** - 406错误，需要浏览器签名头
2. **手动下载Excel** - 每天都要手动操作，无法自动化
3. **Chrome扩展未完成** - 有bug，CDP方案更优

## ✅ 解决方案

### 方案1：CDP自动化（推荐）

通过Chrome DevTools Protocol控制浏览器，在浏览器上下文中调用API，绕开签名问题。

#### 一次性配置

```bash
# 1. 启动Chrome CDP
./start_chrome_cdp.sh

# 2. 在Chrome中登录聚光（首次）
#    - 访问 https://partner.xiaohongshu.com/
#    - 登录后选择「蔡司眼镜」客户账户
```

#### 每天使用

```bash
# 方式1：一键运行
./run_daily.sh

# 方式2：指定日期
./run_daily.sh --date 2026-05-21

# 方式3：指定项目
./run_daily.sh --project "汤臣倍健-MD"
```

### 方案2：全自动（定时任务）

```bash
# 设置每天9点自动运行
./setup_cron.sh --time 09:00

# 查看任务
crontab -l

# 删除任务
crontab -l | grep -v 'run_daily.sh' | crontab -
```

### 方案3：开机自启动Chrome CDP

launchd plist已创建：`~/Library/LaunchAgents/com.juguang.chrome-cdp.plist`

```bash
# 加载
launchctl load ~/Library/LaunchAgents/com.juguang.chrome-cdp.plist

# 卸载
launchctl unload ~/Library/LaunchAgents/com.juguang.chrome-cdp.plist
```

## 📁 文件说明

| 文件 | 用途 |
|------|------|
| `start_chrome_cdp.sh` | 启动Chrome CDP |
| `run_daily.sh` | 一键运行日报 |
| `setup_cron.sh` | 设置定时任务 |
| `auto_pipeline.py` | 核心自动化脚本 |
| `juguang_daily.py` | Excel→日报转换器 |

## 🔧 故障排查

### 问题1：CDP端口不可达
```bash
# 检查Chrome是否运行
ps aux | grep Chrome | grep remote-debugging-port

# 重启Chrome
./start_chrome_cdp.sh
```

### 问题2：未找到聚光标签页
```bash
# 在Chrome中手动打开聚光
open -a "Google Chrome" "https://partner.xiaohongshu.com/"
```

### 问题3：登录态失效
```bash
# 在Chrome中重新登录
# 1. 打开 https://partner.xiaohongshu.com/
# 2. 登录后选择「蔡司眼镜」客户账户
# 3. 重新运行 ./run_daily.sh
```

## 📊 工作流程

```
┌─────────────────────────────────────────────────────────────┐
│  start_chrome_cdp.sh                                        │
│  └─ 启动Chrome with --remote-debugging-port=9222            │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  run_daily.sh                                               │
│  ├─ 检查CDP端口                                              │
│  ├─ 检查聚光登录态                                            │
│  └─ 运行 auto_pipeline.py daily --save                      │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  auto_pipeline.py                                           │
│  ├─ 通过CDP连接Chrome                                        │
│  ├─ 在浏览器中调用聚光API（自动携带签名头）                       │
│  ├─ 保存数据到 data/raw/                                     │
│  └─ 调用 juguang_daily.py 生成日报                           │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  data/reports/日报_<项目>_<日期>.txt                          │
└─────────────────────────────────────────────────────────────┘
```

## 🚀 快速开始

```bash
# 1. 首次配置
./start_chrome_cdp.sh

# 2. 登录聚光后测试
./run_daily.sh

# 3. 设置定时任务（可选）
./setup_cron.sh --time 09:00
```
