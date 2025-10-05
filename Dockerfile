# # Base image
# FROM python:3.11-slim

# # Set working directory
# WORKDIR /app

# # Copy only necessary files first for caching
# COPY requirements.txt .

# # Install system dependencies (adjust if your packages need more)
# RUN apt-get update && apt-get install -y \
#     gcc \
#     libpq-dev \
#     && rm -rf /var/lib/apt/lists/*

# # Install Python dependencies
# RUN pip install --no-cache-dir --upgrade pip && \
#     pip install --no-cache-dir -r requirements.txt

# # Copy the rest of the application
# COPY . .

# # Expose port for Vercel
# EXPOSE 8080

# RUN bash ./build.sh

# # Run the app and generate credentials at runtime
# CMD ["python", "app.py"]



# Base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy only necessary files first for caching
COPY requirements.txt .

# Install dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev bash \
    && pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy the rest of the application
COPY . .

# Expose port for Vercel
EXPOSE 8080

# Run the build script (if it exists) and start FastAPI app
CMD ["/bin/bash", "-c", "if [ -f ./build.sh ]; then bash ./build.sh; fi && uvicorn app:app --host 0.0.0.0 --port 8080"]
