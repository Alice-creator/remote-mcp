FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY gateway/ ./gateway/
COPY mocks/ ./mocks/
COPY run_gateway.py ./

CMD ["python", "run_gateway.py"]
