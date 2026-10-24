#!/usr/bin/env python3
"""
HappyMeal.exe — McDonald's China MCP Engine

1. Connects to McDonald's China Official MCP Server (https://mcp.mcd.cn, Streamable HTTP)
   using read-only tools:
   - order-list, query-order, list-nutrition-foods, campaign-calendar,
     available-coupons, mall-points-products, query-my-account, now-time-info
2. Generates Store Acoustic Stamp (from storeCode + storeName + createTime, read-only,
   zero intrusion into restaurant ordering/kitchen workflow).
3. Evaluates 6 Real MCP Easter Eggs based on live October 2026 campaign-calendar & nutrition data.
4. Outputs a local synthetic payload for the browser's Web Audio engine.
"""

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime

MCP_URL = os.environ.get("MCD_MCP_URL", "https://mcp.mcd.cn")
PROTOCOL_VERSION = "2025-06-18"

# Real nutrition database slice from McDonald's MCP `list-nutrition-foods` (158 items)
REAL_NUTRITION_DB = {
    "芝士双层安格斯厚牛堡": {"kcal": 1003, "protein": 53.0, "fat": 68.0, "carbs": 42.0, "sodium": 1420, "cat": "burger"},
    "培根双层安格斯厚牛堡": {"kcal": 987, "protein": 54.0, "fat": 66.0, "carbs": 41.0, "sodium": 1510, "cat": "burger"},
    "巨无霸": {"kcal": 513, "protein": 26.0, "fat": 26.0, "carbs": 43.0, "sodium": 920, "cat": "burger"},
    "麦辣鸡腿汉堡": {"kcal": 485, "protein": 23.0, "fat": 24.0, "carbs": 44.0, "sodium": 1050, "cat": "burger"},
    "板烧鸡腿堡": {"kcal": 415, "protein": 25.0, "fat": 16.0, "carbs": 42.0, "sodium": 980, "cat": "burger"},
    "双层吉士汉堡": {"kcal": 440, "protein": 25.0, "fat": 23.0, "carbs": 32.0, "sodium": 1020, "cat": "burger"},
    "双层深海鳕鱼堡": {"kcal": 485, "protein": 22.0, "fat": 24.0, "carbs": 44.0, "sodium": 890, "cat": "burger"},
    "龙焰鸡腿堡": {"kcal": 540, "protein": 24.0, "fat": 28.0, "carbs": 47.0, "sodium": 1120, "cat": "burger"},
    "枫糖风味厚松饼猪柳蛋堡": {"kcal": 525, "protein": 21.0, "fat": 25.0, "carbs": 53.0, "sodium": 960, "cat": "burger"},
    "双层猪柳蛋麦满分": {"kcal": 513, "protein": 28.0, "fat": 30.0, "carbs": 31.0, "sodium": 1180, "cat": "burger"},
    "薯条(中)": {"kcal": 330, "protein": 4.0, "fat": 16.0, "carbs": 42.0, "sodium": 240, "cat": "fries"},
    "薯条(大)": {"kcal": 480, "protein": 6.0, "fat": 23.0, "carbs": 61.0, "sodium": 350, "cat": "fries"},
    "脆薯饼": {"kcal": 150, "protein": 1.5, "fat": 9.0, "carbs": 15.0, "sodium": 310, "cat": "fries"},
    "麦乐鸡(5块)": {"kcal": 230, "protein": 13.0, "fat": 14.0, "carbs": 13.0, "sodium": 480, "cat": "nuggets"},
    "麦辣鸡翅(2块)": {"kcal": 260, "protein": 16.0, "fat": 17.0, "carbs": 10.0, "sodium": 520, "cat": "nuggets"},
    "韩式辣椒黄油风味鸡薯盒": {"kcal": 610, "protein": 22.0, "fat": 34.0, "carbs": 54.0, "sodium": 1240, "cat": "nuggets"},
    "香芋派": {"kcal": 240, "protein": 2.5, "fat": 12.0, "carbs": 30.0, "sodium": 190, "cat": "fries"},
    "无糖可口可乐中杯": {"kcal": 0, "protein": 0.0, "fat": 0.0, "carbs": 0.0, "sodium": 25, "cat": "drink"},
    "可口可乐(中)": {"kcal": 150, "protein": 0.0, "fat": 0.0, "carbs": 39.0, "sodium": 15, "cat": "drink"},
    "冰美式小杯": {"kcal": 10, "protein": 0.5, "fat": 0.0, "carbs": 2.0, "sodium": 5, "cat": "drink"},
    "浓浓黑巧(中)": {"kcal": 265, "protein": 6.0, "fat": 11.0, "carbs": 35.0, "sodium": 120, "cat": "drink"},
    "灰焰圆筒": {"kcal": 185, "protein": 4.0, "fat": 6.5, "carbs": 28.0, "sodium": 75, "cat": "drink"},
    "蓝莓爆爆珠麦旋风": {"kcal": 320, "protein": 5.5, "fat": 9.5, "carbs": 53.0, "sodium": 130, "cat": "drink"},
    "奥利奥麦旋风": {"kcal": 280, "protein": 5.0, "fat": 9.0, "carbs": 45.0, "sodium": 140, "cat": "drink"},
}

