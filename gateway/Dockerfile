FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir fastapi uvicorn httpx
COPY server.py /app/server.py
EXPOSE 8081
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8081"]
