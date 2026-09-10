FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    HF_HOME=/app/.cache/huggingface

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Keep pinned model weights in the image while MLS-derived indexes remain runtime mounts.
RUN python -c "from sentence_transformers import CrossEncoder, SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2', revision='1110a243fdf4706b3f48f1d95db1a4f5529b4d41'); CrossEncoder('cross-encoder/ms-marco-MiniLM-L6-v2', revision='233902d25c440f23af6f7d6e94d2946bac0bee0a')"

COPY src ./src
COPY data/processed/taxonomy.json data/processed/taxonomy.json
COPY data/processed/valid_cities.json data/processed/valid_cities.json

EXPOSE 8000

CMD ["uvicorn", "src.real_estate_nlp.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
