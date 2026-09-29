Họ và tên: `Phan Duy Thành`
MSSV: `2A202602930`
Link nộp: `https://github.com/thanhpd123/K4-L3B-DAY12-PhanDuyThanh-2A202602930-CloudServicesAndDeployment`
Ngày: 29/09/2026

---

# Báo cáo Lab Day 12 — Hạ tầng Cloud & Deployment

## 1. Tóm tắt

Bài lab bắt đầu từ một agent FastAPI chạy được ở `localhost:8000` và yêu cầu
đưa nó tới trạng thái "chạy được thật": có địa chỉ công khai, biết ai đang gọi,
không để người lạ đốt hết tiền, và không rớt request mỗi lần deploy bản mới.

Kết quả hiện tại: **CP1–CP4 hoàn thành và đã kiểm tra xanh**, code đã chạy thật
trong Docker với 3 instance song song. CP5 (địa chỉ công khai trên cloud) là
phần duy nhất còn phụ thuộc vào tài khoản cloud, sẽ được điền URL sau khi deploy.

| Checkpoint | Nội dung                                             | Trạng thái                                     |
| ---------- | ---------------------------------------------------- | ---------------------------------------------- |
| CP1        | 12-Factor config, health check, log JSON             | ✅ 13/13 test xanh                              |
| CP2        | Dockerfile multi-stage, bảo mật image, compose stack | ✅ 16/16 test, image thật: 1.19 GB → **184 MB** |
| CP3        | API key, rate limit, cost guard                      | ✅ 27/27 test xanh                              |
| CP4        | Stateless, readiness, graceful shutdown              | ✅ 22/22 test xanh                              |
| CP5        | Deploy lên cloud                                     | ⏳ Chờ điền Public URL                          |

Tổng thể bộ test: `55 failed` lúc đầu → **`68 passed`, chỉ còn CP5 và phần bonus
chưa đạt** (đúng như thiết kế: hai phần đó cần tài khoản cloud và GitHub Actions).

---

## 2. Bức tranh tổng thể

Điểm chung của cả bài là một câu hỏi: *cái gì giống nhau ở mọi môi trường, và
cái gì khác nhau?* Code thì giống nhau — nên nó nằm trong image. Cấu hình, khóa
API, địa chỉ Redis thì khác nhau — nên chúng nằm ở biến môi trường. Cùng một
image chạy ở laptop và trên cloud, chỉ khác mấy biến môi trường được truyền vào.

```
        Người dùng
            │  POST /ask  (kèm X-API-Key, X-User-Id)
            ▼
   ┌──────────────────────┐
   │  FastAPI (container) │
   │                      │
   │  1. verify_api_key   │── sai/thiếu key ──► 401
   │  2. rate limiter     │── quá nhanh ──────► 429
   │  3. cost guard       │── hết ngân sách ──► 402
   │  4. gọi LLM          │
   │  5. ghi log JSON     │
   └──────────┬───────────┘
              │  state dùng chung
              ▼
   ┌──────────────────────┐
   │  Redis               │  lịch sử hội thoại · đếm request · chi phí
   └──────────────────────┘
```

Điểm mấu chốt: **container không giữ gì trong RAM**. Muốn scale lên 3 instance
thì cả 3 phải nhìn vào cùng một Redis, nếu không agent sẽ "mất trí nhớ" ngẫu
nhiên tuỳ request rơi vào container nào.

---

## 3. Từng checkpoint

### CP1 — Tách cấu hình khỏi code, log cho máy đọc

Ba việc, và việc nào cũng có một lý do cụ thể:

**`app/config.py`** khai báo 6 trường, trong đó `agent_api_key` là trường duy
nhất **không có giá trị mặc định**. Ban đầu em thấy hơi khó chịu vì app chết
ngay khi thiếu biến — nhưng đó chính là mục đích. Nếu đặt mặc định
`"changeme"`, app vẫn khởi động trên cloud khi mình quên set secret, vẫn trả
lời request, và mình chỉ phát hiện ra khi nhìn hóa đơn. Còn không có mặc định
thì lỗi hiện ra ngay lúc deploy, khi mình còn đang ngồi trước màn hình.

