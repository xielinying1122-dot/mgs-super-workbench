#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
聚光数据自动导出脚本
使用Selenium + Chrome profile实现自动化
"""

import os
import sys
import time
import glob
import shutil
from datetime import datetime, timedelta
from pathlib import Path

# 添加虚拟环境路径
VENV_PATH = Path.home() / "juguang-automation" / ".venv"
sys.path.insert(0, str(VENV_PATH / "lib" / "python3.14" / "site-packages"))

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys


class JuguangAutoExporter:
    """聚光数据自动导出器"""
    
    def __init__(self, profile_path: str = None, headless: bool = False):
        """
        初始化
        
        Args:
            profile_path: Chrome profile路径，如 ~/Library/Application Support/Google/Chrome/Profile 34
            headless: 是否无头模式
        """
        self.profile_path = profile_path
        self.headless = headless
        self.driver = None
        
    def init_driver(self):
        """初始化Chrome驱动"""
        options = Options()
        
        # 使用用户现有的Chrome profile
        if self.profile_path:
            profile_dir = os.path.dirname(self.profile_path)
            profile_name = os.path.basename(self.profile_path)
            options.add_argument(f"--user-data-dir={profile_dir}")
            options.add_argument(f"--profile-directory={profile_name}")
        
        if self.headless:
            options.add_argument("--headless=new")
        
        # 反检测
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        # 设置下载目录
        download_dir = Path.home() / "juguang-automation" / "data" / "raw"
        download_dir.mkdir(parents=True, exist_ok=True)
        
        prefs = {
            "download.default_directory": str(download_dir),
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True
        }
        options.add_experimental_option("prefs", prefs)
        
        # 使用系统Chrome
        options.binary_location = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        
        self.driver = webdriver.Chrome(options=options)
        
        # 反检测JS
        self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined})
            """
        })
        
        return self.driver
    
    def export_data(self, v_seller_id: str, start_date: str, end_date: str):
        """
        导出聚光数据
        
        Args:
            v_seller_id: 卖家ID
            start_date: 开始日期 YYYY-MM-DD
            end_date: 结束日期 YYYY-MM-DD
        """
        if not self.driver:
            self.init_driver()
        
        # 构建URL
        url = f"https://ad.xiaohongshu.com/aurora/data/creative?vSellerId={v_seller_id}"
        
        print(f"正在打开: {url}")
        self.driver.get(url)
        
        # 等待页面加载
        time.sleep(3)
        
        # 检查是否需要登录
        if "login" in self.driver.current_url or "登录" in self.driver.title:
            print("⚠️ 需要登录！请在浏览器中手动登录，登录后按回车继续...")
            input()
        
        # 等待数据加载
        try:
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "table, .ant-table"))
            )
        except:
            print("⚠️ 页面加载超时，请检查网络")
            return None
        
        # TODO: 根据实际页面结构填写日期选择和导出逻辑
        # 这里需要根据聚光后台的实际HTML结构来编写
        
        print("✅ 页面加载成功，请手动选择日期并点击导出")
        print("导出完成后按回车继续...")
        input()
        
        return self.check_downloaded_file()
    
    def check_downloaded_file(self):
        """检查下载的文件"""
        download_dir = Path.home() / "juguang-automation" / "data" / "raw"
        
        # 等待下载完成
        time.sleep(2)
        
        # 查找最新的CSV/Excel文件
        files = list(download_dir.glob("*.csv")) + list(download_dir.glob("*.xlsx"))
        if files:
            latest = max(files, key=os.path.getctime)
            print(f"✅ 找到下载文件: {latest}")
            return latest
        return None
    
    def close(self):
        """关闭浏览器"""
        if self.driver:
            self.driver.quit()


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="聚光数据自动导出")
    parser.add_argument("--profile", type=str, help="Chrome profile路径")
    parser.add_argument("--seller-id", type=str, required=True, help="卖家ID (vSellerId)")
    parser.add_argument("--start-date", type=str, help="开始日期 YYYY-MM-DD")
    parser.add_argument("--end-date", type=str, help="结束日期 YYYY-MM-DD")
    parser.add_argument("--headless", action="store_true", help="无头模式")
    
    args = parser.parse_args()
    
    # 默认昨天
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    start_date = args.start_date or yesterday
    end_date = args.end_date or yesterday
    
    exporter = JuguangAutoExporter(
        profile_path=args.profile,
        headless=args.headless
    )
    
    try:
        result = exporter.export_data(
            v_seller_id=args.seller_id,
            start_date=start_date,
            end_date=end_date
        )
        
        if result:
            print(f"\n✅ 数据导出成功: {result}")
            print("\n接下来运行数据清洗和日报生成:")
            print(f"  cd ~/juguang-automation && .venv/bin/python main.py --mode clean")
            print(f"  cd ~/juguang-automation && .venv/bin/python main.py --mode report --date {start_date}")
    finally:
        exporter.close()


if __name__ == "__main__":
    main()
