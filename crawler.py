# -*- coding: utf-8 -*-
"""
串子语录采集脚本（多源开箱即用版）
====================================
采集源：
  1. 一言 API（v1.hitokoto.cn）—— 12 个分类，主源，稳定
  2. vvhan 段子 API          —— 补充源，失败自动跳过
  3. 天若笑话 API            —— 补充源，失败自动跳过
  4. 内置保底种子 20 条      —— 所有接口都挂了也不会让网站空白
依赖：pip install requests
输出：quotes.json（与 index.html 同目录）
说明：所有接口都带 try/except，单个源失败不影响其他源；直接粘贴即可运行。
"""
import json
import random
import hashlib
from datetime import date
import requests

# ========== 配置区（无需修改） ==========
OUTPUT = "quotes.json"
PER_SOURCE = 8           # 每个分类/源每次请求次数（越小越快）
TIMEOUT = 5              # 单次请求超时（秒）
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                         "AppleWebKit/537.36 Chrome/120.0 Safari/537.36"}

# 一言分类 -> 本站分类 / 来源平台（12 个分类全覆盖）
HITOKOTO_MAP = {
    "a": ("饭圈", "B站"), "b": ("情感钓鱼", "知乎"), "c": ("情感钓鱼", "知乎"),
    "d": ("经典老串", "贴吧"), "e": ("键政", "知乎"), "f": ("互联网魔怔", "贴吧"),
    "g": ("互联网魔怔", "贴吧"), "h": ("游戏区", "NGA"), "i": ("情感钓鱼", "知乎"),
    "j": ("职场", "贴吧"), "k": ("键政", "微博"), "l": ("电竞圈", "NGA"),
}

# 补充源配置（网络开放时生效，失败自动跳过）
EXTRA_SOURCES = [
    {"url": "https://api.vvhan.com/api/duanzi", "category": "互联网魔怔", "source": "段子站", "key": "data"},
    {"url": "https://api.qqsuu.cn/api/dm-joke", "category": "互联网魔怔", "source": "笑话站", "key": "content"},
]

# 保底种子 20 条：确保任何情况下网站都不会空白
SEED = [
    {"id": 90001, "content": "这波团战打完，我直接把显示器砸了，然后发现是梦境。", "category": "电竞圈", "source": "贴吧", "hot": True},
    {"id": 90002, "content": "打野不来 gank 我就挂机，这是规矩，懂？", "category": "电竞圈", "source": "NGA", "hot": False},
    {"id": 90003, "content": "辅助不插眼？那我 AD 为什么不 A 兵，reply 一下。", "category": "电竞圈", "source": "微博", "hot": False},
    {"id": 90004, "content": "我家哥哥唱歌虽然跑调，但那叫艺术加工，你懂不懂！", "category": "饭圈", "source": "微博", "hot": True},
    {"id": 90005, "content": "你说我家哥哥不好看？你眼睛是不是捐了？", "category": "饭圈", "source": "抖音", "hot": False},
    {"id": 90006, "content": "控评！控评！把不好的评论都点举报，冲鸭！", "category": "饭圈", "source": "微博", "hot": False},
    {"id": 90007, "content": "这个需求上午提下午要，很合理吧？又不是做火箭。", "category": "职场", "source": "贴吧", "hot": True},
    {"id": 90008, "content": "工资三千，操心三亿的项目，格局打开了。", "category": "职场", "source": "NGA", "hot": False},
    {"id": 90009, "content": "弹性工作制嘛，就是弹性地加班，很柔性。", "category": "职场", "source": "贴吧", "hot": False},
    {"id": 90010, "content": "典！太典了！这帖子典中典，绷不住了。", "category": "互联网魔怔", "source": "贴吧", "hot": True},
    {"id": 90011, "content": "我不说话，我就静静地看着你表演。", "category": "互联网魔怔", "source": "抖音", "hot": False},
    {"id": 90012, "content": "你急了，你急了，你开始急了，哈哈哈哈。", "category": "互联网魔怔", "source": "NGA", "hot": True},
    {"id": 90013, "content": "我先声明我是理性讨论，但你这个说法我不认同。", "category": "键政", "source": "微博", "hot": False},
    {"id": 90014, "content": "键盘在手，天下我有，指点江山挥斥方遒。", "category": "键政", "source": "贴吧", "hot": False},
    {"id": 90015, "content": "在吗？在吗？在吗？我有个东西给你看，保证刺激。", "category": "情感钓鱼", "source": "贴吧", "hot": True},
    {"id": 90016, "content": "其实我一直在默默关注你，从你第一条动态开始。", "category": "情感钓鱼", "source": "抖音", "hot": False},
    {"id": 90017, "content": "这游戏平衡性做得真好，我删游戏了，祝大家玩得开心。", "category": "游戏区", "source": "NGA", "hot": True},
    {"id": 90018, "content": "氪金？这辈子都不可能氪金的，除非真的很划算。", "category": "游戏区", "source": "贴吧", "hot": False},
    {"id": 90019, "content": "前排占座，楼下复读，一楼楼上，二楼楼下。", "category": "经典老串", "source": "贴吧", "hot": True},
    {"id": 90020, "content": "马克一下，收藏了，以后再看，大概率不会看。", "category": "经典老串", "source": "NGA", "hot": False},
]


