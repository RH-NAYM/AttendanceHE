# Use the official lightweight Python image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /code

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
COPY create_cred.py .
RUN pip install --upgrade pip
RUN pip install -r requirements.txt


RUN python create_cred.py || true
# Copy project files
COPY . .

# Expose the port Uvicorn will run on
EXPOSE 7860

# Start the application
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]