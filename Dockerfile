# syntax=docker/dockerfile:1

FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Не /app: пакет тоже называется app, и каталог перекрыл бы импорт.
WORKDIR /srv

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Явный список файлов вместо "COPY . ." — в образ попадает ровно то, что нужно.
COPY app ./app

RUN useradd --create-home --uid 1000 runner
USER runner

# Свой адрес передаётся аргументом:
#   docker compose run --rm speedtest https://ash-speed.hetzner.com/1GB.bin
ENTRYPOINT ["python", "app/main.py"]
