# =============================================================================
# XenoSys Core Dockerfile - Production Optimized
# Uses layer caching and static installation (no -e/ editable flag)
# =============================================================================

# -----------------------------------------------------------------------------
# Builder Stage: Compile dependencies
# -----------------------------------------------------------------------------
FROM python:3.13-slim AS builder

WORKDIR /app

# Install system dependencies needed for building
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast package management
RUN pip install --no-cache-dir uv

# Copy ONLY dependency files first (exploits Docker layer caching)
COPY pyproject.toml ./

# Install dependencies WITHOUT the project itself (no -e flag)
# This creates a static installation that doesn't depend on source
RUN uv pip install --system --no-cache-dir .

# -----------------------------------------------------------------------------
# Production Stage: Minimal runtime image
# -----------------------------------------------------------------------------
FROM python:3.13-slim AS production

WORKDIR /app

# Install minimal runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy only necessary files from builder
# No need to copy node_modules or build artifacts
COPY --from=builder /app /app

# Create non-root user for security (principle of least privilege)
RUN useradd -m -u 1000 xenosys && \
    chown -R xenosys:xenosys /app
USER xenosys

# Environment variables for production
ENV PYTHONUNBUFFERED=1
ENV GRPC_HOST=0.0.0.0
ENV TAURI_ENV=false
ENV LOG_LEVEL=INFO

# Expose gRPC port
EXPOSE 50051

# Health check for gRPC
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
  CMD python -c "import grpc; print('OK')" || exit 1

# Start application
CMD ["python", "-m", "nexus.core"]