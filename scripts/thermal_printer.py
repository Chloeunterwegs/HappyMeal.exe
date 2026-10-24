#!/usr/bin/env python3
"""
HappyMeal.exe Thermal Receipt Utilities (experimental)

Provides:
1. Standard ESC/POS (58mm / 80mm) binary command generation for compatible printers.
2. A local HTTP webhook (`POST /api/v1/thermal-print`) that generates ESC/POS bytes.
   It does NOT communicate with a physical printer and never reports that printing occurred.
3. Standalone CLI generation of a sample ESC/POS `.bin` file.

Printer code pages, Bluetooth/USB transport, and physical output require per-model validation.
"""

import argparse
import hashlib
import json
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer


def generate_escpos_bytes(ticket: dict) -> bytes:
    """
    Generate standard ESC/POS byte stream for 58mm/80mm thermal printers:
    - ESC @ (Initialize)
    - Center align header + store serial stamp
    - Order metadata, mood and one-line message
    - Native ESC/POS GS ( k QR Code command for opening the shared song page
    - GS V (Feed and cut paper)
    """
    buf = bytearray()
    # Initialize printer
    buf += b"\x1b\x40"
    # Center align
    buf += b"\x1b\x61\x01"
    # Double height/width bold title
    buf += b"\x1b\x21\x30"
    buf += "M · 开心乐园餐音乐单\n".encode("gb18030", errors="replace")
    buf += b"\x1b\x21\x00"
    buf += "HAPPYMEAL.EXE MUSIC RECEIPT\n".encode("ascii")
    buf += ("-" * 32 + "\n").encode("ascii")

    # Left align metadata
    buf += b"\x1b\x61\x00"
    lines = [
        f"门店: {ticket.get('store_name', '八音盒厨房（模拟）')} (#{ticket.get('store_code', 'DEMO')})",
        f"单号: {ticket.get('order_no', 'DEMO-THERMAL')}",
        f"时间: {ticket.get('time', datetime.now().strftime('%Y-%m-%d %H:%M'))}",
        f"心情: {ticket.get('mood_label', '有点 Down ★★★★☆')}",
        f"调性: {ticket.get('musical_key', 'A Minor Healing Ballad')}",
        "-" * 32,
        "【这顿饭的歌】",
        f" ● 汉堡: {ticket.get('burger', '双层吉士汉堡')}",
        f" ● 小食: {ticket.get('sides', '中薯条')}",
        f" ● 饮品: {ticket.get('drinks', '无糖可乐')}",
        f" ● 模拟能量: {ticket.get('kcal', 770)} kcal",
        "-" * 32,
        ticket.get("message", ticket.get("lyrics", "小时候考满分才有的玩具，今晚这顿随心配替你补上。")),
        "-" * 32,
    ]
    for line in lines:
        buf += (line + "\n").encode("gb18030", errors="replace")

    # Center align for QR code
    buf += b"\x1b\x61\x01"
    qr_payload = ticket.get("share_url", ticket.get("song_download_url", "https://chloeunterwegs.github.io/HappyMeal.exe/web/index.html#s=HMDEMO~double_cheese~down~4"))
    qr_bytes = qr_payload.encode("utf-8")
    store_len = len(qr_bytes) + 3
    pL = store_len & 0xFF
    pH = (store_len >> 8) & 0xFF

    # GS ( k — QR Code Model 2, size 6, error correction M
    buf += b"\x1d\x28\x6b\x04\x00\x31\x41\x32\x00"
    buf += b"\x1d\x28\x6b\x03\x00\x31\x43\x06"
    buf += b"\x1d\x28\x6b\x03\x00\x31\x45\x31"
    buf += bytes([0x1D, 0x28, 0x6B, pL, pH, 0x31, 0x50, 0x30]) + qr_bytes
    buf += b"\x1d\x28\x6b\x03\x00\x31\x51\x30"

    buf += "\n扫码打开分享页，可试听或下载\n".encode("gb18030", errors="replace")
    buf += "Ba-Da-Ba-Ba-Ba · 麦门永存\n\n\n".encode("gb18030", errors="replace")
    # Cut paper
    buf += b"\x1d\x56\x42\x00"
    return bytes(buf)


class ThermalPrintHandler(BaseHTTPRequestHandler):
    """Webhook endpoint `POST /api/v1/thermal-print` for store POS or local agent."""

    def _set_cors(self, status=200, content_type="application/json"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_OPTIONS(self):
        self._set_cors(200)

    def do_POST(self):
        if self.path != "/api/v1/thermal-print":
            self._set_cors(404)
            self.wfile.write(b'{"error":"not_found"}')
            return
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        escpos_raw = generate_escpos_bytes(body)
        digest = hashlib.sha256(escpos_raw).hexdigest()[:12].upper()
        resp = {
            "status": "generated",
            "printing_performed": False,
            "message": "ESC/POS bytes generated; no physical printer was contacted.",
            "printer_protocol": "ESC/POS 80mm/58mm",
            "bytes_length": len(escpos_raw),
            "ticket_hash": f"POS-{digest}",
            "escpos_hex_preview": escpos_raw[:64].hex(),
        }
        self._set_cors(200)
        self.wfile.write(json.dumps(resp, ensure_ascii=False).encode("utf-8"))


def main():
    parser = argparse.ArgumentParser(description="HappyMeal.exe ESC/POS Generator (experimental)")
    parser.add_argument("--serve", action="store_true", help="Run local ESC/POS generation webhook on port 10240")
    parser.add_argument("--out-bin", default="", help="Write sample ESC/POS binary to path")
    args = parser.parse_args()

    sample_ticket = {
        "store_name": "深夜八音盒厨房（模拟）",
        "store_code": "DEMO",
        "order_no": "DEMO-THERMAL",
        "mood_label": "🌧️ 有点 Down (★★★★☆)",
        "musical_key": "A Minor · 柔音钢琴",
        "burger": "双层吉士汉堡",
        "sides": "中薯条 + 麦乐鸡",
        "drinks": "无糖可口可乐",
        "kcal": 1000,
        "lyrics": "小时候考满分才有的开心乐园餐玩具，今晚这顿 13.9 的随心配替你补上。",
        "share_url": "https://chloeunterwegs.github.io/HappyMeal.exe/web/index.html#s=HMDEMO~double_cheese~down~4",
    }

    if args.out_bin:
        raw = generate_escpos_bytes(sample_ticket)
        with open(args.out_bin, "wb") as f:
            f.write(raw)
        print(f"ESC/POS binary written: {args.out_bin} ({len(raw)} bytes)")
        return

    if args.serve:
        server = HTTPServer(("127.0.0.1", 10240), ThermalPrintHandler)
        print("Thermal Print Webhook listening on http://127.0.0.1:10240/api/v1/thermal-print")
        server.serve_forever()
    else:
        raw = generate_escpos_bytes(sample_ticket)
        print(f"ESC/POS test OK: {len(raw)} bytes generated (header hex: {raw[:24].hex()})")


if __name__ == "__main__":
    main()
