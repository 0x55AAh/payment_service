# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Copy uv binary from the official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV PYTHONPATH=/app/src
# Avoid building environments as root
ENV UV_PROJECT_ENVIRONMENT=/usr/local

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY pyproject.toml uv.lock ./
# Note: if uv.lock doesn't exist yet, it'll be created, but better to have it
RUN uv sync --frozen --no-install-project --extra test

# Copy project
COPY . .

# Default command
CMD ["uv", "run", "uvicorn", "payment.main:app", "--host", "0.0.0.0"]
