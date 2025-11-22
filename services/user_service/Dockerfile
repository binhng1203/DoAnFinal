FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y build-essential libpq-dev && rm -rf /var/lib/apt/lists/*

# Python deps
# Chỉ copy file định nghĩa dependencies
# Thêm 'poetry.lock*' để đảm bảo cài đúng version
COPY pyproject.toml poetry.lock* /app/

RUN pip install --no-cache-dir poetry==1.8.3 && \
    poetry config virtualenvs.create false && \
    # THÊM FLAG --no-root VÀO ĐÂY
    poetry install --no-interaction --no-ansi --no-root

# App code
# Bây giờ mới copy toàn bộ code của bạn vào
COPY . /app

EXPOSE 8000