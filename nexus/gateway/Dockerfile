# =============================================================================
# XenoSys Gateway Dockerfile - Production Optimized
# Uses multi-stage build with proper layer caching
# =============================================================================

# -----------------------------------------------------------------------------
# Builder Stage: Compile TypeScript
# -----------------------------------------------------------------------------
FROM node:22-alpine AS builder

WORKDIR /app

# Copy package files first (exploits Docker layer caching)
COPY package*.json ./
COPY tsconfig.json ./

# Install ALL dependencies (dev + prod for build)
RUN npm ci

# Copy source code
COPY src/ ./src/

# Build TypeScript
RUN npm run build

# -----------------------------------------------------------------------------
# Production Stage: Minimal runtime image
# -----------------------------------------------------------------------------
FROM node:22-alpine AS production

WORKDIR /app

# Install production dependencies only
COPY package*.json ./
RUN npm ci --only=production

# Copy built output from builder (not source code)
COPY --from=builder /app/dist/ ./dist/
COPY --from=builder /app/node_modules/ ./node_modules/

# Copy proto files
COPY src/proto/ ./dist/proto/

# Environment variables for production
ENV NODE_ENV=production
ENV HOST=0.0.0.0
ENV PORT=3000

# Expose ports
EXPOSE 3000 50051

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD wget -q --spider http://localhost:3000/health || exit 1

# Start application
CMD ["npm", "start"]