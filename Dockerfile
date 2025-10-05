# ---- Base Image ----
FROM python:3.11-slim AS base

# ---- Environment ----
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV PATH="/root/.local/bin:$PATH"

# ---- Working Directory ----
WORKDIR /app

# ---- System Dependencies ----
RUN apt-get update
RUN apt-get install -y --no-install-recommends gcc
RUN apt-get install -y --no-install-recommends libpq-dev
RUN apt-get install -y --no-install-recommends libffi-dev
RUN apt-get install -y --no-install-recommends libssl-dev
RUN apt-get install -y --no-install-recommends curl
RUN apt-get clean && rm -rf /var/lib/apt/lists/*
RUN apt-get update
RUN apt-get upgrade -y

# ---- Copy & Install Dependencies ----
COPY requirements.txt .

RUN pip install --upgrade pip setuptools wheel
RUN pip install -r requirements.txt

# ---- Copy Application Files ----
COPY . .

# ---- Pre-run Setup ----
# If your script creates environment files or credentials before launch
RUN python create_cred.py || true

# ---- Expose Port ----
EXPOSE 8080

# ---- Launch Command ----
# Vercel expects CMD to run the app directly
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