def get(url, params=None):
    """统一的 GET 请求，失败返回 None"""
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        return r
    except Exception as e:
        print(f"[WARN] 请求失败 {url}: {e}")
        return None


def load_existing(path):
    """读取已有数据，返回 (列表, id集合)；异常则返回空"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            return [], set()
        return data, {item["id"] for item in data}
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return [], set()


def stable_id(text):
    """基于内容生成稳定数字 id（MD5，避免内置 hash 的随机性）"""
    return 100000 + int(hashlib.md5(text.encode("utf-8")).hexdigest()[:6], 16) % 900000


def add_item(data, ids, content, category, source, today):
    """添加一条语录，自动去重；返回是否新增成功"""
    content = " ".join(str(content).split())  # 清洗空白
    if not (6 <= len(content) <= 300):
        return False
    qid = stable_id(content)
    if qid in ids:
        return False
    ids.add(qid)
    data.append({"id": qid, "content": content, "category": category,
                 "source": source, "date": today, "hot": False})
    return True


def collect_hitokoto(data, ids, today):
    """主源：一言 API，遍历全部 12 个分类"""
    added = 0
    for cat, (category, source) in HITOKOTO_MAP.items():
        for _ in range(PER_SOURCE):
            r = get("https://v1.hitokoto.cn/",
                    params={"c": cat, "encode": "utf-8", "_": random.randint(1, 10**9)})
            if not r:
                continue
            try:
                content = r.json().get("hitokoto", "")
            except Exception:
                continue
            if add_item(data, ids, content, category, source, today):
                added += 1
    print(f"[INFO] 一言接口新增 {added} 条")
    return added


def collect_extra(data, ids, today):
    """补充源：其他段子/笑话接口，失败自动跳过"""
    added = 0
    for cfg in EXTRA_SOURCES:
        r = get(cfg["url"])
        if not r:
            continue
        try:
            payload = r.json()
            raw = payload.get(cfg["key"], [])
            if isinstance(raw, str):
                raw = [raw]
            for text in raw[:PER_SOURCE]:
                if add_item(data, ids, text, cfg["category"], cfg["source"], today):
                    added += 1
        except Exception as e:
            print(f"[WARN] 解析补充源失败 {cfg['url']}: {e}")
    print(f"[INFO] 补充源新增 {added} 条")
    return added


def main():
    data, ids = load_existing(OUTPUT)
    today = date.today().isoformat()

    # 1. 保底种子（仅首次写入）
    seed_added = 0
    for s in SEED:
        if s["id"] not in ids:
            item = dict(s)
            item["date"] = today
            data.append(item)
            ids.add(s["id"])
            seed_added += 1

    # 2. 多源采集
    collect_hitokoto(data, ids, today)
    collect_extra(data, ids, today)

    # 3. 保留最新 200 条
    data = sorted(data, key=lambda x: x.get("date", ""), reverse=True)[:200]

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"[DONE] 保底 {seed_added} 条，总计 {len(data)} 条语录 -> {OUTPUT}")


if __name__ == "__main__":
    main()
