FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=kindergarten_project.settings

RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    libpq-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements-railway.txt /app/requirements.txt

RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/

# Применяем миграции
RUN python manage.py migrate --noinput

# Собираем статические файлы
RUN python manage.py collectstatic --noinput

EXPOSE $PORT

CMD gunicorn kindergarten_project.wsgi:application --bind 0.0.0.0:$PORT --workers 3