**`app/logging_utils.py`** in ra **một dòng JSON** cho mỗi sự kiện. Không dùng
`indent`, và phải có `ensure_ascii=False` để tiếng Việt không thành ký tự lạ.
Lý do rất thực tế: cloud gom log theo dòng, một JSON xuống dòng là một bản ghi
bị vỡ thành nhiều mảnh vô nghĩa.

**`/health`** chỉ trả lời một câu: process này có cần restart không? Nên nó
**không được** chạm vào Redis. Nếu để nó kiểm tra Redis, Redis nấc một cái là
orchestrator tưởng cả cụm container hỏng và restart tất cả — biến một sự cố
nhỏ thành sự cố lớn. Bài kiểm tra còn kiểm tra điều này bằng cách soi chữ ký
hàm: `health()` không được nhận tham số `Depends` nào.

### CP2 — Docker: image nhỏ, chạy an toàn

Dockerfile gốc có 6 vấn đề, và bản mới sửa từng cái:

| Vấn đề ở bản gốc                 | Cách sửa                                                        | Vì sao quan trọng                                     |
| -------------------------------- | --------------------------------------------------------------- | ----------------------------------------------------- |
| Một stage, mang theo cả compiler | Hai stage: `builder` cài dependency, `runtime` chỉ nhận kết quả | Compiler chỉ cần lúc build, không cần lúc chạy        |
| Base image `python:3.11` đầy đủ  | `python:3.11-slim`                                              | Bớt được hàng trăm MB không dùng tới                  |
| `COPY . .` trước `pip install`   | `COPY requirements.txt` → `pip install` → mới copy code         | Sửa một dòng code không phải cài lại toàn bộ thư viện |
| Chạy bằng root                   | Tạo `appuser` (uid 10001) và `USER appuser`                     | Có thoát được khỏi app cũng chỉ là user thường        |
| Không có healthcheck             | `HEALTHCHECK` gọi `/health`                                     | Docker biết container còn phục vụ được hay không      |
| Cổng cố định 8000                | `--port ${PORT:-8000}`                                          | Railway/Render tự gán cổng, cứng 8000 là chết         |

Kết quả đo thật: image multi-stage **184 MB** (yêu cầu của lab là dưới 500 MB).
Bản một-stage gốc nặng **1.19 GB** — multi-stage giảm được gần 6.5 lần mà
không phải đánh đổi gì về chức năng.

Hai chi tiết nhỏ nhưng đáng nhớ:

- `.dockerignore` phải có `.env`, `__pycache__`, `.git`, `.venv` — bỏ sót `.env`
  nghĩa là khóa API bị nướng thẳng vào image gửi lên registry.
- Trong `docker-compose.yml`, `REDIS_URL` phải là `redis://redis:6379/0` chứ
  không phải `localhost`. Trong mạng của compose, tên service chính là hostname;
  `localhost` bên trong container là chính container đó. Đây là lỗi kinh điển
  của người mới dùng compose.

### CP3 — Ba lớp bảo vệ, ba câu hỏi khác nhau

| Lớp            | Câu hỏi                         | Mã lỗi |
| -------------- | ------------------------------- | ------ |
| Authentication | Bạn là ai?                      | 401    |
| Rate limiting  | Bạn gọi có quá nhanh không?     | 429    |
| Cost guard     | Bạn đã tiêu hết ngân sách chưa? | 402    |

**So sánh khóa bằng `secrets.compare_digest`.** Toán tử `==` dừng ngay tại ký tự
đầu tiên khác nhau, nên thời gian phản hồi rò rỉ thông tin: đoán đúng ký tự đầu
thì phản hồi chậm hơn một chút. Đo đủ nhiều lần là dò ra khóa từng ký tự một.
`compare_digest` luôn chạy hết chuỗi nên không có kẽ hở đó.

