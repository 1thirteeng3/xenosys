#!/bin/bash
# =============================================================================
# Pre-bundle script - Baixa dependências para instalação offline
# =============================================================================
# Uso: ./prebundle.sh [-f|--force] (execute uma vez durante build/release)
# Idempotente: Sai com sucesso se wheelhouse já existe (use -f para forçar)
# =============================================================================

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
WHEELHOUSE="$PROJECT_ROOT/wheelhouse"
REQUIREMENTS="$PROJECT_ROOT/requirements.txt"
FORCE=0

# Parse args
while [[ $# -gt 0 ]]; do
    case $1 in
        -f|--force)
            FORCE=1
            shift
            ;;
        *)
            echo "Unknown: $1"
            exit 1
            ;;
    esac
done

echo "=== Pre-bundle: Preparando dependências offline ==="
echo "Projeto: $PROJECT_ROOT"
echo "Wheelhouse: $WHEELHOUSE"
echo "Force: $FORCE"

# IDEMPOTENTE: Verificar se já existe
if [ $FORCE -eq 0 ] && [ -d "$WHEELHOUSE" ]; then
    COUNT=$(ls -1 "$WHEELHOUSE"/*.whl 2>/dev/null | wc -l)
    if [ "$COUNT" -gt 0 ]; then
        echo "=== wheelhouse já existe ($COUNT wheels) - abortando (use -f para forçar) ==="
        exit 0
    fi
fi

# Verificar requirements.txt
if [ ! -f "$REQUIREMENTS" ]; then
    echo "ERROR: requirements.txt não encontrado"
    exit 1
fi

# Criar diretório
mkdir -p "$WHEELHOUSE"

# Baixar dependências
echo "Baixando packages Python..."
pip download -r "$REQUIREMENTS" -d "$WHEELHOUSE" --no-deps 2>/dev/null || true
pip download -r "$REQUIREMENTS" -d "$WHEELHOUSE" 2>/dev/null || true

# Contar arquivos
COUNT=$(ls -1 "$WHEELHOUSE"/*.whl 2>/dev/null | wc -l)
echo "=== Pre-bundle concluído: $COUNT wheels salvos ==="

if [ "$COUNT" -eq 0 ]; then
    echo "WARNING: Nenhum wheel baixado. Verifique conexão internet."
    exit 1
fi

echo "Para instalar offline: make install"