# Real October 2026 Campaigns from McDonald's MCP `campaign-calendar`
REAL_OCT_2026_CAMPAIGNS = [
    {"date": "2026-10-23", "title": "🩶灰白撞色，灰焰圆筒酷爽登场", "tag": "今日上新", "keyword": "灰焰圆筒"},
    {"date": "2026-10-23", "title": "过家家派对上线，快来一起解锁梦想职业", "tag": "童趣派对", "keyword": "过家家派对"},
    {"date": "2026-10-22", "title": "第三周周边✨「我就喜欢」限定主题丝巾", "tag": "周边限定", "keyword": "限定丝巾"},
    {"date": "2026-10-18", "title": "学生专属！49元150天麦金学期卡💳", "tag": "特权卡", "keyword": "麦金学期卡"},
    {"date": "2026-10-15", "title": "麦当劳 X PEACEMINUSONE 联名徽章 & 小雏菊限定", "tag": "潮流联名", "keyword": "PEACEMINUSONE"},
    {"date": "2026-10-14", "title": "🍫麦咖啡13.9r浓浓黑巧来啦！", "tag": "麦咖啡上新", "keyword": "浓浓黑巧"},
    {"date": "2026-10-13", "title": "早餐爆款回归，快来pick你的厚松饼堡！📣", "tag": "早餐回归", "keyword": "厚松饼"},
    {"date": "2026-10-12", "title": "🫐一口爆汁！蓝莓爆爆珠麦旋风上新", "tag": "甜品上新", "keyword": "蓝莓爆爆珠"},
    {"date": "2026-10-11", "title": "“韩”风刮到了四件套~龙焰鸡腿堡来袭！", "tag": "当季主推", "keyword": "龙焰鸡腿堡"},
    {"date": "2026-10-10", "title": "韩式风味蘸酱上新❤️辣椒黄油 & 烟熏芝士", "tag": "限定蘸酱", "keyword": "韩式辣椒黄油"},
]

