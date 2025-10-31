FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN apt-get update && apt-get install -y supervisor && \
    apt-get install -y ffmpeg && \
    apt-get install -y docker.io && \
    pip install --no-cache-dir -r requirements.txt && \
    apt-get clean

# Copy app files
COPY . .

# Copy supervisor config
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Expose the default port (can be overridden by .env)
EXPOSE 8501

# Make supervisor the container entrypoint
CMD ["supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
