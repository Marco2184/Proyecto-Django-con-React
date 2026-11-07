FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
RUN useradd --create-home app && mkdir -p /app/media /app/staticfiles && chown -R app:app /app
COPY --chown=app:app manage.py ./
COPY --chown=app:app monolith ./monolith
COPY --chown=app:app usuarios ./usuarios
COPY --chown=app:app productos ./productos
COPY --chown=app:app carrito ./carrito
COPY --chown=app:app templates ./templates
COPY --chown=app:app locale ./locale
COPY --chown=app:app docker ./docker
USER app
EXPOSE 8000
CMD ["sh", "-c", "python manage.py collectstatic --noinput && exec gunicorn monolith.wsgi:application --bind 0.0.0.0:8000 --workers 2 --timeout 60 --access-logfile - --access-logformat '%(m)s %(s)s %(L)s'"]
