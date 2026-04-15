# =============================================================================
# XenoSys Gateway Dockerfile - Production Optimized
# =============================================================================

# -----------------------------------------------------------------------------
# Builder Stage: Compile TypeScript
# -----------------------------------------------------------------------------
FROM node:20-alpine AS builder
WORKDIR /app

# Copia apenas os manifestos primeiro para aproveitar o cache do Docker
COPY package*.json ./

# -----------------------------------------------------------------------------
# HOTFIX ARQUITETURAL: Sanitização de Ghost Dependencies
# Remove pacotes 'workspace:*' com segurança sem quebrar a sintaxe JSON.
# -----------------------------------------------------------------------------
RUN node -e "\
  const fs = require('fs'); \
  const pkg = JSON.parse(fs.readFileSync('package.json', 'utf8')); \
  ['dependencies', 'devDependencies'].forEach(type => { \
    if (pkg[type]) { \
      for (const key in pkg[type]) { \
        if (pkg[type][key].includes('workspace:')) { \
          console.log('Removendo ghost dependency:', key); \
          delete pkg[type][key]; \
        } \
      } \
    } \
  }); \
  fs.writeFileSync('package.json', JSON.stringify(pkg, null, 2)); \
"

# Instala as dependências reais (agora sem o erro 404 do acp-proto)
RUN npm install

# Copia o código fonte (incluindo a pasta src/proto que já tem o que precisamos)
COPY . .

# Compila o TypeScript e os Protos
RUN npm run build

# -----------------------------------------------------------------------------
# Production Stage: Minimal runtime image
# -----------------------------------------------------------------------------
FROM node:20-alpine AS production
WORKDIR /app

# Variáveis de ambiente
ENV NODE_ENV=production
ENV HOST=0.0.0.0
ENV PORT=3000

# Copia o package.json (já higienizado pelo stage anterior)
COPY --from=builder /app/package.json ./package.json
COPY --from=builder /app/dist ./dist

# Instala apenas as dependências de produção para manter a imagem leve
RUN npm install --omit=dev

# Expõe as portas HTTP/WS e gRPC
EXPOSE 3000 50051

# Health check validando o endpoint que criamos
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD wget -q --spider http://localhost:3000/health || exit 1

CMD ["npm", "start"]