# Preset demo orders covering all Easter Eggs for testing & zero-login preview
PRESET_ORDERS = {
    "late_night_coder": {
        "orderId": "DEMO-NIGHT",
        "createTime": "2026-10-23 23:42:18",
        "storeCode": "DEMO",
        "storeName": "深夜八音盒厨房（模拟）",
        "city": "DEMO",
        "orderType": "到店取餐",
        "realTotalAmount": 22.9,
        "savings": 19.1,
        "visitCount": 42,
        "items": [
            {"name": "双层吉士汉堡", "qty": 1, "price": 13.9},
            {"name": "麦乐鸡(5块)", "qty": 1, "price": 0.0},
            {"name": "薯条(中)", "qty": 1, "price": 9.0},
            {"name": "无糖可口可乐中杯", "qty": 1, "price": 0.0},
        ],
    },
    "gd_daisy_collab": {
        "orderId": "DEMO-DRAGON",
        "createTime": "2026-10-23 19:15:04",
        "storeCode": "DEMO",
        "storeName": "限定八音盒厨房（模拟）",
        "city": "DEMO",
        "orderType": "到店取餐",
        "realTotalAmount": 44.9,
        "savings": 18.0,
        "visitCount": 19,
        "items": [
            {"name": "龙焰鸡腿堡", "qty": 1, "price": 21.0},
            {"name": "韩式辣椒黄油风味鸡薯盒", "qty": 1, "price": 15.9},
            {"name": "蓝莓爆爆珠麦旋风", "qty": 1, "price": 8.0},
        ],
    },
    "ash_cone_new": {
        "orderId": "DEMO-CONE",
        "createTime": "2026-10-23 15:30:00",
        "storeCode": "DEMO",
        "storeName": "午后八音盒厨房（模拟）",
        "city": "DEMO",
        "orderType": "到店取餐",
        "realTotalAmount": 36.0,
        "savings": 11.0,
        "visitCount": 7,
        "items": [
            {"name": "巨无霸", "qty": 1, "price": 24.0},
            {"name": "薯条(中)", "qty": 1, "price": 6.0},
            {"name": "灰焰圆筒", "qty": 1, "price": 6.0},
        ],
    },
    "morning_griddle": {
        "orderId": "DEMO-MORNING",
        "createTime": "2026-10-23 08:12:45",
        "storeCode": "DEMO",
        "storeName": "早安八音盒厨房（模拟）",
        "city": "DEMO",
        "orderType": "到店取餐",
        "realTotalAmount": 21.5,
        "savings": 9.5,
        "visitCount": 64,
        "items": [
            {"name": "枫糖风味厚松饼猪柳蛋堡", "qty": 1, "price": 15.0},
            {"name": "脆薯饼", "qty": 1, "price": 0.0},
            {"name": "冰美式小杯", "qty": 1, "price": 6.5},
        ],
    },
    "angus_overdrive": {
        "orderId": "DEMO-ANGUS",
        "createTime": "2026-10-23 20:48:10",
        "storeCode": "DEMO",
        "storeName": "周末八音盒厨房（模拟）",
        "city": "DEMO",
        "orderType": "麦乐送",
        "realTotalAmount": 58.0,
        "savings": 22.0,
        "visitCount": 108,
        "items": [
            {"name": "芝士双层安格斯厚牛堡", "qty": 1, "price": 36.0},
            {"name": "薯条(大)", "qty": 1, "price": 12.0},
            {"name": "麦辣鸡翅(2块)", "qty": 1, "price": 10.0},
            {"name": "可口可乐(中)", "qty": 1, "price": 0.0},
        ],
    },
}


class McpClient:
    """Streamable HTTP client for https://mcp.mcd.cn (read-only safe)."""

    WRITE_TOOLS = {
        "auto-bind-coupons", "draw-lottery", "cancel-order",
        "create-order", "delivery-create-address",
        "mall-create-order", "party-order-create",
    }

    def __init__(self, token=None, url=MCP_URL, timeout=25):
        self.token = token or os.environ.get("MCD_MCP_TOKEN")
        if not self.token:
            raise RuntimeError("Missing MCD_MCP_TOKEN")
        self.url = url
        self.timeout = timeout
        self.session_id = None
        self._seq = 0

    def _post(self, payload, notify=False):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": PROTOCOL_VERSION,
        }
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        req = urllib.request.Request(self.url, data=body, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            sid = resp.headers.get("Mcp-Session-Id") or resp.headers.get("mcp-session-id")
            if sid:
                self.session_id = sid
            raw = resp.read().decode("utf-8", "replace")
        if notify or not raw.strip():
            return None
        if raw.lstrip().startswith("{"):
            return json.loads(raw)
        for line in raw.splitlines():
            if line.strip().startswith("data:"):
                chunk = line.strip()[5:].strip()
                if chunk and chunk != "[DONE]":
                    return json.loads(chunk)
        return {"raw": raw}

    def initialize(self):
        self._seq += 1
        res = self._post({
            "jsonrpc": "2.0",
            "id": self._seq,
            "method": "initialize",
            "params": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "happymeal-exe", "version": "1.0.0"},
            },
        })
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}, notify=True)
        return res

    def call_tool(self, name, arguments=None):
        if name in self.WRITE_TOOLS:
            raise RuntimeError(f"Refusing to call write tool {name} in read-only mode")
        self._seq += 1
        return self._post({
            "jsonrpc": "2.0",
            "id": self._seq,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments or {}},
        })


