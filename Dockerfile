FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY shared/ ./shared/
COPY gateway/ ./gateway/
COPY worker/ ./worker/
COPY run_gateway.py run_worker.py ./

# Default: run worker. Override with CMD at deploy time.
CMD ["python", "run_worker.py"]
