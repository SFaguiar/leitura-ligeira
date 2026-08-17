FROM python:3.14.7-slim-bookworm@sha256:23c59390fc717bf09f9336908199a0ae75d9c4264bf296123f94ad772fea3b52

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.lock .
RUN python -m pip install --no-cache-dir --disable-pip-version-check -r requirements.lock

RUN addgroup --system leitura && adduser --system --ingroup leitura leitura

COPY --chown=leitura:leitura app ./app
COPY --chown=leitura:leitura scripts ./scripts
COPY --chown=leitura:leitura static ./static
RUN mkdir -p /app/data && chown leitura:leitura /app/data

USER leitura

EXPOSE 8000

CMD ["python", "scripts/run_server.py", "--lan"]
