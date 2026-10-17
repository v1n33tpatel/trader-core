FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TRADER_STATE_DB=/data/trader_state.db

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src/ ./src/
RUN pip install --no-cache-dir .

COPY main.py engine.py dashboard.html dashboard.css dashboard.js ./
COPY brokers/ ./brokers/
COPY core/ ./core/
COPY deploy/ ./deploy/
COPY feeds/ ./feeds/
COPY logo/ ./logo/
COPY models/ ./models/
COPY risk/ ./risk/
COPY strategies/ ./strategies/

RUN mkdir -p /data && chmod 777 /data

EXPOSE 5000

CMD ["python", "main.py"]
