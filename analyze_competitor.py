#!/usr/bin/env python3
"""
小红书竞品深度分析 - 隔离版
通过CDP连接独立的Chrome实例，不影响日常Chrome
"""
import json
import time
import re
import requests
import websocket
import sys
from collections import Counter

CDP_URL = "http://localhost:9222"

def check_cdp():
    """检查CDP是否可用"""
    try:
        resp = requests.get(f"{CDP_URL}/json/version", timeout=5)
        return resp.status_code == 200
    except:
        return False

def get_xhs_tab():
    """获取小红书标签页"""
    try:
        tabs = requests.get(f"{CDP_URL}/json", timeout=5).json()
        for tab in tabs:
            if "xiaohongshu.com" in tab.get("url", "") and tab.get("type") == "page":
                return tab
    except:
        pass
    return None

def create_xhs_tab():
    """创建新的小红书标签页"""
    try:
        resp = requests.put(f"{CDP_URL}/json/new?url=https://www.xiaohongshu.com/", timeout=10)
        return resp.json()
    except:
        return None

def send_cmd(ws, method, params=None):
    """发送CDP命令"""
    msg_id = int(time.time() * 1000) % 100000
    ws.send(json.dumps({"id": msg_id, "method": method, "params": params or {}}))
    while True:
        raw = ws.recv()
        resp = json.loads(raw)
        if resp.get("id") == msg_id:
            return resp

def eval_js(ws, expression):
    """执行JavaScript"""
    result = send_cmd(ws, "Runtime.evaluate", {
        "expression": expression,
        "returnByValue": True,
        "awaitPromise": True
    })
    return result.get("result", {}).get("result", {}).get("value")

def parse_likes(text):
    """解析点赞数"""
    if not text:
        return 0
    text = str(text).strip()
    if '万' in text:
        return int(float(text.replace('万', '')) * 10000)
    if '亿' in text:
        return int(float(text.replace('亿', '')) * 100000000)
    try:
        return int(text)
    except:
        return 0

