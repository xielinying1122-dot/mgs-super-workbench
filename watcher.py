#!/usr/bin/env python3
"""
下载目录监听器 - 自动检测聚光导出的CSV → 清洗 → 聚合 → 日报
"""
import os, sys, time, logging
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path.home() / "juguang-automation"))
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("watcher")

from data_cleaner import DataCleaner
from aggregator import Aggregator
from report_generator import ReportGenerator
from anomaly_detector import AnomalyDetector
import pandas as pd

WATCH_DIR = Path.home() / "Downloads"
PATTERN = "聚光_蔡司MD_*.csv"
PROJECT_NAME = "蔡司-MD"
MONTH_BUDGET = 3000000  # TODO: 从config读取

cleaner = DataCleaner()
agg = Aggregator()
gen = ReportGenerator()
gen.project_name = PROJECT_NAME
gen.month_budget = MONTH_BUDGET
detector = AnomalyDetector()

logger.info(f"监听目录: {WATCH_DIR}")
logger.info(f"文件模式: {PATTERN}")

# 获取初始状态（排除已存在的文件）
known = set(str(f) for f in WATCH_DIR.glob(PATTERN))
logger.info(f"初始已知文件: {len(known)}")

while True:
    current = set(str(f) for f in WATCH_DIR.glob(PATTERN))
    new_files = current - known
    
    if new_files:
        for fpath in sorted(new_files):
            fname = Path(fpath).name
            logger.info(f"发现新文件: {fname}")
            
            # 等待文件完全写入
            time.sleep(1)
            
            try:
                # 复制到raw目录
                import shutil
                raw_dir = Path.home() / "juguang-automation" / "data" / "raw"
                dest = raw_dir / fname
                shutil.copy2(fpath, dest)
                logger.info(f"已复制到: {dest}")
                
                # 读取并识别类型
                df = pd.read_csv(fpath)
                file_type = "campaign"
                if "单元" in fname or "unit" in fname.lower():
                    file_type = "unit"
                elif "创意" in fname or "creative" in fname.lower():
                    file_type = "creative"
                
                # 清洗
                clean_df = cleaner.clean(df, file_type)
                logger.info(f"清洗: {len(df)} → {len(clean_df)} 条")
                
                # 保存清洗结果
                processed_dir = Path.home() / "juguang-automation" / "data" / "processed"
                processed_dir.mkdir(exist_ok=True)
                clean_path = processed_dir / f"clean_{file_type}_{fname.replace('.csv', '')}.csv"
                clean_df.to_csv(clean_path, index=False, encoding="utf-8-sig")
                logger.info(f"清洗结果: {clean_path}")
                
            except Exception as e:
                logger.error(f"处理 {fname} 失败: {e}")
        
        known = current
        
        # 所有文件处理完后生成日报
        if new_files:
            logger.info("所有文件处理完毕，生成日报...")
            try:
                # 读取所有清洗后的数据
                all_csvs = list((Path.home() / "juguang-automation" / "data" / "processed").glob("clean_*.csv"))
                if all_csvs:
                    dfs = [pd.read_csv(f) for f in all_csvs]
                    combined = pd.concat(dfs, ignore_index=True)
                    logger.info(f"合并 {len(dfs)} 个文件: {len(combined)} 条")
                    
                    # 聚合
                    results = agg.run_all(combined)
                    
                    # 异常检测
                    anomalies = detector.detect_all(
                        results.get("daily_summary", pd.DataFrame()),
                        results.get("campaign_performance", pd.DataFrame()),
                        results.get("creative_performance", pd.DataFrame()),
                    )
                    
                    # 生成日报
                    today = datetime.now().strftime("%Y-%m-%d")
                    report, path = gen.generate_and_save(
                        results.get("daily_summary", pd.DataFrame()),
                        results.get("ad_type_summary", pd.DataFrame()),
                        results.get("campaign_performance", pd.DataFrame()),
                        results.get("creative_performance", pd.DataFrame()),
                        results.get("keyword_performance", pd.DataFrame()),
                        anomalies,
                        today,
                    )
                    
                    print("\n" + "=" * 60)
                    print("日报已生成！")
                    print(report)
                    print("=" * 60)
                    
            except Exception as e:
                logger.error(f"生成日报失败: {e}")
    
    time.sleep(2)  # 每2秒扫描一次
