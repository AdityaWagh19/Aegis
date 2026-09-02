# Aegis API container (docker-compose service `api`, per project-context/deploy.md Step 3).
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY compliance_config.yaml ./
COPY api/ api/
COPY core/ core/
COPY models/ models/
COPY services/ services/
COPY workers/ workers/
COPY observability/ observability/

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
