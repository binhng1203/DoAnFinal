# Base image ổn định
FROM python:3.11-slim

WORKDIR /app

# Cài thư viện hệ thống cho OpenCV/Scikit-image
RUN apt-get update && apt-get install -y \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy và cài đặt thư viện Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy toàn bộ source code vào
COPY . .

# Thiết lập đường dẫn import để Python tìm thấy self_healing_v1
ENV PYTHONPATH=/app

# Chạy app (Lưu ý đường dẫn tới file api.py)
CMD ["python", "runner/api.py"]