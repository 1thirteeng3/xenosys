# =============================================================================
# XenoSys Gateway Dockerfile - Backup & Restore Strategy
# =============================================================================

FROM node:20-alpine AS builder
WORKDIR /app

COPY package*.json ./

# 1. Higieniza o package.json uma ÚNICA vez
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

# 2. Instala as dependências e o uuid no arquivo já limpo
RUN npm install uuid --save
RUN npm install --include=dev

# 3. A MÁGICA: Salva uma cópia de segurança do package.json perfeito
RUN cp package.json package-pristine.json

# 4. Copia o código da sua máquina (isso traz o arquivo sujo de volta)
COPY . .

# 5. A MÁGICA 2: Restaura o nosso arquivo perfeito por cima do arquivo sujo!
RUN mv package-pristine.json package.json

# 6. Resolve imports e compila o projeto
RUN sed -i '/hono\/ws/d' src/gateway/server.ts || true
RUN sed -i "s/c.set('requestId', uuid());/(c as any).set('requestId', uuid());/g" src/gateway/server.ts || true
RUN npm run build
RUN node -e "const fs=require('fs'); fs.cpSync('src/proto', 'dist/proto', {recursive: true});"

# 7. Agora o prune lê o arquivo perfeito e funciona 100%
RUN npm prune --omit=dev

# -----------------------------------------------------------------------------
FROM node:20-alpine AS production
WORKDIR /app

ENV NODE_ENV=production
ENV HOST=0.0.0.0
ENV PORT=3000

# Copia os artefatos limpos para a imagem final
COPY --from=builder /app/package.json ./package.json
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/node_modules ./node_modules

EXPOSE 3000 50051

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD wget -q --spider http://localhost:3000/health || exit 1

CMD ["npm", "start"]
