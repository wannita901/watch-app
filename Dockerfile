# Stage 1: build frontend
FROM node:22-alpine AS web
WORKDIR /build
COPY web/package*.json ./
RUN npm ci --no-fund --no-audit
COPY web/ ./
RUN npm run build

# Stage 2: python server
FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir "fastapi>=0.115" "uvicorn>=0.30" "python-multipart>=0.0.9"
COPY server/*.py ./
COPY --from=web /build/dist /app/web/dist
ENV DB_PATH=/data/watch.db STATIC_DIR=/app/web/dist
VOLUME /data
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
