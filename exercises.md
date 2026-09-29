# Phiếu Phản Ánh — K4 Level 3B, Ngày 12

> **Bài làm cá nhân.** Trả lời bằng lời của chính bạn, dựa trên những gì bạn
> quan sát được khi chạy code — không sao chép đáp án của người khác.
>
> Cách trả lời: viết câu trả lời ngay dưới mỗi câu hỏi, trong khối trích dẫn.
> `grade.py` đếm số câu đã trả lời (15 điểm cho 10 câu).
>
> Họ và tên: Phan Duy Thành  Mã học viên: 2A202602930

---

### Câu 1 — Fail fast (CP1)

Trong `Settings`, `agent_api_key` không có giá trị mặc định nên app chết ngay
khi khởi động nếu thiếu biến môi trường. Hãy mô tả một tình huống cụ thể mà
việc "chết sớm" này cứu bạn, so với việc để mặc định `"changeme"`.

> Tình huống: em deploy lần đầu lên Railway bằng `railway up` nhưng quên set
> biến `AGENT_API_KEY` trong dashboard.
>
> Với `agent_api_key: str` không mặc định, container khởi động là chết ngay
> với `ValidationError: agent_api_key Field required`. Railway thấy health
> check fail nên báo deploy lỗi, log hiện thẳng tên biến còn thiếu. Em biết
> ngay mình quên gì, sửa trong một phút, và điều quan trọng nhất: **chưa có
> request nào của người lạ đi vào service**.
>
> Nếu để mặc định `"changeme"`, mọi chuyện diễn ra ngược lại. Container khởi
> động bình thường, health check xanh, deploy báo thành công, service trả lời
> trơn tru. Nhưng khóa hữu hiệu lúc đó là `"changeme"` — một chuỗi ai cũng đoán
> được, lại còn nằm công khai trong source code trên GitHub nên bất kỳ ai đọc
> repo cũng biết. Bot quét Internet tìm endpoint mới trong vòng vài giờ. Đến
> lúc em phát hiện ra thì vấn đề không còn là "quên set biến" nữa, mà là hóa
> đơn LLM do người khác tiêu, và em không có cách nào chứng minh đó không phải
> mình. Việc "chết sớm" đổi một sự cố im lặng kéo dài thành một lỗi ồn ào
> trong 2 phút.
>
> Điều này cũng đúng ở mức nhỏ hơn: trong test CP1, `Settings(_env_file=None)`
> khi không có biến môi trường sẽ ném `ValidationError` ngay, chứ không âm
> thầm chạy bằng một giá trị nào đó.

---

### Câu 2 — Log cho máy đọc (CP1)

Chạy service và gọi `/ask` vài lần. Dán một dòng log JSON bạn thu được, rồi
nêu **hai** việc bạn làm được với dòng log đó mà `print("đã trả lời xong")`
không làm được.

> Dòng log thật lấy từ `docker compose logs agent`:
>
> ```json
> {"event": "ask_completed", "level": "info", "timestamp": "2026-09-29T04:33:20.435960+00:00", "user_id": "sv-roundrobin", "tokens_in": 490, "tokens_out": 46, "cost_usd": 0.0001011}
> ```
>
> Hai việc làm được:
>
> **1. Tính tổng chi phí theo từng user.** Vì `user_id` và `cost_usd` là hai
> trường riêng biệt, em lọc các dòng có `event = "ask_completed"` rồi cộng dồn
> `cost_usd` theo `user_id`, và biết ngay hôm nay ai tiêu nhiều nhất. Với
> `print("đã trả lời xong")` thì không có gì để lọc cả — chuỗi đó không mang
> theo thông tin nào, muốn biết chi phí phải sửa code ở mọi chỗ đã in.
>
> **2. Đặt cảnh báo tự động trên một ngưỡng số.** Vì `level` là trường riêng và
> `timestamp` ở định dạng ISO, em cấu hình được quy tắc kiểu *"nếu trong 5 phút
> qua có nhiều hơn N dòng `cost_usd` cộng lại vượt X thì bắn cảnh báo"*. Hệ
> thống gom log (Datadog, CloudWatch...) đọc được các trường này vì mỗi dòng là
> một JSON object hợp lệ. Một câu tiếng Việt tự do thì máy phải "hiểu" ngôn ngữ
> mới phân tích được, còn JSON thì chỉ cần đọc khóa.
>
> Ngoài ra, vì mỗi event nằm gọn trên **một dòng** và dùng `ensure_ascii=False`,
> tiếng Việt trong câu trả lời vẫn đọc được mà log không bị vỡ thành nhiều mảnh
> khi cloud gom theo dòng.

