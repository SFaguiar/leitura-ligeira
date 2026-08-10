FROM python:3.14.0-slim-bookworm@sha256:d13fa0424035d290decef3d575cea23d1b7d5952cdf429df8f5542c71e961576

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
