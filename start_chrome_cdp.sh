#!/bin/bash
# ============================================================
# Chrome CDP 启动器（隔离版）
# ============================================================
# 功能：启动独立的CDP Chrome实例，不影响日常Chrome
# 用法：./start_chrome_cdp.sh [--bg]
# ============================================================

set -e

CDP_PORT=9222
CHROME_PROFILE="$HOME/.chrome-juguang-cdp"
XHS_URL="https://www.xiaohongshu.com/"

# 颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}=== Chrome CDP 启动器（隔离版） ===${NC}"

# 检查CDP端口是否已被占用
if curl -s "http://localhost:$CDP_PORT/json/version" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Chrome CDP 已在端口 $CDP_PORT 运行${NC}"
    
    # 检查是否有小红书tab
    TABS=$(curl -s "http://localhost:$CDP_PORT/json" 2>/dev/null)
    if echo "$TABS" | grep -q "xiaohongshu.com"; then
        echo -e "${GREEN}✅ 已找到小红书标签页${NC}"
    else
        echo -e "${YELLOW}⚠️  未找到小红书标签页，将在CDP Chrome中打开${NC}"
        # 在CDP Chrome中打开小红书（通过CDP API）
        curl -s "http://localhost:$CDP_PORT/json/new?url=$XHS_URL" > /dev/null 2>&1
    fi
    
    if [ "$1" != "--bg" ]; then
        echo ""
        echo "按 Enter 退出..."
        read
    fi
    exit 0
fi

echo -e "${YELLOW}启动独立的CDP Chrome实例...${NC}"
echo -e "${YELLOW}（不影响你日常使用的Chrome）${NC}"
echo ""

# 启动带调试端口的Chrome（使用独立配置文件）
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
    --remote-debugging-port=$CDP_PORT \
    --remote-allow-origins=* \
    --user-data-dir="$CHROME_PROFILE" \
    --no-first-run \
    --no-default-browser-check \
    "$XHS_URL" &
    
CHROME_PID=$!
echo -e "${GREEN}CDP Chrome 已启动 (PID: $CHROME_PID)${NC}"
echo -e "${YELLOW}请在 CDP Chrome 中登录小红书...${NC}"
echo ""
echo -e "${YELLOW}注意：这是独立的Chrome实例，与你日常Chrome完全隔离${NC}"
echo -e "${YELLOW}你需要在这个Chrome中重新登录小红书${NC}"

# 等待CDP端口可用
echo -n "等待 CDP 端口就绪"
for i in {1..30}; do
    if curl -s "http://localhost:$CDP_PORT/json/version" > /dev/null 2>&1; then
        echo -e "\n${GREEN}✅ CDP 端口 $CDP_PORT 已就绪${NC}"
        break
    fi
    echo -n "."
    sleep 1
done

if [ "$1" != "--bg" ]; then
    echo ""
    echo -e "${GREEN}登录完成后，按 Enter 继续...${NC}"
    read
fi
