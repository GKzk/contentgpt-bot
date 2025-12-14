FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
COPY main.py .
COPY config.py .
COPY .env .

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "main.py"]
