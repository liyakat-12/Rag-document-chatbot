# DocuMind AI — API + Streamlit image (offline-capable)
# Build:  docker compose build
# Optional model pre-download: docker build --build-arg PRELOAD_MODELS=1 .

FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Optional: bake FastEmbed model into the image (needs network at build time)
ARG PRELOAD_MODELS=0
ENV FASTEMBED_CACHE_PATH=/models/fastembed
RUN mkdir -p /models/fastembed /app/uploads /app/vector_store /app/data \
    && if [ "$PRELOAD_MODELS" = "1" ]; then \
         python -c "from fastembed import TextEmbedding; TextEmbedding(model_name='BAAI/bge-small-en-v1.5')"; \
       fi

COPY backend ./backend
COPY streamlit_app ./streamlit_app

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV MAX_UPLOAD_SIZE_MB=40
ENV LLM_PROVIDER=extractive
ENV EMBEDDING_PROVIDER=local
ENV LOCAL_EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
ENV EMBEDDING_DIMENSIONS=384
ENV HF_HOME=/models/hf
ENV FASTEMBED_CACHE_PATH=/models/fastembed

EXPOSE 7860 8000 8501

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=5 \
  CMD curl -fsS http://127.0.0.1:8000/api/v1/health || exit 1

CMD ["streamlit", "run", "streamlit_app/app.py", \
     "--server.port=7860", \
     "--server.address=0.0.0.0", \
     "--browser.gatherUsageStats=false"]
