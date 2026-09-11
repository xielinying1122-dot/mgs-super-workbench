#!/bin/bash
# ============================================================
# 聚光自动化 - 定时任务设置
# ============================================================
# 功能：设置crontab每天自动运行日报
# 用法：./setup_cron.sh [--time HH:MM]
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_TIME="09:00"

# 解析参数
TIME="$DEFAULT_TIME"
while [[ $# -gt 0 ]]; do
    case $1 in
        --time)
            TIME="$2"
            shift 2
            ;;
        *)
            echo "未知参数: $1"
            exit 1
            ;;
    esac
done

# 解析时间
HOUR=$(echo "$TIME" | cut -d: -f1)
MINUTE=$(echo "$TIME" | cut -d: -f2)

echo "=== 设置聚光日报定时任务 ==="
echo "时间: 每天 $TIME"
echo ""

# 创建crontab条目
CRON_ENTRY="$MINUTE $HOUR * * * cd $SCRIPT_DIR && ./run_daily.sh >> logs/cron.log 2>&1"

# 检查是否已存在
if crontab -l 2>/dev/null | grep -q "run_daily.sh"; then
    echo "⚠️  已存在聚光日报定时任务"
    echo "当前任务:"
    crontab -l | grep "run_daily.sh"
    echo ""
    read -p "是否更新？(y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "已取消"
        exit 0
    fi
    # 删除旧任务
    crontab -l | grep -v "run_daily.sh" | crontab -
fi

# 添加新任务
(crontab -l 2>/dev/null; echo "$CRON_ENTRY") | crontab -

echo "✅ 定时任务已设置"
echo ""
echo "查看任务: crontab -l"
echo "删除任务: crontab -l | grep -v 'run_daily.sh' | crontab -"
echo ""
echo "注意：需要保持电脑开机且Chrome CDP运行"