**Rate limit dùng cửa sổ trượt 60 giây** lưu trong Redis Sorted Set, score là
timestamp. Em đã thử nghiệm với 15 request liên tiếp và kết quả đúng như thiết
kế: 10 request đầu qua, 5 request sau bị 429.

Hai chỗ dễ sai mà em đã xử lý:

- **Kiểm tra trước, ghi nhận sau.** Nếu `zadd` trước rồi mới `zcard` thì request
  thứ 10 (đúng bằng hạn mức) đã bị chặn oan.
- **Member phải duy nhất** (`f"{now}:{uuid4().hex}"`). Hai request cùng timestamp
  mà trùng member thì ZSET chỉ giữ một, và mình đếm thiếu.

Vì sao không đếm theo phút đồng hồ cho đơn giản? Với hạn mức 10/phút, người
dùng gửi 10 request lúc 10:00:59 và 10 request lúc 10:01:01 — 20 request trong
2 giây mà vẫn "đúng luật". Cửa sổ trượt không có kẽ hở đó.

**Cost guard** đếm tiền theo tháng (`cost:<user>:<YYYY-MM>`), nên sang tháng mới
ngân sách tự reset. `spent()` phải xử lý trường hợp key chưa tồn tại: Redis trả
`None`, hàm phải trả `0.0` chứ không được ném lỗi.

Rate limit và cost guard không thay thế nhau: 10 request/phút nghe có vẻ an
toàn, nhưng nếu mỗi request 50.000 token thì ngân sách bay trong vài phút.

**Thứ tự trong `/ask` là phần quan trọng nhất**: chặn trước khi gọi LLM. Tiền
mất ở bước gọi LLM, nên chặn sau khi đã gọi thì mình vừa mất tiền vừa phải trả
lỗi cho người dùng.

### CP4 — Sống sót khi scale và khi bị tắt

**State ra khỏi process.** Ban đầu em nghĩ một dict trong RAM là đủ nhanh và
đơn giản. Nhưng với 3 instance sau load balancer, câu hỏi thứ nhất rơi vào
container A, câu thứ hai rơi vào container B — nếu lịch sử nằm trong RAM của A
thì B không biết gì, agent "mất trí nhớ" ngẫu nhiên. Chuyển sang Redis List là
cách duy nhất để cả ba instance nhìn thấy cùng một dữ liệu.

Hai chi tiết bắt buộc trong `store.append()`: `ltrim(key, -20, -1)` chỉ giữ 20
message mới nhất (prompt dài vô hạn = tiền token vô hạn), và `expire` để hội
thoại cũ tự hết hạn. Còn `ping()` phải nuốt mọi exception và trả `False` — nó
dùng cho `/ready`, để exception thoát ra là readiness probe biến thành lỗi 500.

**`/health` khác `/ready` ở đúng một điểm**, và điểm đó quan trọng:

|                     | `/health` (liveness)               | `/ready` (readiness)                               |
| ------------------- | ---------------------------------- | -------------------------------------------------- |
| Câu hỏi             | Process còn sống không?            | Nhận traffic được chưa?                            |
| Kiểm tra dependency | Không                              | Có                                                 |
| Trả 503 thì sao     | Orchestrator **restart** container | Load balancer **ngừng gửi** request, không restart |

Gộp hai cái làm một là lỗi kinh điển: Redis mất kết nối 30 giây → cả 3 container
đều báo unhealthy → orchestrator restart cả 3 cùng lúc → khi Redis quay lại thì
không còn container nào phục vụ.

