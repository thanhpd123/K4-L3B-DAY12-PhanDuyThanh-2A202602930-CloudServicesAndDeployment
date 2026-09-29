# ═══════════════════════════════════════════════════════════════════
# CP2 — Containerization
#
# Dưới đây là Dockerfile "chạy được nhưng chưa production": một stage,
# chạy bằng user root, không có health check, base image nặng.
#
# NHIỆM VỤ: sửa file này thành bản production-ready. Yêu cầu:
#   [x] Multi-stage build: stage `builder` cài dependency, stage runtime
#       chỉ copy kết quả sang → image nhỏ hơn, không mang theo compiler.
#       Cú pháp: `FROM python:3.11-slim AS builder`
#   [x] Base image slim (hoặc alpine), không dùng `python:3.11` bản đầy đủ
#   [x] COPY requirements.txt và pip install TRƯỚC khi COPY source code
#       (Docker cache theo layer: sửa 1 dòng code không phải cài lại thư viện)
#   [x] Tạo user thường và chuyển sang bằng lệnh `USER` — container chạy
#       root nghĩa là ai thoát được khỏi app cũng thành root trên host
#   [x] Có `HEALTHCHECK` gọi vào endpoint /health
#   [x] Đọc cổng từ biến môi trường PORT (cloud tự gán cổng, không cố định 8000)
#
# Kiểm tra:  pytest tests/test_cp2.py -v
# Build thử: docker build -t day12-agent:prod .
#            docker images day12-agent:prod     # xem dung lượng
# ═══════════════════════════════════════════════════════════════════

# ── Stage 1: builder ────────────────────────────────────────────────
# Stage này được phép "nặng": cài compiler, build wheel... rồi bị vứt đi.
FROM python:3.11-slim AS builder

WORKDIR /build

# COPY requirements TRƯỚC source: sửa code không làm hỏng cache thư viện.
COPY requirements.txt .

# Cài vào /install để stage runtime chỉ việc copy nguyên thư mục này sang.
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Stage 2: runtime ────────────────────────────────────────────────
# Chỉ stage CUỐI trở thành image: không compiler, không pip cache.
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Lấy dependency đã cài sẵn từ builder — không cài lại từ đầu.
COPY --from=builder /install /usr/local

# Source copy SAU cùng: mỗi lần sửa code chỉ rebuild từ layer này.
COPY app ./app
COPY utils ./utils

# Không chạy bằng root: có thoát được khỏi app cũng chỉ là user thường.
RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 8000

# Docker tự biết container còn phục vụ được không (gọi /health).
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '8000') + '/health').read()" || exit 1

# 0.0.0.0 để gọi được từ ngoài container; ${PORT:-8000} vì cloud tự gán cổng.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
