"""Kiểm tra nhanh một bản deploy — dùng cho CP5.

Chạy được với cả bản ở máy và bản trên cloud:

    python scripts/smoke_check.py                          # mặc định localhost:8000
    python scripts/smoke_check.py https://abc.up.railway.app
    python scripts/smoke_check.py --round-robin            # kiểm tra 3 instance 8000/8001/8002

Khi kiểm tra bản cloud, đặt `DEPLOY_API_KEY` trong `.env` (không commit file đó).
Script chỉ in ra mã trạng thái và phần thân response — không in giá trị khóa.
"""

from __future__ import annotations

import os
import sys

import httpx
from dotenv import load_dotenv

# Console Windows mặc định là cp1252 → in tiếng Việt sẽ lỗi. Ép UTF-8.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

load_dotenv()

ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
ROUND_ROBIN = "--round-robin" in sys.argv
BASE_URL = (ARGS[0] if ARGS else "http://localhost:8000").rstrip("/")

# Ưu tiên khóa của bản deploy; chưa set thì dùng khóa local.
API_KEY = os.environ.get("DEPLOY_API_KEY") or os.environ.get("AGENT_API_KEY", "")


def show(label: str, response: httpx.Response) -> None:
    body = " ".join(response.text.split())[:120]
    print(f"  {label:<44} {response.status_code:>3}  {body}")


def check_basic(client: httpx.Client) -> None:
    print(f"\n== Kiểm tra cơ bản: {BASE_URL} ==")
    show("GET  /health   (liveness)", client.get(f"{BASE_URL}/health"))
    show("GET  /ready    (readiness)", client.get(f"{BASE_URL}/ready"))
    show(
        "POST /ask      (không có API key)",
        client.post(f"{BASE_URL}/ask", json={"question": "Hello"}),
    )

    headers = {"X-API-Key": API_KEY, "X-User-Id": "sv-smoke"}
    response = client.post(
        f"{BASE_URL}/ask", json={"question": "Docker là gì?"}, headers=headers
    )
    show("POST /ask      (có API key)", response)
    if response.status_code == 200:
        data = response.json()
        print(
            f"      → history_length={data['history_length']} "
            f"cost_usd={data['cost_usd']} tokens={data['tokens']}"
        )

    codes = [
        client.post(
            f"{BASE_URL}/ask",
            json={"question": f"request {i}"},
            headers={"X-API-Key": API_KEY, "X-User-Id": "sv-ratelimit"},
        ).status_code
        for i in range(15)
    ]
    ok = codes.count(200)
    limited = codes.count(429)
    print(f"  {'POST /ask × 15 (rate limit)':<44} {codes}")
    print(f"      → {ok} request qua, {limited} request bị 429")


def check_round_robin() -> None:
    """Gọi lần lượt 3 container: lịch sử phải TĂNG DẦN nếu state nằm ở Redis."""
    print("\n== Kiểm tra stateless: 3 instance 8000 / 8001 / 8002 ==")
    headers = {"X-API-Key": API_KEY, "X-User-Id": "sv-roundrobin"}
    with httpx.Client(timeout=30) as client:
        for i, port in enumerate([8000, 8001, 8002, 8000, 8001, 8002], start=1):
            response = client.post(
                f"http://localhost:{port}/ask",
                json={"question": f"lượt {i}"},
                headers=headers,
            )
            if response.status_code != 200:
                print(f"  port {port}: {response.status_code} — bỏ qua")
                continue
            print(
                f"  lượt {i} → container cổng {port}: "
                f"history_length = {response.json()['history_length']}"
            )


def main() -> None:
    if not API_KEY:
        print("CẢNH BÁO: chưa có AGENT_API_KEY/DEPLOY_API_KEY trong môi trường.")
    with httpx.Client(timeout=30) as client:
        check_basic(client)
    if ROUND_ROBIN:
        check_round_robin()


if __name__ == "__main__":
    main()
