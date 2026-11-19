FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY tests ./tests

# Fail the build if tests fail, same as the Go service.
RUN python -m pytest -q

# -u = unbuffered output, so logs show up in `docker compose logs` immediately.
CMD ["python", "-u", "-m", "app.main"]