**Graceful shutdown** là phần em thấy thú vị nhất. Khi deploy bản mới, platform
gửi SIGTERM rồi đợi vài chục giây trước khi SIGKILL. Cái bẫy: mỗi tín hiệu chỉ
có **một** handler, nên đăng ký handler của mình là ghi đè handler của uvicorn —
thứ thực sự chịu trách nhiệm dừng server. Quên gọi lại nó thì app bật cờ "đang
tắt" rồi chạy tiếp mãi, cho tới khi bị SIGKILL. Viết graceful shutdown để rồi bị
kill cứng thì còn tệ hơn là không viết gì. Cách làm đúng: nhớ handler cũ trong
`install()`, rồi gọi lại nó trong `request_shutdown()`.

### CP5 — Đưa lên Internet

Phần này dùng Railway: `railway.toml` đã khai báo build từ Dockerfile và
healthcheck trỏ vào `/health`. Các biến môi trường (`AGENT_API_KEY`, `REDIS_URL`,
`RATE_LIMIT_PER_MINUTE`, `MONTHLY_BUDGET_USD`, `LOG_LEVEL`) được set trong
dashboard, **không** nằm trong repo. Biến `PORT` do Railway tự gán — đây là lý do
Dockerfile phải đọc `${PORT:-8000}` thay vì cứng 8000.

Trong lúc chờ tài khoản cloud, em đã kiểm tra toàn bộ luồng bằng stack chạy ở
máy với 3 instance — kết quả trình bày ở phần dưới.

---

## 4. Bằng chứng đo được

### 4.1 Image Docker

| Bản                                                    | Dung lượng  |
| ------------------------------------------------------ | ----------- |
| Một stage (`Dockerfile.single-stage`, bản gốc của lab) | **1.19 GB** |
| Multi-stage (`Dockerfile`)                             | **184 MB**  |

Chênh lệch khoảng 1.0 GB — bản multi-stage nhỏ hơn gần **6.5 lần**. Nguyên nhân
chính là base image `python:3.11` bản đầy đủ, cộng thêm việc bản một-stage
không có stage nào để vứt phần chỉ phục vụ build (chi tiết ở `exercises.md`
Câu 3). Đáng chú ý: **cùng một bộ test CP2 chạy qua cả hai** — code không đổi,
chỉ đổi cách đóng gói.

### 4.2 Stack 3 instance chạy thật

`docker compose up -d --scale agent=3` — cả ba container `healthy`:

```
agent|Up 3 minutes (healthy)|0.0.0.0:8002->8000/tcp
agent|Up 3 minutes (healthy)|0.0.0.0:8001->8000/tcp
agent|Up 3 minutes (healthy)|0.0.0.0:8000->8000/tcp
redis|Up 26 minutes (healthy)|0.0.0.0:6379->6379/tcp
```

Gọi tuần tự vào ba cổng khác nhau (tức ba container khác nhau) với cùng một
`X-User-Id`:

```
lượt 1 → container cổng 8000: history_length = 12
lượt 2 → container cổng 8001: history_length = 14
lượt 3 → container cổng 8002: history_length = 16
lượt 4 → container cổng 8000: history_length = 18
lượt 5 → container cổng 8001: history_length = 20
lượt 6 → container cổng 8002: history_length = 20
```

Đọc bảng này ra được hai điều:

1. `history_length` tăng đều 2 đơn vị mỗi lượt **dù request rơi vào container
   khác nhau** → lịch sử thật sự nằm ở Redis. Nếu lịch sử nằm trong dict Python
   của từng container, con số sẽ nhảy lung tung hoặc quay về 0.
2. Lượt 6 vẫn là 20 chứ không phải 22 → `ltrim` đã cắt đúng ở giới hạn 20
   message. Nếu quên `ltrim`, prompt sẽ phình vô hạn và tiền token cũng vậy.

### 4.3 Các mã trạng thái quan sát được

```
GET  /health                                 200  {"status":"ok","service":"day12-agent","version":"1.0.0"}
GET  /ready                                  200  {"status":"ready","redis":true}
POST /ask   (không có API key)               401  {"detail":"invalid or missing API key"}
POST /ask   (có API key)                     200  {"answer":"...","history_length":2,...}
POST /ask   × 15 (hạn mức 10/phút)           [200 ×10, 429 ×5]
```

