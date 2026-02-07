FROM python:3.12-slim

WORKDIR /app
COPY gateway/server.py /app/server.py
COPY gateway/cache_manager.py /app/cache_manager.py
COPY common /app/common
# Install curl to fetch cosign, then install cosign binary
RUN apt-get update && apt-get install -y curl ca-certificates && rm -rf /var/lib/apt/lists/* \
 && curl -L https://github.com/sigstore/cosign/releases/latest/download/cosign-linux-amd64 \
    -o /usr/local/bin/cosign \
 && chmod +x /usr/local/bin/cosign

# Provide the public key to verify signatures
COPY ./keys/cosign.pub /app/cosign.pub
 
RUN pip install --no-cache-dir fastapi uvicorn httpx

EXPOSE 8081
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8081"]
