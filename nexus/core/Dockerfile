# =============================================================================
# XenoSys Core Dockerfile
# Python for agent orchestration, memory, and LLM operations
# =============================================================================

FROM python:3.13-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install uv for fast package management
RUN pip install uv

# Copy dependency files
COPY requirements.txt pyproject.toml ./

# Compile dependencies
RUN uv pip install --system --no-cache -r requirements.txt

# Production image
FROM python:3.13-slim AS production

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY requirements.txt pyproject.toml ./

# Install Python dependencies using uv (faster)
RUN pip install uv && \
    uv pip install --system --no-cache -r requirements.txt

# Copy source code
COPY nexus/ ./nexus/

# Create non-root user for security
RUN useradd -m -u 1000 xenosys && \
    chown -R xenosys:xenosys /app
USER xenosys

# Expose gRPC port
EXPOSE 50051

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:50051/health || exit 1

# Start via module
CMD ["python", "-m", "nexus.core"]