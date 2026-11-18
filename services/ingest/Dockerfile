FROM python:3.13-slim

WORKDIR /app

# Install dependencies first, in their own layer. Docker caches layers, so
# editing your code later won't trigger a slow re-install.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY tests ./tests

EXPOSE 8001
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
