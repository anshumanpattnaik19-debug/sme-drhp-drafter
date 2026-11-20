# DRHP Studio launcher on a Hugging Face Docker Space (Vercel runs launcher/app.py directly and ignores this file).
# A host that sets PORT is honoured; a Space does not, so 7860 is the default.
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py ./
USER 1000
EXPOSE 7860
CMD ["sh", "-c", "exec python -m uvicorn app:app --host 0.0.0.0 --port ${PORT:-7860} --proxy-headers --forwarded-allow-ips=*"]
