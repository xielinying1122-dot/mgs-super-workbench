#!/usr/bin/env python3
"""
微信密钥提取 - Spawn 模式
关闭微信后重新启动，在启动过程中捕获密钥
"""
import frida
import sys
import time
import os
import subprocess

SCRIPT_CODE = open(os.path.expanduser("~/juguang-automation/get_wechat_key_spawn.js")).read()
KEY_FILE = os.path.expanduser("~/.openclaw/workspace/wechat_data/db_key.txt")

found_keys = []

def on_message(message, data):
    if message['type'] == 'send':
        payload = message['payload']
        if payload.get('type') == 'key':
            key = payload['key']
            found_keys.append(key)
            print(f"\n{'='*60}")
            print(f"[!!!] 密钥捕获成功: {key}")
            print(f"      长度: {payload.get('len')}")
            print(f"      来源: {payload.get('source')}")
            print(f"{'='*60}\n")
            with open(KEY_FILE, 'a') as f:
                f.write(f"{key}\n")
    elif message['type'] == 'error':
        print(f"[ERR] {message.get('description', '')}")

def main():
    # 先关闭微信
    print("[*] 正在关闭微信...")
    subprocess.run(["pkill", "-f", "WeChat"], capture_output=True)
    subprocess.run(["pkill", "-f", "微信"], capture_output=True)
    time.sleep(3)
    
    # 用 spawn 模式启动微信
    print("[*] 以 spawn 模式启动微信...")
    device = frida.get_local_device()
    
    # 找到微信的路径
    wechat_path = "/Applications/WeChat.app/Contents/MacOS/WeChat"
    if not os.path.exists(wechat_path):
        print(f"[-] 微信不在 {wechat_path}")
        sys.exit(1)
    
    pid = device.spawn([wechat_path])
    print(f"[+] 微信已启动 PID: {pid}")
    
    session = device.attach(pid)
    script = session.create_script(SCRIPT_CODE)
    script.on('message', on_message)
    script.load()
    
    print("[*] Hook 已注入，恢复微信执行...")
    device.resume(pid)
    
    print("[*] 等待密钥捕获... (最多等60秒)")
    
    try:
        for i in range(60):
            time.sleep(1)
            if found_keys:
                print(f"\n[+] 已捕获 {len(found_keys)} 个密钥!")
                # 多等几秒看有没有更多
                time.sleep(5)
                break
    except KeyboardInterrupt:
        pass
    
    print(f"\n{'='*60}")
    if found_keys:
        # 去重
        unique_keys = list(set(found_keys))
        print(f"[+] 共捕获 {len(unique_keys)} 个唯一密钥:")
        for i, k in enumerate(unique_keys, 1):
            print(f"    {i}. {k}")
        print(f"\n[+] 已保存到: {KEY_FILE}")
    else:
        print("[-] 未捕获到密钥")
    print(f"{'='*60}")
    
    try:
        session.detach()
    except:
        pass

if __name__ == '__main__':
    main()
