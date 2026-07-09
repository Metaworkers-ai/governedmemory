# GovernedMemory API server (E7) — self-hosted REST API.
#
# Build from the repo root, not this directory, so it can COPY both core/
# and api/:
#   docker build -f deploy/Dockerfile -t governedmemory-api .
# Or via docker compose, which does this automatically:
#   docker compose -f deploy/docker-compose.yml up -d

FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml requirements-core.txt requirements-api.txt ./
RUN pip install --no-cache-dir -r requirements-core.txt -r requirements-api.txt

COPY core/ core/
COPY api/ api/
RUN pip install --no-cache-dir --no-deps -e .

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
