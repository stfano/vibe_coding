FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
COPY requirements-semantic.txt .
RUN pip install --no-cache-dir -r requirements.txt
ARG INSTALL_SEMANTIC_EMBEDDINGS=true
RUN if [ "$INSTALL_SEMANTIC_EMBEDDINGS" = "true" ]; then pip install --no-cache-dir -r requirements-semantic.txt; fi

COPY app ./app

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
