# -*- coding: utf-8 -*-
"""
串子语录采集脚本（多源版 · 内容去重 · 上限10000）
====================================================
采集源（多源）：
  1. 一言 API（v1.hitokoto.cn）—— 12 个分类，主源
  2. 60s API —— 中文段子 / 发病文学 / KFC梗 / 冷笑话（最贴合串子风格），多实例容错
  3. vvhan / qqsuu 段子接口 —— 补充，失败自动跳过
  4. 内置保底种子 20 条
核心修复：
  - 按「内容」去重（不再按 id），彻底消除重复语录
  - 加载旧数据时自动清理历史重复
  - 数据上限 10000 条
  - 使用北京时间（UTC+8），"今日新增"统计准确
依赖：pip install requests
输出：quotes.json
"""
import json
import random
import hashlib
from datetime import datetime, timedelta, timezone
import requests

# ========== 配置区 ==========
OUTPUT = "quotes.json"
MAX_ITEMS = 10000         # 数据保留上限
PER_SOURCE = 8            # 每个分类/源每次请求次数（越小越快）
TIMEOUT = 5               # 单次请求超时（秒）
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                         "AppleWebKit/537.36 Chrome/120.0 Safari/537.36"}

# 北京时间（UTC+8）—— 与前端"今日新增"统计保持一致
def beijing_today():
    return (datetime.now(timezone.utc) + timedelta(hours=8)).date().isoformat()

# 一言分类 -> 本站分类 / 来源平台（12 个分类全覆盖）
HITOKOTO_MAP = {
    "a": ("饭圈", "B站"), "b": ("情感钓鱼", "知乎"), "c": ("情感钓鱼", "知乎"),
    "d": ("经典老串", "贴吧"), "e": ("键政", "知乎"), "f": ("互联网魔怔", "贴吧"),
    "g": ("互联网魔怔", "贴吧"), "h": ("游戏区", "NGA"), "i": ("情感钓鱼", "知乎"),
    "j": ("职场", "贴吧"), "k": ("键政", "微博"), "l": ("电竞圈", "NGA"),
}

# 补充源：60s API 公共实例（已实测可用，失败自动跳过）
# 每个实例都试一遍，任一可用即可；数据字段在 data.<key> 中
SIXTY_BASES = [
    "https://60s.okbaike.com",       # 实测可用
    "https://api.cczo.cc/60s",       # 实测可用（备用）
    "https://60s.viki.moe",          # 官方域名（GitHub 服务器可能可用）
]
# 端点 -> (本站分类, 来源标识, 数据字段名)
SIXTY_ENDPOINTS = [
    ("duanzi",   "互联网魔怔", "贴吧", "duanzi"),    # 网络段子
    ("fabing",   "互联网魔怔", "微博", "saying"),    # 发病文学（魔怔发言，最贴合串子风格）
    ("kfc",      "经典老串",   "微博", "kfc"),       # 疯狂星期四热梗
    ("dad-joke", "互联网魔怔", "抖音", "content"),   # 冷笑话
]

# 旧补充源（保留兼容，失败自动跳过）
EXTRA_SOURCES = [
    {"url": "https://api.vvhan.com/api/duanzi", "category": "互联网魔怔", "source": "段子站", "key": "data"},
    {"url": "https://api.qqsuu.cn/api/dm-joke", "category": "互联网魔怔", "source": "笑话站", "key": "content"},
]

# 保底种子 20 条
SEED = [
    "这波团战打完，我直接把显示器砸了，然后发现是梦境。",
    "打野不来 gank 我就挂机，这是规矩，懂？",
    "辅助不插眼？那我 AD 为什么不 A 兵，reply 一下。",
    "我家哥哥唱歌虽然跑调，但那叫艺术加工，你懂不懂！",
    "你说我家哥哥不好看？你眼睛是不是捐了？",
    "控评！控评！把不好的评论都点举报，冲鸭！",
    "这个需求上午提下午要，很合理吧？又不是做火箭。",
    "工资三千，操心三亿的项目，格局打开了。",
    "弹性工作制嘛，就是弹性地加班，很柔性。",
    "典！太典了！这帖子典中典，绷不住了。",
    "我不说话，我就静静地看着你表演。",
    "你急了，你急了，你开始急了，哈哈哈哈。",
    "我先声明我是理性讨论，但你这个说法我不认同。",
    "键盘在手，天下我有，指点江山挥斥方遒。",
    "在吗？在吗？在吗？我有个东西给你看，保证刺激。",
    "其实我一直在默默关注你，从你第一条动态开始。",
    "这游戏平衡性做得真好，我删游戏了，祝大家玩得开心。",
    "氪金？这辈子都不可能氪金的，除非真的很划算。",
    "前排占座，楼下复读，一楼楼上，二楼楼下。",
    "马克一下，收藏了，以后再看，大概率不会看。",
]
# 种子分类/来源按索引分配
SEED_META = [
    ("电竞圈", "贴吧", True), ("电竞圈", "NGA", False), ("电竞圈", "微博", False),
    ("饭圈", "微博", True), ("饭圈", "抖音", False), ("饭圈", "微博", False),
    ("职场", "贴吧", True), ("职场", "NGA", False), ("职场", "贴吧", False),
    ("互联网魔怔", "贴吧", True), ("互联网魔怔", "抖音", False), ("互联网魔怔", "NGA", True),
    ("键政", "微博", False), ("键政", "贴吧", False),
    ("情感钓鱼", "贴吧", True), ("情感钓鱼", "抖音", False),
    ("游戏区", "NGA", True), ("游戏区", "贴吧", False),
    ("经典老串", "贴吧", True), ("经典老串", "NGA", False),
]


