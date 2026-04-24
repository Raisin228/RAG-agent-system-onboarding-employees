# Пока что не удалось развернуться полностью в compose -- полагаю это из-за нехватки ОЗУ

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip wheel "poetry==2.1.1"

RUN poetry config virtualenvs.create false

COPY pyproject.toml poetry.lock ./

RUN poetry install --no-root --only main


COPY . .

WORKDIR /app/finbridge

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
