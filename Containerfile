FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src/ ./src/
RUN pip install --no-cache-dir .

COPY main.py dashboard.html dashboard.css dashboard.js ./
COPY brokers/ ./brokers/
COPY logo/ ./logo/

EXPOSE 5000

CMD ["python", "main.py"]
