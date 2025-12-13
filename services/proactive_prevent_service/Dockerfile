# Sử dụng Python 3.9 bản nhẹ (slim)
FROM python:3.9-slim

# Cài đặt Git (bắt buộc để clone repo) và curl
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Thiết lập thư mục làm việc
WORKDIR /app

# Copy file thư viện và cài đặt
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy toàn bộ code vào container
COPY . .

# Tạo thư mục cache cho repo
RUN mkdir -p /app/repo_cache

# Biến môi trường
ENV REPO_CACHE_DIR=/app/repo_cache
ENV PYTHONUNBUFFERED=1

# Lệnh chạy khi container khởi động
CMD ["python", "api.py"]