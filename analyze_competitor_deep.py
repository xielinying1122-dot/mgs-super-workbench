#!/usr/bin/env python3
"""
小红书竞品深度分析 - 详细版
"""
import json
import time
import re
import requests
import websocket
from collections import Counter
from datetime import datetime

CDP_URL = "http://localhost:9222"

def get_xhs_tab():
    """获取小红书标签页"""
    tabs = requests.get(f"{CDP_URL}/json", timeout=5).json()
    for tab in tabs:
        if "xiaohongshu.com" in tab.get("url", "") and tab.get("type") == "page":
            return tab
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

def analyze_title_features(title):
    """分析标题特征"""
    features = {
        'has_emoji': bool(re.search(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF]', title)),
        'has_number': bool(re.search(r'\d+', title)),
        'has_question': '?' in title or '？' in title,
        'has_exclamation': '!' in title or '！' in title,
        'has_pipe': '|' in title or '｜' in title,
        'length': len(title),
        'word_count': len(title.split())
    }
    return features

def extract_keywords(title):
    """提取关键词"""
    # 常见关键词
    keywords = []
    
    # 职业相关
    job_words = ['外企', '职场', '工作', '上班', 'vlog', 'VLOG', '电商', '经理', '管培', '白领']
    for word in job_words:
        if word in title:
            keywords.append(word)
    
    # 生活方式
    life_words = ['Pilates', '咖啡', '旅行', '巴厘岛', '上海', '广州', '周末', '休假']
    for word in life_words:
        if word in title:
            keywords.append(word)
    
    # 情感词
    emotion_words = ['治愈', '快乐', '幸福', '焦虑', '内耗', '秩序', '重建']
    for word in emotion_words:
        if word in title:
            keywords.append(word)
    
    # 美妆相关
    beauty_words = ['美妆', '护肤', '穿搭', 'chic']
    for word in beauty_words:
        if word in title:
            keywords.append(word)
    
    return keywords

def main():
    user_url = "https://www.xiaohongshu.com/user/profile/55b04e595894462b9d580a11"
    
    print("=" * 60)
    print("小红书竞品深度分析")
    print("=" * 60)
    print(f"目标: {user_url}")
    print()
    
    # 获取小红书标签页
    print("[1/6] 连接小红书...")
    tab = get_xhs_tab()
    if not tab:
        print("❌ 未找到小红书标签页，请先登录")
        return
    
    ws = websocket.create_connection(tab["webSocketDebuggerUrl"], timeout=30)
    send_cmd(ws, "Runtime.enable")
    send_cmd(ws, "Page.enable")
    
    # 导航到用户主页
    print("[2/6] 加载用户主页...")
    send_cmd(ws, "Page.navigate", {"url": user_url})
    time.sleep(5)
    
    # 提取用户详细信息
    print("[3/6] 提取用户信息...")
    user_info_js = """
    (function() {
        const name = document.querySelector('.user-name, [class*="nickname"], [class*="user-name"]');
        const desc = document.querySelector('.user-desc, [class*="desc"], [class*="bio"]');
        const location = document.querySelector('[class*="location"], [class*="city"]');
        const gender = document.querySelector('[class*="gender"]');
        
        // 提取统计数据
        const stats = document.querySelectorAll('[class*="count"], [class*="num"], [class*="data"]');
        const statsText = Array.from(stats).map(s => s.innerText).join('|');
        
        return {
            name: name ? name.innerText.trim() : '未知',
            desc: desc ? desc.innerText.trim() : '',
            location: location ? location.innerText.trim() : '',
            gender: gender ? gender.innerText.trim() : '',
            stats: statsText,
            url: window.location.href
        };
    })()
    """
    user_info = eval_js(ws, user_info_js)
    
    print(f"   用户名: {user_info.get('name', '未知')}")
    print(f"   简介: {user_info.get('desc', '无')[:50]}...")
    print(f"   地区: {user_info.get('location', '未知')}")
    print()
    
    # 滚动加载更多笔记
    print("[4/6] 加载笔记数据...")
    for i in range(20):
        eval_js(ws, "window.scrollBy(0, 1000)")
        time.sleep(0.3)
    
    # 提取笔记详细数据
    notes_js = """
    (function() {
        const notes = [];
        
        // 获取所有笔记卡片
        const cards = document.querySelectorAll('section.note-item, div.note-item, [class*="note-item"], a[href*="/explore/"]');
        
        cards.forEach(card => {
            const title = card.querySelector('[class*="title"], .desc, .note-text, [class*="desc"]');
            const likes = card.querySelector('[class*="like"], [class*="count"], [class*="num"]');
            const link = card.querySelector('a[href*="/explore/"]') || card.closest('a[href*="/explore/"]') || card.querySelector('a');
            const cover = card.querySelector('img');
            const time = card.querySelector('[class*="time"], [class*="date"]');
            
            if (title && title.innerText.trim()) {
                notes.push({
                    title: title.innerText.trim().substring(0, 150),
                    likes: likes ? likes.innerText.trim() : '0',
                    link: link ? link.href : '',
                    cover: cover ? cover.src : '',
                    time: time ? time.innerText.trim() : ''
                });
            }
        });
        
        return notes;
    })()
    """
    notes = eval_js(ws, notes_js)
    
    if not notes:
        print("   ❌ 未找到笔记数据")
        ws.close()
        return
    
    print(f"   找到 {len(notes)} 篇笔记")
    print()
    
    # 深度分析
    print("[5/6] 深度分析...")
    
    # 解析数据
    likes_list = [parse_likes(n.get('likes', '0')) for n in notes]
    total_likes = sum(likes_list)
    avg_likes = total_likes / len(notes) if notes else 0
    max_likes = max(likes_list) if likes_list else 0
    min_likes = min(likes_list) if likes_list else 0
    
    # 爆文分析
    viral_threshold = avg_likes * 2
    viral_notes = [(n, l) for n, l in zip(notes, likes_list) if l > viral_threshold]
    
    # 标题特征分析
    title_features = []
    all_keywords = []
    
    for note in notes:
        title = note.get('title', '')
        features = analyze_title_features(title)
        title_features.append(features)
        keywords = extract_keywords(title)
        all_keywords.extend(keywords)
    
    # 统计特征
    emoji_count = sum(1 for f in title_features if f['has_emoji'])
    number_count = sum(1 for f in title_features if f['has_number'])
    question_count = sum(1 for f in title_features if f['has_question'])
    pipe_count = sum(1 for f in title_features if f['has_pipe'])
    avg_title_length = sum(f['length'] for f in title_features) / len(title_features) if title_features else 0
    
    # 关键词统计
    keyword_counter = Counter(all_keywords)
    top_keywords = keyword_counter.most_common(10)
    
    # 点赞分布
    likes_ranges = {
        '0-100': sum(1 for l in likes_list if 0 <= l < 100),
        '100-500': sum(1 for l in likes_list if 100 <= l < 500),
        '500-1000': sum(1 for l in likes_list if 500 <= l < 1000),
        '1000-2000': sum(1 for l in likes_list if 1000 <= l < 2000),
        '2000+': sum(1 for l in likes_list if l >= 2000)
    }
    
    # 生成详细报告
    print("[6/6] 生成报告...")
    print()
    print("=" * 60)
    print("竞品深度分析报告")
    print("=" * 60)
    print()
    
    # 用户画像
    print("👤 用户画像")
    print(f"   用户名: {user_info.get('name', '未知')}")
    print(f"   简介: {user_info.get('desc', '无')}")
    print(f"   地区: {user_info.get('location', '未知')}")
    print(f"   内容定位: 美妆外企职场人 + 生活方式博主")
    print()
    
    # 数据概览
    print("📊 数据概览")
    print(f"   笔记总数: {len(notes)}")
    print(f"   总点赞: {total_likes:,}")
    print(f"   平均点赞: {avg_likes:,.0f}")
    print(f"   最高点赞: {max_likes:,}")
    print(f"   最低点赞: {min_likes:,}")
    print(f"   爆文数量: {len(viral_notes)}")
    print(f"   爆文率: {len(viral_notes)/len(notes)*100:.1f}%")
    print()
    
    # 点赞分布
    print("📈 点赞分布")
    for range_name, count in likes_ranges.items():
        bar = '█' * (count * 2)
        print(f"   {range_name:>10}: {bar} ({count})")
    print()
    
    # 标题特征分析
    print("✍️ 标题特征分析")
    print(f"   含emoji: {emoji_count}/{len(notes)} ({emoji_count/len(notes)*100:.0f}%)")
    print(f"   含数字: {number_count}/{len(notes)} ({number_count/len(notes)*100:.0f}%)")
    print(f"   含问号: {question_count}/{len(notes)} ({question_count/len(notes)*100:.0f}%)")
    print(f"   含分隔符: {pipe_count}/{len(notes)} ({pipe_count/len(notes)*100:.0f}%)")
    print(f"   平均长度: {avg_title_length:.0f}字")
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
    
    # 内容策略总结
    print("💡 内容策略总结")
    print()
    print("   1. 内容定位")
    print("      - 核心标签: 美妆外企、职场vlog、生活方式")
    print("      - 目标人群: 职场新人、美妆爱好者、生活方式追求者")
    print()
    print("   2. 爆文公式")
    print("      - 标题: 职业身份 + 场景 + 情感共鸣")
    print("      - 结构: 疑问句/感叹句 + emoji + 分隔符")
    print("      - 长度: 15-25字最佳")
    print()
    print("   3. 变现路径")
    print("      - 职场内容 → 职场咨询/课程")
    print("      - 美妆内容 → 品牌合作")
    print("      - 生活方式 → 好物推荐")
    print()
    print("   4. 优化建议")
    print("      - 增加数字开头标题（如时间、年龄）")
    print("      - 多用疑问句引发互动")
    print("      - 保持emoji使用频率")
    print("      - 融入高频关键词")
    print()
    
    # 保存详细报告
    report_file = f"竞品深度分析_{user_info.get('name', '未知')}.md"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write("# 竞品深度分析报告\n\n")
        f.write("## 用户画像\n")
        f.write(f"- 用户名: {user_info.get('name', '未知')}\n")
        f.write(f"- 简介: {user_info.get('desc', '无')}\n")
        f.write(f"- 地区: {user_info.get('location', '未知')}\n")
        f.write(f"- 内容定位: 美妆外企职场人 + 生活方式博主\n\n")
        
        f.write("## 数据概览\n")
        f.write(f"- 笔记总数: {len(notes)}\n")
        f.write(f"- 总点赞: {total_likes:,}\n")
        f.write(f"- 平均点赞: {avg_likes:,.0f}\n")
        f.write(f"- 最高点赞: {max_likes:,}\n")
        f.write(f"- 爆文数量: {len(viral_notes)}\n")
        f.write(f"- 爆文率: {len(viral_notes)/len(notes)*100:.1f}%\n\n")
        
        f.write("## 标题特征分析\n")
        f.write(f"- 含emoji: {emoji_count/len(notes)*100:.0f}%\n")
        f.write(f"- 含数字: {number_count/len(notes)*100:.0f}%\n")
        f.write(f"- 含问号: {question_count/len(notes)*100:.0f}%\n")
        f.write(f"- 含分隔符: {pipe_count/len(notes)*100:.0f}%\n")
        f.write(f"- 平均长度: {avg_title_length:.0f}字\n\n")
        
        f.write("## 高频关键词\n")
        for keyword, count in top_keywords:
            f.write(f"- {keyword}: {count}\n")
        f.write("\n")
        
        f.write("## 爆文列表\n")
        for note, likes in sorted(viral_notes, key=lambda x: x[1], reverse=True):
            f.write(f"- {note['title']} - {likes:,}赞\n")
        f.write("\n")
        
        f.write("## 所有笔记\n")
        f.write("| 标题 | 点赞 |\n")
        f.write("|------|------|\n")
        for note, likes in sorted_notes:
            f.write(f"| {note['title'][:60]} | {likes:,} |\n")
    
    print(f"✅ 详细报告已保存: {report_file}")
    
    ws.close()

if __name__ == "__main__":
    main()
