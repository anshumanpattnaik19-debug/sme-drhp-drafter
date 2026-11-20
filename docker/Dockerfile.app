# DRHP Studio: the FastAPI backend and the built React UI, in one image.
# Build from the repository root:  docker build -f docker/Dockerfile.app -t drhp-studio .
# The fine-tuned model is not in this image; point the app's settings at a vLLM server (see docker/docker-compose.yml).

# stage 1: build the UI
FROM node:20-slim AS ui
WORKDIR /ui
COPY ui/package.json ui/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY ui/ ./
RUN npm run build

# stage 2: the service
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DRHP_WORKSPACE=/app/workspace
WORKDIR /app
# OCR (rapidocr-onnxruntime) loads OpenCV, which needs these system libraries in the slim image
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 libxcb1 && rm -rf /var/lib/apt/lists/*
COPY requirements-app.txt ./
RUN pip install --no-cache-dir -r requirements-app.txt
COPY serve/ serve/
COPY draft/ draft/
COPY extract/ extract/
COPY ingest/ ingest/
COPY assemble/ assemble/
COPY verify/ verify/
COPY rag/ rag/
COPY data/ data/
COPY teacher/ teacher/
COPY rai/ rai/
COPY --from=ui /ui/dist ui/dist
# the commit the image is built from, shown by /healthz:  --build-arg GIT_COMMIT=$(git rev-parse HEAD)
ARG GIT_COMMIT=unknown
RUN printf '{"commit": "%s", "dirty": 0}' "$GIT_COMMIT" > BUILD_INFO.json
RUN mkdir -p /app/workspace
EXPOSE 8765
CMD ["python", "-m", "uvicorn", "serve.app:app", "--host", "0.0.0.0", "--port", "8765"]
