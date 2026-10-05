FROM python:3.14.8-slim-bookworm@sha256:c8137f4c460908c8763f281c8f22c431eb5c538514ba9553fc3a89c06b7cfb88

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