def main():
    user_url = "https://www.xiaohongshu.com/user/profile/55b04e595894462b9d580a11"
    
    print("=" * 60)
    print("小红书竞品深度分析")
    print("=" * 60)
    print(f"目标: {user_url}")
    print()
    
    # 检查CDP
    print("[1/6] 检查CDP连接...")
    if not check_cdp():
        print("❌ CDP未运行")
        print("请先启动CDP Chrome：")
        print("  cd ~/juguang-automation")
        print("  ./start_chrome_cdp.sh")
        print()
        print("注意：CDP Chrome是独立实例，不影响你日常使用的Chrome")
        sys.exit(1)
    
    print("✅ CDP已连接")
    
    # 获取小红书标签页
    print("[2/6] 查找小红书标签页...")
    tab = get_xhs_tab()
    if not tab:
        print("   未找到小红书标签页，正在创建...")
        tab = create_xhs_tab()
        if not tab:
            print("❌ 无法创建小红书标签页")
            sys.exit(1)
        time.sleep(5)
    
    print(f"   找到: {tab['title'][:30]}...")
    ws_url = tab["webSocketDebuggerUrl"]
    
    # 连接WebSocket
    ws = websocket.create_connection(ws_url, timeout=30)
    send_cmd(ws, "Runtime.enable")
    send_cmd(ws, "Page.enable")
    
    # 导航到用户主页
    print(f"[3/6] 加载用户主页...")
    send_cmd(ws, "Page.navigate", {"url": user_url})
    time.sleep(5)
    
    # 提取用户信息
    print("[4/6] 提取用户信息...")
    user_info_js = """
    (function() {
        const name = document.querySelector('.user-name, [class*="nickname"], [class*="user-name"]');
        const desc = document.querySelector('.user-desc, [class*="desc"], [class*="bio"]');
        const location = document.querySelector('[class*="location"], [class*="city"]');
        
        return {
            name: name ? name.innerText.trim() : '未知',
            desc: desc ? desc.innerText.trim() : '',
            location: location ? location.innerText.trim() : '',
            url: window.location.href
        };
    })()
    """
    user_info = eval_js(ws, user_info_js)
    
    print(f"   用户名: {user_info.get('name', '未知')}")
    print(f"   简介: {user_info.get('desc', '无')[:50]}...")
    print()
    
    # 滚动加载笔记
    print("[5/6] 加载笔记数据...")
    for i in range(20):
        eval_js(ws, "window.scrollBy(0, 1000)")
        time.sleep(0.3)
    
    # 提取笔记数据
    notes_js = """
    (function() {
        const notes = [];
        const cards = document.querySelectorAll('section.note-item, div.note-item, [class*="note-item"], a[href*="/explore/"]');
        
        cards.forEach(card => {
            const title = card.querySelector('[class*="title"], .desc, .note-text, [class*="desc"]');
            const likes = card.querySelector('[class*="like"], [class*="count"], [class*="num"]');
            const link = card.querySelector('a[href*="/explore/"]') || card.closest('a[href*="/explore/"]') || card.querySelector('a');
            
            if (title && title.innerText.trim()) {
                notes.push({
                    title: title.innerText.trim().substring(0, 150),
                    likes: likes ? likes.innerText.trim() : '0',
                    link: link ? link.href : ''
                });
            }
        });
        
        return notes;
    })()
    """
    notes = eval_js(ws, notes_js)
    
    if not notes:
        print("❌ 未找到笔记数据")
        print("请检查：")
        print("  1. CDP Chrome中是否已登录小红书")
        print("  2. 用户主页URL是否正确")
        ws.close()
        sys.exit(1)
    
    print(f"   找到 {len(notes)} 篇笔记")
    print()
    
    # 深度分析
    print("[6/6] 深度分析...")
    
    # 解析数据
    likes_list = [parse_likes(n.get('likes', '0')) for n in notes]
    total_likes = sum(likes_list)
    avg_likes = total_likes / len(notes) if notes else 0
    max_likes = max(likes_list) if likes_list else 0
    
    # 爆文分析
    viral_threshold = avg_likes * 2
    viral_notes = [(n, l) for n, l in zip(notes, likes_list) if l > viral_threshold]
    
    # 关键词提取
    all_keywords = []
    for note in notes:
        title = note.get('title', '')
        keywords = ['外企', 'vlog', '美妆', '职场', '上海', '电商', '治愈', '经理', '上班']
        for kw in keywords:
            if kw in title:
                all_keywords.append(kw)
    
    keyword_counter = Counter(all_keywords)
    top_keywords = keyword_counter.most_common(10)
    
    # 生成报告
    print()
    print("=" * 60)
    print("竞品深度分析报告")
    print("=" * 60)
    print()
    
    # 用户画像
    print("👤 用户画像")
    print(f"   用户名: {user_info.get('name', '未知')}")
    print(f"   简介: {user_info.get('desc', '无')}")
    print()
    
    # 数据概览
    print("📊 数据概览")
    print(f"   笔记总数: {len(notes)}")
    print(f"   总点赞: {total_likes:,}")
    print(f"   平均点赞: {avg_likes:,.0f}")
    print(f"   最高点赞: {max_likes:,}")
    print(f"   爆文数量: {len(viral_notes)}")
    print(f"   爆文率: {len(viral_notes)/len(notes)*100:.1f}%")
    print()
    
    # 高频关键词
    print("🔑 高频关键词")
    for keyword, count in top_keywords:
        bar = '█' * count
        print(f"   {keyword:>10}: {bar} ({count})")
    print()
    
    # 爆文分析
    print("🔥 爆文分析 (点赞 > 平均值2倍)")
    print(f"   爆文阈值: >{viral_threshold:,.0f}赞")
    print()
    for note, likes in sorted(viral_notes, key=lambda x: x[1], reverse=True):
        print(f"   • {note['title'][:50]}...")
        print(f"     点赞: {likes:,}")
        print()
    
    # Top 10 笔记
    print("🏆 Top 10 笔记")
    sorted_notes = sorted(zip(notes, likes_list), key=lambda x: x[1], reverse=True)
    for i, (note, likes) in enumerate(sorted_notes[:10], 1):
        print(f"   {i:>2}. {note['title'][:45]}...")
        print(f"       点赞: {likes:,}")
    print()
    
    # 保存报告
    report_file = f"竞品深度分析_{user_info.get('name', '未知')}.md"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write("# 竞品深度分析报告\n\n")
        f.write("## 用户画像\n")
        f.write(f"- 用户名: {user_info.get('name', '未知')}\n")
        f.write(f"- 简介: {user_info.get('desc', '无')}\n\n")
        f.write("## 数据概览\n")
        f.write(f"- 笔记总数: {len(notes)}\n")
        f.write(f"- 总点赞: {total_likes:,}\n")
        f.write(f"- 平均点赞: {avg_likes:,.0f}\n")
        f.write(f"- 最高点赞: {max_likes:,}\n")
        f.write(f"- 爆文数量: {len(viral_notes)}\n")
        f.write(f"- 爆文率: {len(viral_notes)/len(notes)*100:.1f}%\n\n")
        f.write("## 高频关键词\n")
        for keyword, count in top_keywords:
            f.write(f"- {keyword}: {count}\n")
        f.write("\n")
        f.write("## 所有笔记\n")
        f.write("| 标题 | 点赞 |\n")
        f.write("|------|------|\n")
        for note, likes in sorted_notes:
            f.write(f"| {note['title'][:60]} | {likes:,} |\n")
    
    print(f"✅ 报告已保存: {report_file}")
    
    ws.close()

if __name__ == "__main__":
    main()