---

### Câu 3 — Kích thước image (CP2)

Build cả hai phiên bản và ghi lại số đo thật:

```bash
docker build -f <Dockerfile-1-stage> -t agent:single .
docker build -t agent:multi .
docker images | grep agent
```

| Bản               | Dung lượng  |
| ----------------- | ----------- |
| 1 stage (bản đầu) | **1.19 GB** |
| Multi-stage       | **184 MB**  |

Giải thích: phần dung lượng chênh lệch đó là những gì?

> **Số đo thật** (`docker images --format "{{.Repository}}:{{.Tag}} => {{.Size}}"`):
>
> ```
> day12-agent:single => 1.19GB
> day12-agent:prod   => 184MB
> ```
>
> Chênh lệch khoảng **1.0 GB** — bản multi-stage chỉ còn chưa tới **1/6** dung
> lượng bản một-stage.
>
> Log build của bản một-stage chỉ có 4 layer, và layer nặng nhất là base image:
>
> ```
> => [1/4] FROM docker.io/library/python:3.11        433.7s
> => [2/4] WORKDIR /app                                0.5s
> => [3/4] COPY . .                                    0.1s
> => [4/4] RUN pip install -r requirements.txt       104.2s
> ```
>
> Phần chênh lệch đến từ ba nguồn, xếp theo mức đóng góp:
>
> 1. **Base image.** `python:3.11` bản đầy đủ kéo về ~409 MB nén (các layer
>    25.6 + 67.8 + 49.4 + 236.4 + 6.1 + 24.1 MB), giải nén ra hơn 1 GB: nó mang
>    theo cả toolchain biên dịch (`gcc`, `make`), thư viện phát triển, `git`,
>    tài liệu... Bản `python:3.11-slim` chỉ còn vài chục MB nén. Đây là phần
>    chiếm gần như toàn bộ khoảng chênh lệch.
> 2. **Cache và wheel của pip nằm lại trong image.** Bản một-stage chạy
>    `pip install` thẳng trong image cuối và không có `--no-cache-dir`, nên mọi
>    file wheel tải về vẫn còn nguyên trong `/root/.cache/pip` của layer đó.
>    Stage `builder` của bản multi-stage có `--no-cache-dir`, và dù có thì cả
>    thư mục build cũng bị vứt đi cùng stage.
> 3. **Thư viện chỉ cần lúc build nhưng không có chỗ để vứt.** Bản một-stage
>    chỉ có một stage duy nhất, nên mọi thứ từng cần để cài đặt dependency đều
>    ở lại trong image. Multi-stage tạo ra một chỗ để bỏ chúng: `COPY --from=
>    builder /install /usr/local` chỉ mang **kết quả** sang, không mang theo
>    quá trình tạo ra kết quả đó.
>
> Điều đáng chú ý: bản multi-stage **nhỏ hơn nhưng vẫn chạy y hệt** — vì image
> runtime không hề thiếu thư viện nào, chỉ thiếu những thứ chỉ phục vụ việc
> build. Đây chính là điểm mà multi-stage giải quyết: tách "thứ cần để tạo ra
> sản phẩm" khỏi "thứ cần để sản phẩm chạy".

---

### Câu 4 — Thứ tự lệnh trong Dockerfile (CP2)

Sửa một ký tự trong `app/main.py` rồi build lại. Với Dockerfile của bạn, những
layer nào được dùng lại từ cache, layer nào phải chạy lại? Nếu bạn đặt
`COPY . .` lên trước `RUN pip install` thì kết quả khác thế nào?

