# -*- coding: utf-8 -*-
"""
串子语录采集脚本（开箱即用版）
数据源：一言开放 API https://v1.hitokoto.cn —— 免费、无需注册、稳定
依赖：pip install requests
输出：quotes.json（与 index.html 同目录）
说明：内置保底语录，即使接口异常也不会生成空文件导致网站空白。
"""
import json
import time
import hashlib
import random
from datetime import date
import requests

# ========== 配置区（无需修改） ==========
OUTPUT = "quotes.json"
FETCH_COUNT = 40
API_URL = "https://v1.hitokoto.cn/"

TYPE_MAP = {
    "a": ("饭圈", "B站"), "b": ("情感钓鱼", "知乎"), "c": ("情感钓鱼", "知乎"),
    "d": ("经典老串", "贴吧"), "e": ("键政", "知乎"), "f": ("互联网魔怔", "贴吧"),
    "g": ("互联网魔怔", "贴吧"), "h": ("游戏区", "NGA"), "i": ("情感钓鱼", "知乎"),
    "j": ("互联网魔怔", "抖音"), "k": ("饭圈", "微博"), "l": ("经典老串", "微博"),
}

SEED = [
    {"id": 90001, "content": "这波团战打完，我直接把显示器砸了，然后发现是梦境。", "category": "电竞圈", "source": "贴吧", "hot": True},
    {"id": 90002, "content": "打野不来 gank 我就挂机，这是规矩，懂？", "category": "电竞圈", "source": "NGA", "hot": False},
    {"id": 90003, "content": "我家哥哥唱歌虽然跑调，但那叫艺术加工，你懂不懂！", "category": "饭圈", "source": "微博", "hot": True},
    {"id": 90004, "content": "这个需求上午提下午要，很合理吧？又不是做火箭。", "category": "职场", "source": "贴吧", "hot": True},
    {"id": 90005, "content": "典！太典了！这帖子典中典，绷不住了。", "category": "互联网魔怔", "source": "贴吧", "hot": True},
    {"id": 90006, "content": "在吗？在吗？在吗？我有个东西给你看，保证刺激。", "category": "情感钓鱼", "source": "贴吧", "hot": True},
    {"id": 90007, "content": "这游戏平衡性做得真好，我删游戏了，祝大家玩得开心。", "category": "游戏区", "source": "NGA", "hot": True},
    {"id": 90008, "content": "前排占座，楼下复读，一楼楼上，二楼楼下。", "category": "经典老串", "source": "贴吧", "hot": True},
]


def load_existing(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            return [], set()
        return data, {item["id"] for item in data}
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return [], set()


def fetch_one(t):
    try:
        resp = requests.get(API_URL, params={"c": t, "encode": "utf-8", "_": time.time_ns()}, timeout=10)
        resp.raise_for_status()
        d = resp.json()
        content = d.get("hitokoto", "").strip()
        return content if 6 <= len(content) <= 300 else None
    except Exception as e:
        print(f"[WARN] 接口请求失败: {e}")
        return None


def stable_id(content):
    return 100000 + int(hashlib.md5(content.encode("utf-8")).hexdigest()[:6], 16) % 900000


def main():
    data, existing_ids = load_existing(OUTPUT)
    today = date.today().isoformat()

    for seed in SEED:
        if seed["id"] not in existing_ids:
            item = dict(seed)
            item["date"] = today
            data.append(item)
            existing_ids.add(seed["id"])

    types = list(TYPE_MAP.keys())
    added = 0
    for _ in range(FETCH_COUNT):
        t = random.choice(types)
        content = fetch_one(t)
        if not content:
            continue
        qid = stable_id(content)
        if qid in existing_ids:
            continue
        existing_ids.add(qid)
        category, source = TYPE_MAP[t]
        data.append({"id": qid, "content": content, "category": category,
                     "source": source, "date": today, "hot": False})
        added += 1
        time.sleep(0.1)

    data = sorted(data, key=lambda x: x.get("date", ""), reverse=True)[:200]

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"[DONE] 本次新增 {added} 条，共 {len(data)} 条语录 -> {OUTPUT}")


if __name__ == "__main__":
    main()