def get(url, params=None):
    """统一 GET 请求，失败返回 None"""
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        return r
    except Exception as e:
        print(f"[WARN] 请求失败 {url}: {e}")
        return None


def normalize(text):
    """标准化文本：压缩空白，用于内容比对和去重"""
    return " ".join(str(text).split())


def content_key(text):
    """内容指纹（MD5）—— 去重的唯一依据，与 id 无关"""
    return hashlib.md5(normalize(text).encode("utf-8")).hexdigest()


def stable_id(text):
    """基于内容生成稳定数字 id"""
    return 100000 + int(content_key(text)[:6], 16) % 900000


def load_existing(path):
    """
    读取已有数据，按内容去重（保留首次出现的），返回 (清理后的列表, 内容指纹集合)
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            return [], set()
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return [], set()

    seen = set()
    cleaned = []
    removed = 0
    for item in data:
        content = item.get("content", "")
        key = content_key(content)
        if key in seen:
            removed += 1
            continue  # 内容重复，丢弃
        seen.add(key)
        cleaned.append(item)
    if removed:
        print(f"[INFO] 清理历史重复 {removed} 条")
    return cleaned, seen


def add_item(data, keys, content, category, source, today):
    """添加一条语录，按内容去重；返回是否新增成功"""
    content = normalize(content)
    if not (6 <= len(content) <= 300):
        return False
    key = content_key(content)
    if key in keys:
        return False
    keys.add(key)
    data.append({"id": stable_id(content), "content": content, "category": category,
                 "source": source, "date": today, "hot": False})
    return True


def collect_hitokoto(data, keys, today):
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
            if add_item(data, keys, content, category, source, today):
                added += 1
    print(f"[INFO] 一言接口新增 {added} 条")
    return added


def collect_60s(data, keys, today):
    """补充源：60s API（段子/发病文学/KFC梗/冷笑话），多实例容错"""
    added = 0
    for base in SIXTY_BASES:
        for endpoint, category, source, field in SIXTY_ENDPOINTS:
            url = f"{base}/v2/{endpoint}"
            for _ in range(PER_SOURCE):
                r = get(url, params={"_": random.randint(1, 10**9)})
                if not r:
                    break  # 该实例不通，换下一个
                try:
                    payload = r.json()
                    if payload.get("code") != 200:
                        break
                    text = payload.get("data", {}).get(field, "")
                except Exception:
                    break
                if add_item(data, keys, text, category, source, today):
                    added += 1
    print(f"[INFO] 60s系列新增 {added} 条")
    return added


def collect_extra(data, keys, today):
    """旧补充源：其他段子/笑话接口，失败自动跳过"""
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
                if add_item(data, keys, text, cfg["category"], cfg["source"], today):
                    added += 1
        except Exception as e:
            print(f"[WARN] 解析补充源失败 {cfg['url']}: {e}")
    print(f"[INFO] 补充源新增 {added} 条")
    return added


def main():
    today = beijing_today()
    data, keys = load_existing(OUTPUT)

    # 1. 保底种子（同样按内容去重，避免与采集内容重复）
    seed_added = 0
    for text, (cat, src, hot) in zip(SEED, SEED_META):
        key = content_key(text)
        if key in keys:
            continue
        keys.add(key)
        data.append({"id": stable_id(text), "content": text, "category": cat,
                     "source": src, "date": today, "hot": hot})
        seed_added += 1

    # 2. 多源采集
    collect_hitokoto(data, keys, today)
    collect_60s(data, keys, today)      # 段子/发病文学/KFC梗/冷笑话
    collect_extra(data, keys, today)

    # 3. 按日期排序，保留最新 MAX_ITEMS 条
    data = sorted(data, key=lambda x: x.get("date", ""), reverse=True)[:MAX_ITEMS]

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # 最终校验：确认无重复
    assert len(data) == len({content_key(x["content"]) for x in data}), "存在重复内容！"
    print(f"[DONE] 种子 {seed_added} 条，总计 {len(data)} 条（上限 {MAX_ITEMS}），无重复 -> {OUTPUT}")


if __name__ == "__main__":
    main()