> Dockerfile của em có thứ tự: `FROM ... AS builder` → `COPY requirements.txt .`
> → `RUN pip install` → `FROM ... AS runtime` → `COPY --from=builder /install
> /usr/local` → `COPY app ./app` → `COPY utils ./utils` → `RUN useradd` →
> `USER appuser` → `HEALTHCHECK` → `CMD`.
>
> Khi sửa một ký tự trong `app/main.py` và build lại:
>
> - **Dùng lại từ cache:** hai layer `FROM` (base image đã có sẵn), layer
>   `COPY --from=builder /install /usr/local` và toàn bộ stage `builder` bên
>   trong nó — tức là `COPY requirements.txt` và `RUN pip install`. Docker
>   không cài lại một thư viện nào, vì nội dung `requirements.txt` không đổi.
> - **Phải chạy lại:** `COPY app ./app` (vì nội dung `app/` đã thay đổi), và mọi
>   layer đứng sau nó. May là các layer sau rất rẻ: `RUN useradd`, `USER`,
>   `EXPOSE`, `HEALTHCHECK`, `CMD` chỉ là thao tác gần như tức thời, không có
>   bước nào tải hay biên dịch.
>
> Nói cách khác, chi phí build lại gần như bằng 0 phần dependency, chỉ tốn thời
> gian copy source — khoảng vài giây.
>
> **Nếu đặt `COPY . .` lên trước `RUN pip install`** thì mọi thứ đảo ngược. Mỗi
> lần sửa một dấu phẩy trong code, nội dung thư mục build context thay đổi →
> layer `COPY . .` mất cache → kéo theo `RUN pip install` mất cache luôn, vì
> Docker huỷ cache từ **layer đầu tiên thay đổi trở đi**. Kết quả là mỗi lần
> sửa code phải cài lại toàn bộ thư viện từ đầu: tải và cài lại fastapi,
> pydantic, uvicorn... Một thay đổi 1 ký tự biến thành một phút chờ, và điều
> này xảy ra ở *mọi lần build* trong suốt quá trình phát triển.
>
> Nguyên tắc em rút ra: **những thứ ít thay đổi đặt trước, những thứ hay thay
> đổi đặt sau.** `requirements.txt` gần như không đổi, source code thì đổi liên
> tục — nên thứ tự `requirements` → `pip install` → `source` là thứ tự đúng.

---

### Câu 5 — Vì sao không chạy bằng root (CP2)

Container mặc định chạy bằng root. Mô tả chuỗi sự kiện dẫn từ "một lỗ hổng
trong code Python của bạn" tới "kẻ tấn công có quyền cao trên máy host", và
lệnh `USER` cắt đứt chuỗi đó ở chỗ nào.

> Chuỗi sự kiện khi container chạy bằng root:
>
> 1. Code Python có một lỗ hổng cho phép chạy lệnh (ví dụ deserialization hoặc
>    path traversal dẫn tới thực thi lệnh). Kẻ tấn công gửi một request khai
>    thác lỗ hổng đó.
> 2. Lệnh của họ chạy **trong container**, với quyền của process đang phục vụ
>    request — mà process đó là root (uid 0), vì Dockerfile không có `USER`.
> 3. Là root trong container, họ không bị giới hạn bởi quyền file: đọc được
>    mọi thứ trong image, sửa được `/usr/local/lib/python3.11/...` để cài
>    backdoor tồn tại qua các lần restart, và quan trọng hơn là đọc được toàn
>    bộ **biến môi trường** — chỗ chứa `AGENT_API_KEY` và `REDIS_URL`.
> 4. Từ đó họ nối tới Redis (cùng network của compose, và `redis` là hostname
>    nội bộ), đọc/sửa lịch sử hội thoại và chi phí của mọi người dùng. Container
>    bị chiếm không còn là "một container bị chiếm" nữa mà là một bàn đạp.
> 5. Bước cuối là thoát hẳn ra host. Container chạy root **không tự động
>    nghĩa là** thoát được ra host — cần thêm điều kiện (chạy `--privileged`,
>    mount `/var/run/docker.sock`, hoặc một lỗ hổng kernel cho phép thoát
>    container). Nhưng khi process đã là root thì mọi điều kiện đó trở thành
>    "chỉ cần một lỗ hổng nữa", trong khi nếu là user thường thì kẻ tấn công
>    phải phá thêm **hai** lớp: thoát container **và** leo thang đặc quyền.
>
> Lệnh `USER appuser` cắt chuỗi ở **bước 2**. Với `useradd --create-home --uid
> 10001 appuser` rồi `USER appuser`, process chỉ có quyền của uid 10001:
>
> - Không ghi được vào `/usr/local` hay `/etc` → không cài backdoor vào image.
> - Không đọc được những file mà chỉ root đọc được.
> - Không cài được package, không sửa được cấu hình hệ thống.
> - Muốn thoát container thì phải có thêm một lỗ hổng leo thang đặc quyền nữa,
>   tức là phải phá hai lớp thay vì một.
>
> Điều đáng chú ý: `USER appuser` **không làm mất chức năng nào** của app. App
> chỉ cần bind cổng 8000 (lớn hơn 1024 nên user thường cũng bind được), đọc
> source trong `/app` và nói chuyện với Redis. Đây là trường hợp điển hình của
> một thay đổi gần như miễn phí nhưng cắt hẳn một lớp rủi ro.

