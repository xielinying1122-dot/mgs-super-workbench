#!/usr/bin/env python3
import frida
import sys
import time
import os
import subprocess

SCRIPT_CODE = open(os.path.expanduser("~/juguang-automation/get_wechat_key4.js")).read()
KEY_FILE = os.path.expanduser("~/.openclaw/workspace/wechat_data/db_key.txt")

found_keys = []
all_output = []

def on_message(message, data):
    if message['type'] == 'send':
        payload = message['payload']
        if payload.get('type') == 'key':
            key = payload['key']
            found_keys.append(key)
            print(f"\n[!!!KEY!!!] {key}\n")
            with open(KEY_FILE, 'a') as f:
                f.write(f"{key}\n")
        elif payload.get('type') == 'pragma_key':
            sql = payload.get('sql', '')
            print(f"\n[!!!PRAGMA!!!] {sql}\n")
            with open(KEY_FILE, 'a') as f:
                f.write(f"PRAGMA: {sql}\n")
    elif message['type'] == 'error':
        print(f"[ERR] {message.get('description', '')}")

def main():
    print("[*] 关闭微信...")
    subprocess.run(["pkill", "-9", "WeChat"], capture_output=True)
    subprocess.run(["killall", "WeChat"], capture_output=True)
    time.sleep(3)
    
    print("[*] Spawn 微信...")
    device = frida.get_local_device()
    wechat_path = "/Applications/WeChat.app/Contents/MacOS/WeChat"
    
    pid = device.spawn([wechat_path])
    print(f"[+] PID: {pid}")
    
    session = device.attach(pid)
    script = session.create_script(SCRIPT_CODE)
    script.on('message', on_message)
    script.load()
    
    print("[*] 恢复执行...")
    device.resume(pid)
    
    print("[*] 等待60秒...")
    try:
        for i in range(60):
            time.sleep(1)
            sys.stdout.write(f"\r  {i+1}/60s  keys={len(found_keys)}")
            sys.stdout.flush()
    except KeyboardInterrupt:
        pass
    
    print(f"\n\n结果: 捕获 {len(found_keys)} 个密钥")
    for k in found_keys:
        print(f"  {k}")
    
    session.detach()

if __name__ == '__main__':
    main()
