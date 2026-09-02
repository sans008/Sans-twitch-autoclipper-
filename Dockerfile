FROM python:3.11-slim

# ffmpeg is a system package, not a pip package -- needed for download/clip/analysis
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p output

# Render sets $PORT itself; app.py reads it. Default 5000 for other hosts.
ENV PORT=5000
EXPOSE 5000

CMD ["python", "app.py"]
