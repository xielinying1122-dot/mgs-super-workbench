#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
聚光数据监听处理脚本
配合影刀RPA使用：影刀导出文件 → 此脚本自动处理 → 生成日报

使用方式：
    cd ~/juguang-automation && .venv/bin/python watcher_for_yingdao.py
    
或者后台运行：
    nohup ~/juguang-automation/.venv/bin/python ~/juguang-automation/watcher_for_yingdao.py &
"""

import os
import sys
import time
import shutil
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd

# 配置
RAW_DIR = Path.home() / "juguang-automation" / "data" / "raw"
PROCESS_DIR = Path.home() / "juguang-automation" / "data" / "processed"
REPORT_DIR = Path.home() / "juguang-automation" / "data" / "reports"
VENV_PYTHON = Path.home() / "juguang-automation" / ".venv" / "bin" / "python"

# 确保目录存在
for d in [RAW_DIR, PROCESS_DIR, REPORT_DIR]:
    d.mkdir(parents=True, exist_ok=True)


def find_new_file(old_files: set) -> Path:
    """检测新文件"""
    current_files = set(RAW_DIR.glob("*.xlsx")) | set(RAW_DIR.glob("*.csv"))
    new_files = current_files - old_files
    if new_files:
        return max(new_files, key=os.path.getctime)
    return None


def detect_date_from_file(filepath: Path) -> str:
    """从文件内容推断日期"""
    try:
        df = pd.read_excel(filepath, sheet_name=0)
        if '时间' in df.columns:
            dates = df['时间'].dropna().unique()
            if len(dates) > 0:
                latest = max(dates)
                return str(latest).split(' ')[0] if ' ' in str(latest) else str(latest)
    except Exception as e:
        print(f"读取文件失败: {e}")
    
    # 默认昨天
    return (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")


def clean_data(filepath: Path) -> bool:
    """清洗数据"""
    print(f"正在清洗数据: {filepath}")
    
    # 使用现有的清洗逻辑
    cmd = f"cd ~/juguang-automation && {VENV_PYTHON} main.py --mode clean"
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    
    if result.returncode == 0:
        print("✅ 数据清洗完成")
        return True
    else:
        print(f"❌ 清洗失败: {result.stderr}")
        return False


def generate_report(date: str) -> Path:
    """生成日报"""
    print(f"正在生成日报: {date}")
    
    cmd = f"cd ~/juguang-automation && {VENV_PYTHON} main.py --mode report --date {date}"
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    
    report_path = REPORT_DIR / f"日报_{date.replace('-', '')}.txt"
    
    if report_path.exists():
        print(f"✅ 日报生成完成: {report_path}")
        return report_path
    else:
        print(f"❌ 日报生成失败")
        return None


def format_daily_report(date: str) -> str:
    """格式化文字日报（用户指定格式）"""
    # 读取处理后的数据
    processed_file = PROCESS_DIR / f"daily_summary_{date.replace('-', '')}.csv"
    
    if not processed_file.exists():
        # 尝试从原始文件读取
        raw_files = list(RAW_DIR.glob("*.xlsx"))
        if raw_files:
            latest = max(raw_files, key=os.path.getctime)
            df = pd.read_excel(latest, sheet_name=0)
            df_date = df[df['时间'] == date]
            
            if len(df_date) == 0:
                return None
            
            # 计算核心指标
            total_cost = df_date['消费'].sum()
            total_show = df_date['展现量'].sum()
            total_click = df_date['点击量'].sum()
            ctr = total_click / total_show * 100 if total_show > 0 else 0
            cpc = total_cost / total_click if total_click > 0 else 0
            cpm = total_cost / total_show * 1000 if total_show > 0 else 0
            total_interact = df_date['互动量'].sum()
            cpe = total_cost / total_interact if total_interact > 0 else 0
            
            # 格式化日报
            date_fmt = date.replace('-', '')[-4:]  # 0503格式
            
            report = f"""【蔡司眼镜投放日报-{date_fmt}】

👉常规种草维度：
消耗¥{total_cost:.2f}、展现{total_show:,.0f}、点击{total_click:,.0f}、CTR {ctr:.2f}%、CPC ¥{cpc:.2f}、CPM ¥{cpm:.2f}、CPE ¥{cpe:.2f}

数据表现情况&今日动作👇：
1、投放阶段分析
2、优化调整动作
3、笔记数据（按笔记ID）
"""
            return report
    
    return None


def watch_and_process(interval: int = 5):
    """监听并处理"""
    print("=" * 50)
    print("聚光数据自动处理监听器")
    print("配合影刀RPA使用")
    print("=" * 50)
    print(f"监听目录: {RAW_DIR}")
    print(f"检查间隔: {interval}秒")
    print("等待影刀导出文件...")
    print()
    
    old_files = set(RAW_DIR.glob("*.xlsx")) | set(RAW_DIR.glob("*.csv"))
    last_processed = None
    
    while True:
        try:
            new_file = find_new_file(old_files)
            
            if new_file and new_file != last_processed:
                print(f"\n🔔 发现新文件: {new_file.name}")
                
                # 等待文件完全写入
                time.sleep(2)
                
                # 检测日期
                date = detect_date_from_file(new_file)
                print(f"检测到日期: {date}")
                
                # 清洗数据
                if clean_data(new_file):
                    # 生成日报
                    report = format_daily_report(date)
                    if report:
                        report_path = REPORT_DIR / f"日报_{date.replace('-', '')}.txt"
                        report_path.write_text(report)
                        print(f"\n📄 日报已生成:\n{report}")
                        print(f"\n日报文件: {report_path}")
                
                last_processed = new_file
                old_files = set(RAW_DIR.glob("*.xlsx")) | set(RAW_DIR.glob("*.csv"))
            
            time.sleep(interval)
            
        except KeyboardInterrupt:
            print("\n监听已停止")
            break
        except Exception as e:
            print(f"错误: {e}")
            time.sleep(interval)


def process_once():
    """单次处理（不监听）"""
    print("处理现有文件...")
    
    raw_files = list(RAW_DIR.glob("*.xlsx")) | set(RAW_DIR.glob("*.csv"))
    if not raw_files:
        print("没有找到数据文件")
        return
    
    latest = max(raw_files, key=os.path.getctime)
    print(f"处理文件: {latest}")
    
    date = detect_date_from_file(latest)
    print(f"检测到日期: {date}")
    
    report = format_daily_report(date)
    if report:
        print(f"\n{report}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="聚光数据监听处理")
    parser.add_argument("--once", action="store_true", help="单次处理，不监听")
    parser.add_argument("--interval", type=int, default=5, help="监听间隔（秒）")
    
    args = parser.parse_args()
    
    if args.once:
        process_once()
    else:
        watch_and_process(args.interval)