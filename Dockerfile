# RAG Document Chatbot (API + Streamlit)

FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend
COPY streamlit_app ./streamlit_app
COPY .env.example .env.example

RUN mkdir -p uploads vector_store data

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV MAX_UPLOAD_SIZE_MB=40

EXPOSE 8000 8501

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
