FROM python:3.12-slim

WORKDIR /app

# Install curl for cosign download
RUN apt-get update && apt-get install -y curl ca-certificates bash && rm -rf /var/lib/apt/lists/* \
 && curl -L https://github.com/sigstore/cosign/releases/latest/download/cosign-linux-amd64 \
    -o /usr/local/bin/cosign \
 && chmod +x /usr/local/bin/cosign

RUN pip install --no-cache-dir httpx

COPY robot.py /app/robot.py
# Provide the public key to verify signatures
COPY cosign.pub /app/cosign.pub

# Unbuffered logs so "docker compose logs -f robot" shows output immediately
ENV PYTHONUNBUFFERED=1

CMD ["python", "/app/robot.py"]