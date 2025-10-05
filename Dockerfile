# Base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy only necessary files first for caching
COPY requirements.txt .

# Install system dependencies (adjust if your packages need more)
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Expose port for Vercel
EXPOSE 8080

RUN python create_cred.py

# Run the app and generate credentials at runtime
CMD ["python", "main.py"]
