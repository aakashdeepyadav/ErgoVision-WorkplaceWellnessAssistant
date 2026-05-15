# ---- Base Image ----
FROM python:3.12-slim as base
WORKDIR /app

# Install system dependencies (needed for OpenCV and MediaPipe)
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# ---- Python Dependencies ----
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---- Node Frontend Build ----
FROM node:18-alpine as frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend .
RUN npm run build

# ---- Final Image ----
FROM base as final
WORKDIR /app

# Copy python source
COPY . .

# Copy built frontend (Optional: if we want to serve it from FastAPI, but we can also use nginx in docker-compose)
# For this setup, we'll keep the backend running and assume frontend is served by a different container or proxy,
# but we'll include it just in case.
COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist

# Expose the API port
EXPOSE 8000

# Start the server
CMD ["python", "server.py"]
