FROM python:3.11-slim

# ffmpeg is a system package, not a pip package -- needed for the
# streaming audio analysis (piping raw PCM out of it).
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p tmp

ENV PORT=5000
EXPOSE 5000

CMD ["python", "app.py"]
