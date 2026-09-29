# Thông Tin Deploy — Checkpoint 5

> Đã deploy thật lên Railway và đã kiểm tra từ ngoài Internet (kết quả ở
> "Phần B"). Lần deploy đầu tiên service báo Online nhưng chưa dùng được vì
> thiếu biến `REDIS_URL` — xem "Ghi Chú Về Lần Deploy Đầu Tiên" ở cuối file.
>
> **Chỉ ghi TÊN biến môi trường, tuyệt đối không dán giá trị API key vào đây.**
> Repo này công khai — dán khóa vào là mất khóa.

## Thông Tin Học Viên

| Mục         | Nội dung                                                                                       |
| ----------- | ---------------------------------------------------------------------------------------------- |
| Họ và tên   | Phan Duy Thành                                                                                 |
| Mã học viên | 2A202602930                                                                                    |
| Repo        | https://github.com/thanhpd123/K4-L3B-DAY12-PhanDuyThanh-2A202602930-CloudServicesAndDeployment |

## Service

| Mục         | Nội dung                                                                           |
| ----------- | ---------------------------------------------------------------------------------- |
| Public URL  | https://k4-l3b-day12-phanduythanh-2a202602930-cloudservi-production.up.railway.app |
| Platform    | Railway — build từ `Dockerfile` (multi-stage), kèm Redis add-on                    |
| Ngày deploy | 2026-09-29                                                                         |

## Biến Môi Trường Đã Set Trên Cloud

Ghi tên biến và **nguồn giá trị**, không ghi giá trị:

| Biến                    | Đã set | Ghi chú                                                                    |
| ----------------------- | ------ | -------------------------------------------------------------------------- |
| `PORT`                  | ✅      | Railway tự gán, app đọc qua `${PORT:-8000}` trong Dockerfile               |
| `AGENT_API_KEY`         | ✅      | đặt trong dashboard (hoặc `railway variables --set`), không nằm trong repo |
| `REDIS_URL`             | ✅      | Variable Reference `${{Redis.REDIS_URL}}` — nối động sang service Redis    |
| `RATE_LIMIT_PER_MINUTE` | ✅      | 10                                                                         |
| `MONTHLY_BUDGET_USD`    | ✅      | 10.0                                                                       |
| `LOG_LEVEL`             | ✅      | INFO                                                                       |

## Lệnh Kiểm Tra

Thay `<URL>` bằng Public URL ở trên:

```bash
# 1. Liveness — mong đợi 200 {"status":"ok"}
curl -i <URL>/health

# 2. Readiness — mong đợi 200 {"status":"ready"} (đã nối được Redis)
curl -i <URL>/ready

# 3. Không có API key — mong đợi 401
curl -i -X POST <URL>/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"Hello"}'

# 4. Có API key — mong đợi 200 kèm câu trả lời
curl -i -X POST <URL>/ask \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $AGENT_API_KEY" \
  -H "X-User-Id: sv-test" \
  -d '{"question":"Deploy là gì?"}'

# 5. Rate limit — gọi 15 lần, những lần cuối phải trả 429
for i in $(seq 1 15); do
  curl -s -o /dev/null -w "%{http_code} " -X POST <URL>/ask \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $AGENT_API_KEY" \
    -H "X-User-Id: sv-test" \
    -d '{"question":"test"}'
done; echo
```

Hoặc dùng script có sẵn trong repo (chạy được với cả URL cloud):

```bash
python scripts/smoke_check.py https://<URL-that>
```

## Kết Quả Chạy Thật

### Phần A — Bản chạy ở máy: `docker compose up -d --scale agent=3`

Ba container agent cùng nối vào một Redis, cả ba đều `healthy`:

```
agent|Up 3 minutes (healthy)|0.0.0.0:8002->8000/tcp
agent|Up 3 minutes (healthy)|0.0.0.0:8001->8000/tcp
agent|Up 3 minutes (healthy)|0.0.0.0:8000->8000/tcp
redis|Up 26 minutes (healthy)|0.0.0.0:6379->6379/tcp
```

Kết quả `python scripts/smoke_check.py --round-robin`:

```
== Kiểm tra cơ bản: http://localhost:8000 ==
  GET  /health   (liveness)                    200  {"status":"ok","service":"day12-agent","version":"1.0.0"}
  GET  /ready    (readiness)                   200  {"status":"ready","redis":true}
  POST /ask      (không có API key)            401  {"detail":"invalid or missing API key"}
  POST /ask      (có API key)                  200  {"answer":"Ngắn gọn: Docker là gì phụ thuộc vào ba yếu tố ...
      → history_length=2 cost_usd=3.465e-05 tokens={'in': 43, 'out': 47}
  POST /ask × 15 (rate limit)                  [200, 200, 200, 200, 200, 200, 200, 200, 200, 200, 429, 429, 429, 429, 429]
      → 10 request qua, 5 request bị 429

== Kiểm tra stateless: 3 instance 8000 / 8001 / 8002 ==
  lượt 1 → container cổng 8000: history_length = 12
  lượt 2 → container cổng 8001: history_length = 14
  lượt 3 → container cổng 8002: history_length = 16
  lượt 4 → container cổng 8000: history_length = 18
  lượt 5 → container cổng 8001: history_length = 20
  lượt 6 → container cổng 8002: history_length = 20
```