---

### Câu 6 — Cửa sổ trượt (CP3)

Rate limit của bạn dùng sliding window 60 giây. Nếu thay bằng cách đếm theo
phút đồng hồ (reset lúc giây 00), một người dùng có thể gửi tối đa bao nhiêu
request trong 2 giây liên tiếp khi hạn mức là 10/phút? Giải thích cách đạt được
con số đó.

> Tối đa **20 request trong 2 giây** — gấp đôi hạn mức.
>
> Cách đạt được: bộ đếm theo phút đồng hồ chỉ reset khi đồng hồ sang giây 00.
> Người dùng chỉ cần canh đúng ranh giới đó:
>
> - Lúc `10:00:59`: gửi 10 request. Bộ đếm của phút 10:00 đang là 0, nhận đủ
>   10 request rồi đạt hạn mức — vẫn hợp lệ.
> - Lúc `10:01:01`, tức **2 giây sau**: đồng hồ sang phút mới, bộ đếm reset về
>   0. Gửi tiếp 10 request. Lại hợp lệ.
>
> Tổng cộng 20 request trong 2 giây, mà cả hai phút đều "đúng luật" nếu chỉ
> nhìn vào con số đếm. Với cửa sổ trượt 60 giây thì chuyện này không xảy ra:
> ở `10:01:01`, cửa sổ vẫn còn nhìn thấy 10 request lúc `10:00:59` (mới 2 giây
> trước), nên 10 request mới bị chặn ngay từ cái đầu tiên — đúng 10 request
> trong 60 giây, không hơn.
>
> Điều em thấy thú vị: cách đếm theo phút đồng hồ không sai ở "số request mỗi
> phút", nó sai ở chỗ **không có gì đảm bảo mật độ trong khoảng thời gian
> ngắn**. Với dịch vụ trả tiền theo request, gấp đôi lưu lượng trong 2 giây
> cũng là gấp đôi hóa đơn trong 2 giây.

---

### Câu 7 — Rate limit và cost guard (CP3)

Hai cơ chế này khác nhau ở điểm nào? Cho một tình huống mà rate limit cho qua
nhưng cost guard phải chặn, và một tình huống ngược lại.

> Khác nhau ở **đại lượng được đo**: rate limit đếm *số lượng* request trong
> một khoảng thời gian, cost guard đếm *số tiền* đã tiêu trong một tháng. Hai
> con số này không tỉ lệ thuận với nhau, vì chi phí của một request phụ thuộc
> vào độ dài prompt và độ dài câu trả lời.
>
> **Rate limit cho qua nhưng cost guard phải chặn:** hạn mức 10 request/phút,
> ngân sách 10 USD/tháng. Một user hỏi 5 câu, mỗi câu kèm một tài liệu dài
> 50.000 token để tóm tắt. Về số lượng, 5 request vẫn nằm dưới hạn mức 10 nên
> rate limiter không có gì để chặn. Nhưng chi phí token đầu vào của 5 request
> đó có thể vượt cả ngân sách tháng. Rate limit nhìn thấy "5 request", cost
> guard nhìn thấy "đã tiêu hết tiền" — và cost guard mới là cái phải lên
> tiếng.
>
> **Cost guard cho qua nhưng rate limit phải chặn:** ngân sách tháng còn rất
> nhiều (mới tiêu 0,01 USD trên 10 USD), nhưng user gửi 60 request trong một
> phút, toàn câu hỏi ngắn một dòng. Chi phí tổng chẳng đáng kể nên cost guard
> không có lý do gì để chặn. Nhưng 60 request/phút là hành vi tấn công hoặc
> một client bị lỗi vòng lặp, và nó làm nghẽn service của những người dùng
> khác — đây là việc của rate limit.
>
> Điểm đáng nhớ: **hai cơ chế này không thay thế nhau, và cũng không được đặt
> sai thứ tự.** Trong `/ask` em đặt `limiter.check()` trước `guard.check()`,
> và cả hai đều chạy **trước** khi gọi LLM. Nếu đặt sau khi gọi LLM thì đã mất
> tiền rồi mới phát hiện ra là không nên phục vụ request đó.

---

### Câu 8 — /health khác /ready (CP4)

Nếu gộp hai endpoint làm một và cho nó kiểm tra Redis, chuyện gì xảy ra với cụm
3 container khi Redis mất kết nối 30 giây? Trả lời theo đúng thứ tự sự kiện.