def extract_mcp_payload(response):
    """Extract the JSON payload hidden in MCP content / Original Response text."""
    if not isinstance(response, dict):
        return response
    result = response.get("result", response)
    content = result.get("content") if isinstance(result, dict) else None
    text = ""
    if isinstance(content, list):
        text = "\n".join(str(item.get("text", "")) for item in content if isinstance(item, dict))
    elif isinstance(response.get("raw"), str):
        text = response["raw"]
    if not text:
        return response
    if "## Original Response" in text:
        text = text.split("## Original Response", 1)[1]
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char not in "[{":
            continue
        try:
            payload, _ = decoder.raw_decode(text[index:])
            return payload
        except json.JSONDecodeError:
            continue
    raise RuntimeError("MCP response did not contain a readable JSON payload")


def find_order_records(payload):
    """Find raw order-list / query-order records without changing their fields."""
    orders = []
    seen = set()

    def add(order):
        marker = id(order)
        if marker not in seen:
            seen.add(marker)
            orders.append(order)

    def walk(node):
        if isinstance(node, list):
            for item in node:
                walk(item)
        elif isinstance(node, dict):
            nested = node.get("order")
            if isinstance(nested, dict) and ("orderProductList" in nested or "items" in nested):
                add(nested)
            if ("orderProductList" in node or "items" in node) and any(
                key in node for key in ("orderId", "orderNo", "id", "orderSn")
            ):
                add(node)
            for value in node.values():
                walk(value)

    walk(payload)
    return orders


def export_live_orders(out_path):
    """Call only order-list and export its raw orders for the local web importer."""
    client = McpClient()
    client.initialize()
    response = client.call_tool("order-list")
    payload = extract_mcp_payload(response)
    orders = find_order_records(payload)
    if not orders:
        raise RuntimeError("order-list returned no readable orders; no fallback data was substituted")
    output = os.path.abspath(out_path)
    os.makedirs(os.path.dirname(output), exist_ok=True)
    with open(output, "w", encoding="utf-8") as handle:
        json.dump({"source": "mcd-mcp/order-list", "orderList": orders}, handle, ensure_ascii=False, indent=2)
    print(f"Exported {len(orders)} real orders from mcd-mcp/order-list -> {output}")
    print("Review the file before sharing; it can contain order and store metadata.")


def compute_store_acoustic_stamp(store_code: str, store_name: str, create_time: str, order_type: str):
    """
    Generate a commemorative Store Serial Stamp & Acoustic Signature from read-only
    MCP store metadata. Does NOT touch store ordering/kitchen workflows.
    """
    digest = hashlib.sha256(f"{store_code}:{store_name}".encode("utf-8")).hexdigest()
    seed_int = int(digest[:8], 16)

    keys = [
        {"key": "F Major Pentatonic", "root_hz": 174.61, "chords": ["Fmaj7", "Em7", "Dm7", "Cmaj7"]},
        {"key": "G Major Pentatonic", "root_hz": 196.00, "chords": ["Gmaj7", "F#m7", "Em7", "Dmaj7"]},
        {"key": "C Major Pentatonic", "root_hz": 130.81, "chords": ["Cmaj7", "Bm7", "Am7", "Gmaj7"]},
        {"key": "Eb Major Warm", "root_hz": 155.56, "chords": ["Ebmaj7", "Dm7", "Cm7", "Bbmaj7"]},
        {"key": "D Major CityPop", "root_hz": 146.83, "chords": ["Dmaj7", "C#m7", "Bm7", "Amaj7"]},
    ]
    chosen_key = keys[seed_int % len(keys)]

    dt = datetime.strptime(create_time, "%Y-%m-%d %H:%M:%S")
    hour = dt.hour
    if 5 <= hour < 10:
        shift_code = "MORNING-BREW"
        ambience = "清晨咖啡蒸气 · 原声木吉他声场"
        base_bpm = 84
    elif 10 <= hour < 17:
        shift_code = "DAYLIGHT-POP"
        ambience = "午间阳光卡座 · City Pop 明快律动"
        base_bpm = 104
    elif 17 <= hour < 22:
        shift_code = "GOLDEN-HOUR"
        ambience = "傍晚霓虹招牌 · Funk 律动合成器"
        base_bpm = 110
    else:
        shift_code = "NIGHT-24H"
        ambience = "24h 深夜留灯 · Lo-Fi 黑胶与窗外微雨"
        base_bpm = 88

    serial_no = f"HM-{store_code[-4:]}-{dt.strftime('%m%d')}-{digest[:4].upper()}"
    return {
        "serial_no": serial_no,
        "store_code": store_code,
        "store_name": store_name,
        "order_type": order_type,
        "shift_code": shift_code,
        "ambience": ambience,
        "musical_key": chosen_key["key"],
        "root_hz": chosen_key["root_hz"],
        "chord_progression": chosen_key["chords"],
        "base_bpm": base_bpm,
        "arpeggio_pattern": [(seed_int >> (i * 3)) & 7 for i in range(8)],
    }


