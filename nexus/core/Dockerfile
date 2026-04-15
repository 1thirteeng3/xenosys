# =============================================================================
# XenoSys Core Dockerfile - Final Runtime Fix
# =============================================================================

FROM python:3.11-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --no-cache-dir hatchling
RUN pip install --no-cache-dir .

# Recria a estrutura exata de módulos do Python
COPY . ./nexus/core/

# Garante que o Python reconheça as pastas como pacotes
RUN touch ./nexus/__init__.py ./nexus/core/__init__.py

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

EXPOSE 50051

# O ALVO EXATO: Inicia a aplicação apontando para app.py
CMD ["python", "-m", "nexus.core.app"]
