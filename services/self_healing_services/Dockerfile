# Base image ổn định
FROM python:3.11-slim

WORKDIR /app

# Cài thư viện hệ thống:
# - build-essential: Để biên dịch C++
# - libgl1, libglib2.0-0: Cho OpenCV (xử lý ảnh)
# - libxml2-dev, libxslt-dev: QUAN TRỌNG CHO LXML
# - libpq-dev: Cho psycopg2 (kết nối DB)
RUN apt-get update && apt-get install -y \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    libxml2-dev \
    libxslt-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy và cài đặt thư viện Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy toàn bộ source code vào
COPY . .

# Thiết lập đường dẫn import để Python tìm thấy self_healing_v1
ENV PYTHONPATH=/app

# Chạy app
# Lưu ý: CMD này sẽ chạy khối if __name__ == "__main__" trong file api.py
CMD ["python", "runner/api.py"]