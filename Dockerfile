FROM python:3.13.11-slim-bookworm@sha256:20080e807bfc404f8450b185cf0fc95d553462673598549613735f70a5b4d5d0

WORKDIR /app

COPY requirements.lock .
RUN python -m pip install --no-cache-dir --disable-pip-version-check -r requirements.lock

COPY app ./app
COPY scripts ./scripts
COPY static ./static

EXPOSE 8000

CMD ["python", "scripts/run_server.py", "--lan"]
