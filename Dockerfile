# DocuMind AI — API + Streamlit image
# Local Compose: backend/frontend override the command below.
# Hugging Face Spaces: uses this default (Streamlit on 7860 + in-process API).

FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend
COPY streamlit_app ./streamlit_app

RUN mkdir -p uploads vector_store data

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV MAX_UPLOAD_SIZE_MB=40
ENV LLM_PROVIDER=extractive
ENV EMBEDDING_PROVIDER=local
ENV LOCAL_EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
ENV EMBEDDING_DIMENSIONS=384

# HF Spaces default port; local compose overrides commands/ports
EXPOSE 7860 8000 8501

CMD ["streamlit", "run", "streamlit_app/app.py", \
     "--server.port=7860", \
     "--server.address=0.0.0.0", \
     "--browser.gatherUsageStats=false"]