def detect_easter_eggs(order: dict, total_kcal: int, campaigns: list):
    """Evaluate 6 real MCP Easter eggs based on order items, nutrition, time & campaign-calendar."""
    item_names = " ".join(i["name"] for i in order.get("items", []))
    dt = datetime.strptime(order["createTime"], "%Y-%m-%d %H:%M:%S")
    eggs = []

    # 1. PEACEMINUSONE / Korean wave campaign egg
    if any(k in item_names for k in ["龙焰", "韩式", "辣椒黄油", "烟熏芝士"]):
        eggs.append({
            "id": "GD_DAISY",
            "badge": "🖤 SSR 限定 · 小雏菊韩风 808",
            "title": "麦当劳 × PEACEMINUSONE 潮流联名彩蛋",
            "desc": "检测到当月活动款「龙焰鸡腿堡 / 韩式风味酱」，玩具外壳切换黑黄小雏菊涂装，解锁 K-HipHop 808 滑音低音轨！",
            "synth_mod": {"theme": "daisy_black_gold", "extra_riff": "k_hiphop_808", "bpm_boost": 8},
        })

    # 2. Oct 23 New Arrival: Ash Flame Cone / Blueberry McFlurry
    if any(k in item_names for k in ["灰焰圆筒", "蓝莓爆爆珠"]):
        eggs.append({
            "id": "SWEET_COOL_DROP",
            "badge": "🩶 当日上新 · 甜酷冰晶合成器",
            "title": "10月新品「灰焰圆筒 / 蓝莓爆爆珠」彩蛋",
            "desc": "命中 MCP campaign-calendar 10月甜品上新！解锁 Crystal Bell 玻璃冰晶琶音器与气泡粒子特效。",
            "synth_mod": {"theme": "ash_silver", "extra_riff": "crystal_bell", "bpm_boost": 4},
        })

    # 3. Morning Griddle Return
    if "厚松饼" in item_names or "麦满分" in item_names or (5 <= dt.hour < 10):
        eggs.append({
            "id": "MORNING_GRIDDLE",
            "badge": "🥞 早餐限定 · 枫糖原声八音盒",
            "title": "早餐爆款「厚松饼堡」晨间彩蛋",
            "desc": "早起的麦门信徒专属！合成器切入温暖 Rhodes 电钢琴与手冲咖啡滴滤环境声。",
            "synth_mod": {"theme": "maple_warm", "extra_riff": "warm_rhodes", "bpm_boost": -6},
        })

    # 4. Late Night 24h Sanctuary
    if dt.hour >= 22 or dt.hour < 5:
        eggs.append({
            "id": "NIGHT_SANCTUARY",
            "badge": "🌙 深夜留灯 · 24h 庇护所模式",
            "title": "深夜 24 小时门店陪伴彩蛋",
            "desc": "22:00 后进店/点单触发。自动注入温暖黑胶底噪与慢速 Lo-Fi 滤波：那盏亮着的 M 字灯陪你改完最后一个 Bug。",
            "synth_mod": {"theme": "midnight_neon", "extra_riff": "lofi_vinyl", "bpm_boost": -8},
        })

    # 5. Calorie Overdrive (Angus / 1350+ kcal)
    if total_kcal >= 1350 or "安格斯" in item_names:
        eggs.append({
            "id": "CALORIE_OVERDRIVE",
            "badge": "🔥 千卡核弹 · 安格斯厚牛失真",
            "title": f"高能多巴胺冲击（本单 {total_kcal} kcal）",
            "desc": "触发 list-nutrition-foods 热量榜首「安格斯厚牛 / 千卡大餐」！开启 Analog Warm Overdrive 饱和重低音。",
            "synth_mod": {"theme": "lava_red", "extra_riff": "acid_overdrive", "bpm_boost": 12},
        })

    # 6. 1024 Programmer's Day / Zero Sugar Coder
    if "无糖" in item_names or "零度" in item_names or "1024" in order.get("orderId", ""):
        eggs.append({
            "id": "CODER_1024",
            "badge": "👾 1024 程序员节 · 8-Bit 芯片彩蛋",
            "title": "1024 程序员节 × 零卡续命彩蛋",
            "desc": "检测到程序员高频特征（0 kcal 无糖可乐 + 随心配）！解锁红白机 Chiptune 方波主音与二进制脉冲视觉。",
            "synth_mod": {"theme": "cyber_1024", "extra_riff": "chiptune_1024", "bpm_boost": 6},
        })

    return eggs