> Cả ba container đều nối vào cùng một Redis, nên thứ tự sự kiện như sau:
>
> 1. Giây 0: Redis mất kết nối (bị restart, mạng chập, hoặc quá tải).
> 2. Mỗi container gọi probe → probe kiểm tra Redis → thất bại → cả **3
>    container cùng lúc** báo unhealthy.
> 3. Orchestrator (Docker, Railway, K8s) đọc tín hiệu unhealthy theo đúng nghĩa
>    của một health check: "đơn vị này hỏng, phải thay". Nó **restart cả ba
>    container cùng lúc**.
> 4. Trong lúc ba container khởi động lại, **không còn instance nào phục vụ**.
>    Trước đó service vẫn trả lời được một phần (chỉ những request cần Redis bị
>    lỗi); bây giờ thì mọi request đều thất bại. Sự cố nhỏ đã thành mất dịch vụ
>    hoàn toàn.
> 5. Giây 30: Redis sống lại. Nhưng lúc này chưa chắc container nào đã khởi
>    động xong, và vì cả ba vừa bị restart nên chúng đang ở trạng thái lạnh
>    (mất cache, phải kết nối lại). Nếu trong lúc khởi động Redis chưa kịp
>    sẵn sàng, container lại báo unhealthy và lại bị restart — vòng lặp
>    crash-loop, mỗi vòng càng làm hệ thống khó hồi phục hơn.
>
> Điểm mấu chốt là vế sau: orchestrator **không phân biệt được** "process này
> hỏng" với "dependency của process này đang hỏng". Nó chỉ thấy unhealthy và
> làm đúng một việc là restart.
>
> Khi tách đúng `/health` (liveness, không chạm Redis) và `/ready` (readiness,
> có chạm Redis), kịch bản đổi hẳn:
>
> 1. Redis mất kết nối → `/health` vẫn 200 vì process còn sống bình thường →
>    orchestrator **không restart** gì cả.
> 2. `/ready` trả 503 → load balancer **ngừng gửi request mới** vào các
>    instance đó. Đây là hành động nhẹ và có thể đảo ngược, khác hẳn restart.
> 3. Giây 30: Redis sống lại → `/ready` trả 200 trở lại → load balancer đẩy
>    traffic vào như cũ. Không container nào phải khởi động lại, không có
>    khoảng downtime nào, người dùng gần như không nhận ra.
>
> Cùng một sự cố Redis 30 giây, một bên là mất dịch vụ toàn hệ thống, một bên
> là chậm vài giây. Khác nhau chỉ ở chỗ endpoint nào được phép kiểm tra
> dependency.

---

### Câu 9 — Stateless (CP4)

Chạy `docker compose up --scale agent=3` rồi gọi `/ask` nhiều lần với cùng một
`X-User-Id`. Quan sát `history_length` trong response. Nếu lịch sử được lưu
trong một dict Python thay vì Redis, bạn sẽ thấy con số đó thay đổi thế nào?

> Em chạy `docker compose up -d --scale agent=3`, cả ba container đều `healthy`,
> rồi gọi lần lượt vào ba cổng khác nhau (8000, 8001, 8002 — tức là ba container
> khác nhau) với cùng `X-User-Id: sv-roundrobin`:
>
> ```
> lượt 1 → container cổng 8000: history_length = 12
> lượt 2 → container cổng 8001: history_length = 14
> lượt 3 → container cổng 8002: history_length = 16
> lượt 4 → container cổng 8000: history_length = 18
> lượt 5 → container cổng 8001: history_length = 20
> lượt 6 → container cổng 8002: history_length = 20
> ```
>
> (12 là vì user này đã có sẵn 12 message từ các lượt gọi trước.)
>
> Con số tăng đều **2 đơn vị mỗi lượt** — vì mỗi lượt ghi thêm 2 message (câu
> hỏi của user và câu trả lời của assistant). Điều quan trọng: nó tăng đều
> **dù request rơi vào ba container khác nhau**. Đó là bằng chứng lịch sử nằm ở
> Redis, nơi cả ba cùng nhìn thấy.
>
> Lượt 6 vẫn là 20 chứ không phải 22 cũng là một kết quả đúng như mong đợi:
> `HISTORY_MAX_MESSAGES = 20` và `ltrim(key, -20, -1)` chỉ giữ 20 message mới
> nhất, nên lịch sử đã chạm trần. Nếu quên `ltrim`, con số này sẽ tăng mãi và
> mỗi lần gọi LLM là một prompt dài hơn lần trước.
>
> **Nếu lịch sử nằm trong một dict Python trong mỗi container**, bảng trên sẽ
> đổi hoàn toàn. Mỗi container có RAM riêng, nên mỗi container có một dict
> riêng bắt đầu từ rỗng:
>
> ```
> lượt 1 → container A (dict A): history_length = 0    (A vừa ghi 2 message)
> lượt 2 → container B (dict B): history_length = 0    (B không biết gì về A)
> lượt 3 → container C (dict C): history_length = 0
> lượt 4 → container A (dict A): history_length = 2    (A chỉ nhớ phần của A)
> lượt 5 → container B (dict B): history_length = 2
> ```
>
> Con số sẽ **quanh quẩn ở 0, 2, 4... và không bao giờ tăng đều**, vì nó phụ
> thuộc vào việc request rơi vào container nào chứ không phụ thuộc vào số câu
> đã hỏi. Nghiêm trọng hơn cả con số: agent sẽ trả lời như thể chưa từng nghe
> câu hỏi trước đó. Người dùng thấy agent "mất trí nhớ" ngẫu nhiên — hỏi lại
> một câu thì lúc nhớ lúc quên, không có quy luật nào. Hiện tượng này còn tệ
> hơn việc lịch sử không tồn tại, vì nó không nhất quán và rất khó tái hiện để
> sửa.

