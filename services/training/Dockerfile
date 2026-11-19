FROM python:3.13-slim

WORKDIR /app

# CPU-only PyTorch from PyTorch's own index: ~200MB instead of ~2.5GB of GPU libraries
# we don't need. Installed in its own layer so code changes never re-download it.
RUN pip install --no-cache-dir torch==2.7.1 --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY tests ./tests

# Includes test_learning: the image won't build if the model can't learn.
RUN python -m pytest -q

CMD ["python", "-u", "-m", "app.main"]
