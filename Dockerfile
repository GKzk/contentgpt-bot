FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
COPY main.py .
COPY config.py .
COPY yandex_kassa_handler.py .

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "main.py"]
