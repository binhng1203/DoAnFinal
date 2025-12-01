# Sử dụng Python 3.11 Slim để tối ưu dung lượng
FROM python:3.11-slim

# Thiết lập biến môi trường:
# - PYTHONDONTWRITEBYTECODE: Không sinh file .pyc
# - PYTHONUNBUFFERED: Log được in ngay lập tức ra console (quan trọng khi debug Docker)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Thiết lập thư mục làm việc trong container
WORKDIR /app

# 1. Cài đặt các gói hệ thống cần thiết
# - build-essential: Cho việc compile các thư viện C
# - libpq-dev: Thư viện cần thiết để psycopg2 kết nối PostgreSQL
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 2. Cài đặt Poetry và Dependencies
# Copy file cấu hình dependencies trước để tận dụng Docker cache layer
COPY pyproject.toml poetry.lock* /app/

# Cài đặt Poetry version 1.8.3 (giữ đồng bộ với User Service)
RUN pip install --no-cache-dir poetry==1.8.3 && \
    # Không tạo virtualenv riêng (vì Docker đã là môi trường cách ly rồi)
    poetry config virtualenvs.create false && \
    # Cài đặt dependencies (flag --no-root để chưa cài package hiện tại)
    poetry install --no-interaction --no-ansi --no-root

# 3. Copy toàn bộ mã nguồn vào container
COPY . /app

# Expose port 8000 (Gunicorn sẽ chạy ở port này bên trong container)
EXPOSE 8000

# Command mặc định (thường sẽ bị override bởi docker-compose, nhưng để đây cho chuẩn)
CMD ["gunicorn", "src.config.wsgi:application", "-b", "0.0.0.0:8000"]