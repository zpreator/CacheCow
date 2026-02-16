FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN apt-get update && \
    apt-get install -y ffmpeg docker.io && \
    pip install --no-cache-dir -r requirements.txt && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

COPY . .

EXPOSE 8501

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8501"]