### 4.4 Log JSON thật

Một dòng lấy từ `docker compose logs agent`:

```json
{"event": "ask_completed", "level": "info", "timestamp": "2026-09-29T04:33:20.435960+00:00", "user_id": "sv-roundrobin", "tokens_in": 490, "tokens_out": 46, "cost_usd": 0.0001011}
```

Từ dòng log này trả lời được những câu mà `print("đã trả lời xong")` không bao
giờ trả lời nổi: user nào đang tiêu nhiều tiền nhất, chi phí trung bình mỗi
request là bao nhiêu, tỷ lệ lỗi trong 5 phút qua là bao nhiêu.

---

## 5. Những chỗ em đã sai và cách tìm ra

**Lỗi 1 — Docker daemon không chạy.** Lần đầu chạy `docker compose up -d redis`
em nhận thông báo `failed to connect to the docker API at
npipe:////./pipe/dockerDesktopLinuxEngine`. Ban đầu em tưởng sai
`docker-compose.yml`, nhưng thực ra chỉ là Docker Desktop chưa khởi động. Cách
kiểm tra nhanh: `docker context ls` — nếu context `desktop-linux` đang được chọn
mà vẫn lỗi thì là daemon chưa lên, không phải lỗi file cấu hình.

**Lỗi 2 — Windows console không in được tiếng Việt.** Script kiểm tra của em
ban đầu chết với `UnicodeEncodeError: 'charmap' codec can't encode character`.
Nguyên nhân: console Windows mặc định dùng cp1252. Cách sửa: ép UTF-8 ngay
trong script bằng `sys.stdout.reconfigure(encoding="utf-8")`.

**Lỗi 3 — build image một-stage không lấy được base image.** Docker báo
`failed to fetch oauth token: lookup auth.docker.io: no such host`, trong khi
máy vẫn vào được Docker Hub. Đây là lỗi DNS bên trong build, không phải lỗi
Dockerfile. Cách xử lý: thử lại, và nếu vẫn không được thì ghi rõ trong báo cáo
số nào đo được, số nào không — chứ không tự bịa số.

Điều em rút ra: phần lớn thời gian không mất ở chỗ viết code, mà ở chỗ phân biệt
"lỗi môi trường" với "lỗi code". `docker context ls` và việc đọc kỹ thông báo lỗi
tiết kiệm được khá nhiều thời gian.

---

## 6. Việc còn lại

1. **Deploy lên Railway** và điền Public URL vào `DEPLOYMENT.md`, rồi chạy
   `pytest tests/test_cp5.py -v`.
2. **Chụp 2 ảnh** vào `screenshots/`: trang dashboard và kết quả gọi `/health`.
3. **(Bonus, không bắt buộc)** tự viết `.github/workflows/ci.yml` cho CI/CD —
   mỗi lần push là chạy test, build image, chỉ deploy khi mọi thứ xanh. Phần này
   cần đẩy repo lên GitHub và cất token deploy trong GitHub Secrets.

Cách tự kiểm tra toàn bộ phần bắt buộc:

```powershell
pytest tests/ -q -m "not docker"     # CP1–CP4
python grade.py                      # xem điểm tổng
python scripts/smoke_check.py        # kiểm tra endpoint bản chạy ở máy
```

---

## 7. Điều đọng lại

Bài lab này dạy em một điều khá đơn giản nhưng phải tự tay làm mới thấm: **hầu
hết các quy tắc trong tài liệu đều là hệ quả của một sự cố thật**. Viết log dạng
JSON vì cloud gom log theo dòng. Không có giá trị mặc định cho secret vì có
người đã trả tiền cho khóa mặc định của người khác. Tách `/health` khỏi `/ready`
vì có hệ thống đã tự sập toàn bộ khi Redis mất kết nối 30 giây. Đọc lý do đằng
sau mỗi quy tắc thì nhớ lâu hơn nhiều so với học thuộc cú pháp.
