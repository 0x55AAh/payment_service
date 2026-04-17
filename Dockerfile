# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV PYTHONPATH=/app/src

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Copy and prepare entrypoint
RUN chmod +x entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]

# Command to run the application (will be overridden in docker-compose for consumer)
CMD ["uvicorn", "payment.main:app", "--host", "0.0.0.0", "--port", "8000"]
