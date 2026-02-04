FROM python:3.12-slim
WORKDIR /app

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/* \
 && curl -L https://github.com/sigstore/cosign/releases/latest/download/cosign-linux-amd64 \
    -o /usr/local/bin/cosign \
 && chmod +x /usr/local/bin/cosign

RUN pip install --no-cache-dir httpx

COPY robot.py /app/robot.py
CMD ["python", "/app/robot.py"]