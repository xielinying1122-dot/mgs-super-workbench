#!/usr/bin/env python3
"""
小红书竞品分析 - 简化版（直接用CDP API）
"""
import json
import time
import requests
import websocket
import sys

CDP_URL = "http://localhost:9222"

def get_tabs():
    """获取所有标签页"""
    resp = requests.get(f"{CDP_URL}/json", timeout=5)
    return resp.json()

def create_tab(url):
    """创建新标签页"""
    resp = requests.put(f"{CDP_URL}/json/new?url={url}", timeout=10)
    return resp.json()

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

def main():
    user_url = "https://www.xiaohongshu.com/user/profile/55b04e595894462b9d580a11"
    
    print("=== 小红书竞品分析 ===")
    print(f"目标: {user_url}")
    print()
    
    # 创建新标签页
    print("1. 创建标签页...")
    tab = create_tab(user_url)
    target_id = tab["id"]
    ws_url = tab["webSocketDebuggerUrl"]
    print(f"   标签页ID: {target_id[:20]}...")
    
    # 等待页面加载
    print("2. 等待页面加载...")
    time.sleep(5)
    
    # 连接WebSocket
    ws = websocket.create_connection(ws_url, timeout=30)
    
    # 启用必要的域
    send_cmd(ws, "Runtime.enable")
    send_cmd(ws, "Page.enable")
    
    # 提取用户信息
    print("3. 提取用户信息...")
    user_info_js = """
    (function() {
        const name = document.querySelector('.user-name, .info-part .name, [class*="nickname"]');
        const desc = document.querySelector('.user-desc, [class*="desc"]');
        const fans = document.querySelector('[class*="fans"], [class*="follower"]');
        const notes = document.querySelector('[class*="note-count"]');
        
        return {
            name: name ? name.innerText.trim() : '未知用户',
            desc: desc ? desc.innerText.trim() : '',
            fans: fans ? fans.innerText.trim() : '',
            notes: notes ? notes.innerText.trim() : ''
        };
    })()
    """
    user_info = eval_js(ws, user_info_js)
    print(f"   用户: {user_info.get('name', '未知')}")
    print(f"   粉丝: {user_info.get('fans', '未知')}")
    print()
    
    # 滚动加载笔记
    print("4. 滚动加载笔记...")
    for i in range(10):
        eval_js(ws, "window.scrollBy(0, 1000)")
        time.sleep(0.5)
    
    # 提取笔记列表
    print("5. 提取笔记数据...")
    notes_js = """
    (function() {
        const notes = [];
        const cards = document.querySelectorAll('section.note-item, div.note-item, [class*="note-item"], a[href*="/explore/"]');
        
        cards.forEach(card => {
            const title = card.querySelector('[class*="title"], .desc, .note-text');
            const likes = card.querySelector('[class*="like"], [class*="count"]');
            const link = card.querySelector('a[href*="/explore/"]') || card.closest('a[href*="/explore/"]');
            
            if (title) {
                notes.push({
                    title: title.innerText.trim().substring(0, 100),
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
        print("   未找到笔记数据，可能需要登录")
        print("   请在Chrome中登录小红书后重试")
        ws.close()
        return
    
    print(f"   找到 {len(notes)} 篇笔记")
    print()
    
    # 分析数据
    print("6. 分析数据...")
    
    # 解析点赞数
    def parse_likes(text):
        if not text:
            return 0
        text = str(text).strip()
        if '万' in text:
            return int(float(text.replace('万', '')) * 10000)
        try:
            return int(text)
        except:
            return 0
    
    # 计算统计数据
    likes_list = [parse_likes(n.get('likes', '0')) for n in notes]
    total_likes = sum(likes_list)
    avg_likes = total_likes / len(notes) if notes else 0
    max_likes = max(likes_list) if likes_list else 0
    
    # 找出爆文（点赞 > 平均值的2倍）
    viral_threshold = avg_likes * 2
    viral_notes = [n for n, l in zip(notes, likes_list) if l > viral_threshold]
    
    # 生成报告
    print("7. 生成报告...")
    print()
    print("=" * 50)
    print("竞品分析报告")
    print("=" * 50)
    print()
    print(f"用户: {user_info.get('name', '未知')}")
    print(f"粉丝: {user_info.get('fans', '未知')}")
    print(f"笔记总数: {len(notes)}")
    print()
    print("📊 数据概览")
    print(f"  总点赞: {total_likes:,}")
    print(f"  平均点赞: {avg_likes:,.0f}")
    print(f"  最高点赞: {max_likes:,}")
    print(f"  爆文数量: {len(viral_notes)}")
    print(f"  爆文率: {len(viral_notes)/len(notes)*100:.1f}%")
    print()
    
    # Top 5 笔记
    print("🔥 Top 5 笔记")
    sorted_notes = sorted(zip(notes, likes_list), key=lambda x: x[1], reverse=True)
    for i, (note, likes) in enumerate(sorted_notes[:5], 1):
        print(f"  {i}. {note['title'][:40]}... - {likes:,}赞")
    print()
    
    # 爆文特征
    if viral_notes:
        print("📈 爆文特征")
        print(f"  爆文阈值: >{viral_threshold:,.0f}赞")
        for note in viral_notes[:3]:
            print(f"  - {note['title'][:50]}...")
        print()
    
    # 保存报告
    report_file = f"竞品分析_{user_info.get('name', '未知')}.md"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(f"# 竞品分析报告\n\n")
        f.write(f"## 用户信息\n")
        f.write(f"- 用户名: {user_info.get('name', '未知')}\n")
        f.write(f"- 粉丝数: {user_info.get('fans', '未知')}\n")
        f.write(f"- 笔记总数: {len(notes)}\n\n")
        f.write(f"## 数据概览\n")
        f.write(f"- 总点赞: {total_likes:,}\n")
        f.write(f"- 平均点赞: {avg_likes:,.0f}\n")
        f.write(f"- 最高点赞: {max_likes:,}\n")
        f.write(f"- 爆文数量: {len(viral_notes)}\n")
        f.write(f"- 爆文率: {len(viral_notes)/len(notes)*100:.1f}%\n\n")
        f.write(f"## Top 5 笔记\n")
        for i, (note, likes) in enumerate(sorted_notes[:5], 1):
            f.write(f"{i}. {note['title'][:50]} - {likes:,}赞\n")
        f.write(f"\n## 所有笔记\n")
        f.write(f"| 标题 | 点赞 |\n")
        f.write(f"|------|------|\n")
        for note, likes in sorted_notes:
            f.write(f"| {note['title'][:40]} | {likes:,} |\n")
    
    print(f"✅ 报告已保存: {report_file}")
    
    # 关闭标签页
    ws.close()

if __name__ == "__main__":
    main()
