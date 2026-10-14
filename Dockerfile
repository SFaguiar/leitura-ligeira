FROM python:3.15.0rc3-slim-bookworm@sha256:ea93de1a70a03fffd10ad8cfde8f4ba969fe2658f0578af02855d1d32f49e6c2

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
