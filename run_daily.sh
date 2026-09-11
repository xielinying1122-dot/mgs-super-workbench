#!/bin/bash
# ============================================================
# 聚光自动化 - 一键运行日报
# ============================================================
# 功能：检查CDP -> 自动登录检测 -> 生成日报
# 用法：./run_daily.sh [--date YYYY-MM-DD] [--project 项目名]
# ============================================================

set -e

CDP_PORT=9222
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}=== 聚光日报自动化 ===${NC}"

# 解析参数
DATE_ARG=""
PROJECT_ARG="蔡司眼镜"

while [[ $# -gt 0 ]]; do
    case $1 in
        --date)
            DATE_ARG="$2"
            shift 2
            ;;
        --project)
            PROJECT_ARG="$2"
            shift 2
            ;;
        *)
            echo "未知参数: $1"
            exit 1
            ;;
    esac
done

# 检查CDP是否可用
echo -n "检查 CDP 端口..."
if ! curl -s "http://localhost:$CDP_PORT/json/version" > /dev/null 2>&1; then
    echo -e "${RED}❌ CDP 端口 $CDP_PORT 不可达${NC}"
    echo ""
    echo "请先启动 Chrome CDP："
    echo "  ./start_chrome_cdp.sh"
    echo ""
    echo "或者手动启动 Chrome："
    echo '  /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \'
    echo "      --remote-debugging-port=$CDP_PORT \\"
    echo '      --user-data-dir="$HOME/.chrome-juguang-cdp" &'
    exit 1
fi
echo -e "${GREEN}✅ CDP 可用${NC}"

# 检查聚光登录态
echo -n "检查聚光登录..."
TABS=$(curl -s "http://localhost:$CDP_PORT/json" 2>/dev/null)
if ! echo "$TABS" | grep -q "xiaohongshu.com"; then
    echo -e "${RED}❌ 未找到聚光标签页${NC}"
    echo ""
    echo "请在 Chrome 中登录聚光："
    echo "  1. 打开 https://partner.xiaohongshu.com/"
    echo "  2. 登录后选择「蔡司眼镜」客户账户"
    echo "  3. 重新运行本脚本"
    exit 2
fi
echo -e "${GREEN}✅ 已找到聚光标签页${NC}"

# 运行流水线
echo ""
echo -e "${YELLOW}正在生成日报...${NC}"
cd "$SCRIPT_DIR"

CMD="python3 auto_pipeline.py daily --save"
if [ -n "$DATE_ARG" ]; then
    CMD="$CMD --date $DATE_ARG"
fi
CMD="$CMD --project \"$PROJECT_ARG\""

echo "执行: $CMD"
eval $CMD

echo ""
echo -e "${GREEN}✅ 日报生成完成！${NC}"
echo "日报位置: ~/juguang-automation/data/reports/"
