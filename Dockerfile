# Dockerfile
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Instalar dependencias
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copiar aplicación
COPY . .

# Crear usuario
RUN useradd -m -u 1000 django_user && \
    chown -R django_user:django_user /app && \
    mkdir -p /app/staticfiles /app/media && \
    chown -R django_user:django_user /app/staticfiles /app/media

USER django_user

EXPOSE 8000

# SIN CMD - Deja que docker-compose maneje