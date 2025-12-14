# Base image
FROM python:3.10-slim

# Thiết lập biến môi trường
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Thư mục làm việc
WORKDIR /app

# Cài đặt dependencies hệ thống (cần thiết cho psycopg2)
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Cài đặt thư viện Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Port mặc định của Flask
EXPOSE 8000

# Lệnh chạy server (Production dùng Gunicorn, Dev dùng Flask run)
CMD ["python", "src/main.py"]