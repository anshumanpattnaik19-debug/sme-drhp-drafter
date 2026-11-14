# The DRHP Studio app (FastAPI backend + built React UI). Not built or tested in this environment (no Docker access on the course VM).
FROM python:3.12-slim
WORKDIR /app
COPY requirements-app.txt ./
RUN pip install --no-cache-dir -r requirements-app.txt
COPY . .
ENV PYTHONDONTWRITEBYTECODE=1
EXPOSE 8765
CMD ["python", "-m", "uvicorn", "serve.app:app", "--host", "0.0.0.0", "--port", "8765"]
