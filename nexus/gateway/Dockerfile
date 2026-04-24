# =============================================================================
# XenoSys Gateway Dockerfile - Strict Quality Build
# =============================================================================

FROM node:20-alpine AS builder
WORKDIR /app

COPY package*.json ./

# 1. Higieniza as dependências "workspace:*" quebradas
RUN node -e "\
  const fs = require('fs'); \
  if (fs.existsSync('package-lock.json')) fs.unlinkSync('package-lock.json'); \
  const pkg = JSON.parse(fs.readFileSync('package.json', 'utf8')); \
  ['dependencies', 'devDependencies'].forEach(t => { \
    if(pkg[t]) Object.keys(pkg[t]).forEach(k => { \
      if(typeof pkg[t][k] === 'string' && pkg[t][k].includes('workspace:')) delete pkg[t][k]; \
    }); \
  }); \
  fs.writeFileSync('package.json', JSON.stringify(pkg, null, 2)); \
"

# 2. Instala os pacotes, incluindo os pacotes tipados que faltavam
RUN npm install uuid zod yaml --save
RUN npm install --include=dev

# 3. Restaurações de segurança
RUN cp package.json package-pristine.json
COPY . .
RUN mv package-pristine.json package.json

# 4. COMPILAÇÃO ESTREITA E RIGOROSA (SEM TS-IGNORE!)
RUN npm run build
RUN node -e "const fs=require('fs'); fs.cpSync('src/proto', 'dist/proto', {recursive: true});"

# 5. Prune
RUN npm prune --omit=dev

# -----------------------------------------------------------------------------
FROM node:20-alpine AS production
WORKDIR /app

ENV NODE_ENV=production
ENV HOST=0.0.0.0
ENV PORT=3000

COPY --from=builder /app/package.json ./package.json
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/node_modules ./node_modules

EXPOSE 3000 50051

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD wget -q --spider http://localhost:3000/health || exit 1

CMD ["npm", "start"]
