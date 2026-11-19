FROM python:3.13-slim

WORKDIR /app

# CPU-only PyTorch first, so sentence-transformers doesn't pull the 2.5 GB GPU build.
RUN pip install --no-cache-dir torch==2.7.1 --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download CLIP (~600 MB) at BUILD time and bake it into the image. Containers
# then start without internet access and never re-download it. This layer is
# cached, so code changes don't repeat the download.
ENV HF_HOME=/models
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('clip-ViT-B-32', device='cpu')"

COPY app ./app
COPY tests ./tests
# Tests use a fake encoder, so they run fast and don't depend on the model.
RUN python -m pytest -q

# Set AFTER the tests: the running service uses real CLIP, offline.
ENV EMBEDDER=clip HF_HUB_OFFLINE=1

EXPOSE 8001
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
