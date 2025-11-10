FROM python:3.10-slim-bullseye

# Set environment variable for non-interactive installation
ENV DEBIAN_FRONTEND=noninteractive
ENV PORT=8000

# Install all necessary system dependencies for headless GUI automation
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    xvfb \
    xauth \
    gnome-screenshot \
    libnss3 \
    libgbm-dev \
    libxshmfence-dev \
    libasound2 \
    libatk-bridge2.0-0 \
    libcups2 \
    libgdk-pixbuf2.0-0 \
    libgtk-3-0 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libxtst6 \
    libxss1 \
    libgbm1 \
    python3-tk \
    python3-dev \
    --no-install-recommends \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# CRITICAL FIX: Include this line to prevent the worker crash (RuntimeError: Directory '/app/static' does not exist)
RUN mkdir -p static 

# Copy the application code
COPY . .

# CRITICAL LAUNCH FIX: Use SHELL form CMD and wrap Gunicorn with xvfb-run.
# Sets the optimal screen size (1920x1080) for reliable full-page screenshots.
CMD xvfb-run --auto-servernum --server-args='-screen 0 1920x1080x24' gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 8 --worker-class uvicorn.workers.UvicornWorker --timeout 1800 app:app
