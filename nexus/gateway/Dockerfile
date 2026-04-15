# =============================================================================
# XenoSys Gateway Dockerfile - Pure Production Build
# =============================================================================

FROM node:20-alpine AS builder
WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

# Compile TypeScript and copy the protos
RUN npm run build
RUN node -e "const fs=require('fs'); fs.cpSync('src/proto', 'dist/proto', {recursive: true});"

FROM node:20-alpine AS production
WORKDIR /app

ENV NODE_ENV=production
ENV HOST=0.0.0.0
ENV PORT=3000

COPY --from=builder /app/package.json ./package.json
COPY --from=builder /app/dist ./dist

# Clean install for production only
RUN npm install --omit=dev

EXPOSE 3000 50051

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD wget -q --spider http://localhost:3000/health || exit 1

CMD ["npm", "start"]
