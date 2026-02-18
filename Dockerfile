FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=config.settings.base

WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements
COPY requirements/base.txt /app/
COPY requirements/development.txt /app/

# Instalar dependencias de Python
RUN pip install --upgrade pip && \
    pip install -r base.txt && \
    pip install -r development.txt

# Copiar aplicación
COPY . .

# Crear usuario no-root
RUN useradd -m -u 1000 django_user && \
    chown -R django_user:django_user /app && \
    mkdir -p /app/staticfiles /app/media && \
    chown -R django_user:django_user /app/staticfiles /app/media

USER django_user

EXPOSE 8000