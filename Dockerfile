# ── Stage 1: Build Vue frontend ──
FROM node:20-alpine AS frontend
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ── Stage 2: Python app ──
FROM python:3.12-slim
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Copy built frontend into the image
COPY --from=frontend /build/dist /app/frontend/dist

EXPOSE 5001
CMD ["python", "run.py"]
