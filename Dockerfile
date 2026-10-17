FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

ARG INSTALL_NEURAL_EMBEDDINGS=0

WORKDIR /app

COPY requirements.txt requirements-embeddings.txt ./
RUN python -m pip install --upgrade pip && \
    if [ "$INSTALL_NEURAL_EMBEDDINGS" = "1" ]; then \
        python -m pip install -r requirements-embeddings.txt; \
    else \
        python -m pip install -r requirements.txt; \
    fi

COPY . .

EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
