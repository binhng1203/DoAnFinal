FROM python:3.11-slim

WORKDIR /app

# Cài các gói hệ thống cần thiết cho psycopg2
RUN apt-get update && apt-get install -y build-essential libpq-dev && rm -rf /var/lib/apt/lists/*

# Cài Poetry & Dependencies
COPY pyproject.toml poetry.lock* /app/
RUN pip install --no-cache-dir poetry==1.8.3 && \
    poetry config virtualenvs.create false && \
    poetry install --no-interaction --no-ansi --no-root

# Copy code
COPY . /app

EXPOSE 8000

# Lệnh chạy mặc định (Sẽ bị override bởi docker-compose)
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8000", "run:app"]