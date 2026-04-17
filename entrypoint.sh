#!/bin/sh

set -e

# Ожидание доступности базы данных (опционально, но полезно)
# Здесь мы просто запускаем миграции, так как docker-compose depends_on уже есть,
# но alembic сам упадет и перезапустится, если БД еще не готова.

echo "Running migrations..."
alembic upgrade head

echo "Starting command: $@"
exec "$@"