Hai điều đáng chú ý trong bảng trên:

- `history_length` tăng đều 2 đơn vị mỗi lượt **dù request rơi vào container
  khác nhau** → lịch sử thật sự nằm ở Redis, không nằm trong RAM của instance.
- Lượt 6 vẫn là 20 chứ không phải 22 → `ltrim` đã cắt đúng ở
  `HISTORY_MAX_MESSAGES = 20`.

Một dòng log JSON thật lấy từ container (`docker compose logs agent`):

```
{"event": "ask_completed", "level": "info", "timestamp": "2026-09-29T04:33:20.435960+00:00", "user_id": "sv-roundrobin", "tokens_in": 490, "tokens_out": 46, "cost_usd": 0.0001011}
```

### Phần B — Bản trên cloud (Railway)

`https://k4-l3b-day12-phanduythanh-2a202602930-cloudservi-production.up.railway.app`

Chạy `python scripts/smoke_check.py https://k4-l3b-day12-phanduythanh-2a202602930-cloudservi-production.up.railway.app`:

```
GET  /health   (liveness)         200  {"status":"ok","service":"day12-agent","version":"1.0.0"}
GET  /ready    (readiness)        200  {"status":"ready","redis":true}
POST /ask      (không có API key) 401  {"detail":"invalid or missing API key"}
POST /ask      (có API key)       200  {"answer":"Ngắn gọn: Docker là gì phụ thuộc vào ba yếu tố ...",
      → history_length=0 cost_usd=2.265e-05 tokens={'in': 3, 'out': 37}
POST /ask × 15 (rate limit)       [200, 200, 200, 200, 200, 200, 200, 200, 200, 200, 429, 429, 429, 429, 429]
      → 10 request qua, 5 request bị 429
```

`pytest tests/test_cp5.py -v` → **9 passed, 4 skipped** (4 test bỏ qua là nhánh
`LOCAL_FALLBACK`, đúng như mong đợi khi đã deploy thật).

## Ghi Chú Về Lần Deploy Đầu Tiên

Lần deploy đầu tiên trông thành công — card service báo **Online** — nhưng thực
ra chưa dùng được:

```
GET  /health  → 200  ← qua, vì /health cố tình KHÔNG kiểm tra dependency
GET  /ready   → 503  {"status":"not ready","redis":false}
POST /ask     → 401 (không key)  /  500 (có key)
```

Nguyên nhân: biến `REDIS_URL` chưa được gắn vào service agent, nên app rơi về
mặc định `redis://localhost:6379/0` — trong container, `localhost` là chính
container đó, không phải service Redis. Cách sửa: thêm Variable Reference
`REDIS_URL=${{Redis.REDIS_URL}}` trong tab Variables của service agent.

## Ảnh Chụp Màn Hình

Đặt ảnh trong thư mục `screenshots/`:

| File                           | Nội dung                                                                                                         |
| ------------------------------ | ---------------------------------------------------------------------------------------------------------------- |
| `screenshots/dashboard.png`    | Canvas Railway: card service agent **Online** + card **Redis** Online                                            |
| `screenshots/health.png`       | Kết quả gọi `/health` trên trình duyệt (`{"status":"ok","service":"day12-agent","version":"1.0.0"}`)             |
| `screenshots/build-logs.png`   | Tab **Build Logs**: `pip install ... cached`, `COPY requirements.txt ... cached` — chứng minh thứ tự layer ở CP2 |
| `screenshots/deploy-logs.png`  | Tab **Deploy Logs**: log JSON một dòng của CP1, kèm các mã 200/401                                               |
| `screenshots/network-logs.png` | Tab **Network Logs**: bảng HTTP có `200` cho `/health`, `/ready` và `429` khi vượt rate limit                    |

---

## Nếu Dùng Phương Án Dự Phòng

Không đăng ký được tài khoản cloud? Vẫn nộp được bài, nhưng CP5 tối đa 60% điểm:

1. Đặt `LOCAL_FALLBACK=true` trong `.env`
2. Chạy `docker compose up -d` rồi kiểm tra `docker compose ps`
3. Chụp màn hình vào `screenshots/`
4. Chạy `pytest tests/test_cp5.py -v` — bộ test sẽ tự chuyển sang kiểm tra
   `http://localhost:8000`
5. Ghi rõ lý do không deploy được vào phần dưới đây:

```
(chưa dùng phương án dự phòng)
```
