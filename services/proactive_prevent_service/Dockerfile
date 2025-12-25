FROM python:3.9-slim

# Chỉ cài Git và Curl để phục vụ phân tích Diff và kiểm tra mạng
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements từ thư mục gốc (Context là DoAnFinal)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy toàn bộ code của Proactive Service
COPY services/proactive_prevent_service/ .

ENV REPO_CACHE_DIR=/app/repo_cache
ENV PYTHONUNBUFFERED=1

CMD ["python", "api.py"]