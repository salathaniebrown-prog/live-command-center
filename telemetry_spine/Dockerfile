FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY eagle_eyes_telemetry_spine.py .
COPY main.py .

EXPOSE 8080

CMD ["python", "-u", "main.py"]