---

### Câu 10 — Deploy thật (CP5)

Ghi lại **một** lỗi bạn gặp khi deploy lên cloud (build fail, health check
timeout, sai REDIS_URL, app không đọc `$PORT`...): thông báo lỗi là gì, bạn
tìm ra nguyên nhân bằng cách nào, và sửa ra sao?

> **Lỗi: deploy xong, service báo Online, nhưng thực ra chưa dùng được.**
>
> Ngay sau `railway up`, card service trên Railway báo **Online** nên em tưởng
> đã xong. Nhưng khi gọi thử thì:
>
> ```
> GET  /health  → 200  {"status":"ok",...}          ← qua
> GET  /ready   → 503  {"status":"not ready","redis":false}
> POST /ask     → 401 (không key)  /  500 (có key)
> ```
>
> **Cách tìm ra nguyên nhân.** Em đọc hai tín hiệu rời nhau thay vì đoán:
>
> - `/ask` **không có key trả 401 chứ không phải 500**. Điều này chứng tỏ
>   `AGENT_API_KEY` đã set đúng — vì lớp xác thực phải chạy được thì mới trả
>   được 401. Vậy lỗi không nằm ở khâu cấu hình chung.
> - `/ready` nói rõ `"redis": false`, tức `store.ping()` thất bại.
>
> Ghép lại: app không nối được Redis. Em mở tab Variables của service agent và
> thấy đúng chỗ thiếu — biến `REDIS_URL` chưa nằm ở đó.
>
> **Nguyên nhân.** Không có `REDIS_URL`, `Settings` rơi về giá trị mặc định
> `redis://localhost:6379/0`. Trong container, `localhost` là **chính container
> đó**, không phải service Redis. Đây đúng là cái bẫy mà `docker-compose.yml` đã
> cảnh báo ở CP2 ("trong compose, tên service chính là hostname") — em đã hiểu
> nó ở mức lý thuyết, và lần này gặp nó thật trên cloud.
>
> **Cách sửa.** Trên Railway: service agent → **Variables** → thêm một Variable
> Reference `REDIS_URL=${{Redis.REDIS_URL}}` để Railway tự nối sang service
> Redis, rồi deploy lại. Sau đó:
>
> ```
> GET  /ready    → 200  {"status":"ready","redis":true}
> POST /ask × 15 → [200 ×10, 429 ×5]
> ```
>
> `pytest tests/test_cp5.py -v` → 9 passed, 4 skipped.
>
> **Điều em rút ra.** "Online" không có nghĩa là "chạy được". Một health check
> không kiểm tra dependency sẽ xanh kể cả khi service chưa phục vụ được request
> nào — và đó chính là lý do CP4 tách `/health` khỏi `/ready`. Nếu bài này chỉ có
> `/health`, em đã tưởng mọi thứ ổn và nộp một service hỏng.
>
> Một trục trặc khác gặp trước đó, khi build image một-stage ở máy: Docker báo
> `failed to fetch oauth token: lookup auth.docker.io: no such host`, trong khi
> máy vẫn vào được Docker Hub (200). Đây là lỗi DNS của môi trường build, không
> phải lỗi Dockerfile — thử lại sau đó là được.

---

