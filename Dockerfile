FROM python:3.13.11-slim-bookworm@sha256:20080e807bfc404f8450b185cf0fc95d553462673598549613735f70a5b4d5d0

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
