# =============================================================================
# XenoSys Gateway Dockerfile - Optimized Build with Backup & Restore Strategy
# =============================================================================

FROM node:20-alpine AS builder
WORKDIR /app

COPY package*.json ./

# 1. Higieniza o package.json (remove referências de workspace que quebram o build isolado)
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

# 2. Instala dependências necessárias
RUN npm install uuid --save
RUN npm install --include=dev

# 3. Salva uma cópia de segurança do package.json limpo
RUN cp package.json package-pristine.json

# 4. Copia o código-fonte
COPY . .

# 5. Restaura o arquivo higienizado por cima do código copiado
RUN mv package-pristine.json package.json

# 6. Ajustes de código e compilação
RUN sed -i '/hono\/ws/d' src/gateway/server.ts || true
RUN sed -i "s/c.set('requestId', uuid());/(c as any).set('requestId', uuid());/g" src/gateway/server.ts || true
RUN npm run build
RUN node -e "const fs=require('fs'); fs.cpSync('src/proto', 'dist/proto', {recursive: true});"

# 7. Remove dependências de desenvolvimento para reduzir a imagem
RUN npm prune --omit=dev

# -----------------------------------------------------------------------------
FROM node:20-alpine AS production
WORKDIR /app

ENV NODE_ENV=production
ENV HOST=0.0.0.0
ENV PORT=3000

# Copia apenas o necessário do builder
COPY --from=builder /app/package.json ./package.json
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/node_modules ./node_modules

EXPOSE 3000 50051

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD wget -q --spider http://localhost:3000/health || exit 1

CMD ["npm", "start"]