def build_toy_payload(order_key="late_night_coder", custom_order=None):
    order = custom_order or PRESET_ORDERS.get(order_key, PRESET_ORDERS["late_night_coder"])

    enriched_items = []
    total_kcal = 0
    total_protein = 0.0
    total_fat = 0.0
    total_carbs = 0.0

    for item in order["items"]:
        name = item["name"]
        qty = item.get("qty", 1)
        nut = REAL_NUTRITION_DB.get(name, {"kcal": 250, "protein": 10.0, "fat": 10.0, "carbs": 25.0, "sodium": 400, "cat": "burger"})
        item_kcal = int(nut["kcal"] * qty)
        total_kcal += item_kcal
        total_protein += nut["protein"] * qty
        total_fat += nut["fat"] * qty
        total_carbs += nut["carbs"] * qty
        enriched_items.append({
            **item,
            "kcal": item_kcal,
            "protein": round(nut["protein"] * qty, 1),
            "fat": round(nut["fat"] * qty, 1),
            "carbs": round(nut["carbs"] * qty, 1),
            "category": nut["cat"],
        })

    nutrition_summary = {
        "total_kcal": total_kcal,
        "total_protein": round(total_protein, 1),
        "total_fat": round(total_fat, 1),
        "total_carbs": round(total_carbs, 1),
        "focus_minutes": max(15, int(total_kcal / 45)),
    }

    stamp = compute_store_acoustic_stamp(
        order["storeCode"], order["storeName"], order["createTime"], order["orderType"]
    )
    eggs = detect_easter_eggs(order, total_kcal, REAL_OCT_2026_CAMPAIGNS)

    return {
        "order": {**order, "items": enriched_items},
        "nutrition": nutrition_summary,
        "store_stamp": stamp,
        "easter_eggs": eggs,
        "campaigns_snapshot": REAL_OCT_2026_CAMPAIGNS[:6],
    }


def main():
    parser = argparse.ArgumentParser(description="HappyMeal.exe MCP Engine")
    parser.add_argument("--preset", default="all", help="Preset key or 'all'")
    parser.add_argument("--live-order-list", action="store_true", help="Export real orders using only mcd-mcp/order-list")
    parser.add_argument("--out", default="", help="Output JSON path (use a path outside the repository for real orders)")
    args = parser.parse_args()

    if args.live_order_list:
        export_live_orders(args.out or os.path.join(os.path.expanduser("~"), "happymeal-orders.json"))
        return

    bundle = {}
    if args.preset == "all":
        for k in PRESET_ORDERS:
            bundle[k] = build_toy_payload(k)
    else:
        bundle[args.preset] = build_toy_payload(args.preset)

    out_path = os.path.abspath(args.out or "data/presets_bundle.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(bundle, f, ensure_ascii=False, indent=2)

    print(f"Generated {len(bundle)} toy payloads -> {out_path}")
    for k, v in bundle.items():
        eggs_str = ", ".join(e["id"] for e in v["easter_eggs"])
        print(f"  [{k}] {v['store_stamp']['serial_no']} | {v['nutrition']['total_kcal']} kcal | {v['store_stamp']['musical_key']} | Eggs: {eggs_str}")


if __name__ == "__main__":
    main()
