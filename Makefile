# =============================================================================
# XenoSys Makefile - Instalação Offline-First (v1.1 FINAL)
# =============================================================================
#
# Objetivo: Automatizar a instalação e validação de pré-requisitos
#          de forma idempotente (silencia erros se já configurado)
#
# OFFLINE-FIRST: Prioriza wheelhouse local, faz fallback para PyPI com AVISO explícito
#
# Uso:
#   make install    - Instala todas as dependências
#   make validate - Valida pré-requisitos
#   make clean    - Limpa artefatos
#   make test    - Executa testes unitários
#   make prebundle - Baixa dependências para wheelhouse/
# =============================================================================

.PHONY: install validate clean test prebundle install_deps

# =============================================================================
# CONFIGURATION
# =============================================================================

PROJECT_ROOT := /workspace/project/xenosys
PYTHON := python3
PIP := pip3
VENV_PATH := $(PROJECT_ROOT)/venv
REQUIREMENTS := $(PROJECT_ROOT)/requirements.txt
WHEELHOUSE := $(PROJECT_ROOT)/wheelhouse

# Directories
DATA_DIR := /tmp/xenosys

# Colors
YELLOW := \033[0;33m
GREEN := \033[0;32m
RED := \033[0;31m
RESET := \033[0m

# =============================================================================
# TARGETS
# =============================================================================

# -----------------------------------------------------------------------------
# install: Instala todas as dependências (offline-first com fallback aviso)
# -----------------------------------------------------------------------------
install: validate venv install_deps data_dir
	@echo "$(GREEN)XenoSys instalado com sucesso$(RESET)"
	@echo "Execute: python3 xenosys_cli.py start"

# -----------------------------------------------------------------------------
# install_deps: Install packages (OFFLINE-FIRST com fallback AVISO)
# -----------------------------------------------------------------------------
install_deps:
	@echo "Verificando diretório wheelhouse..."
	@if [ -d $(WHEELHOUSE) ] && [ $$(ls -1 $(WHEELHOUSE)/*.whl 2>/dev/null | wc -l) -gt 0 ]; then \
		echo "[OFFLINE] wheelhouse encontrado. Instalando via arquivos locais..."; \
		$(VENV_PATH)/bin/pip install --no-index --find-links $(WHEELHOUSE) -r $(REQUIREMENTS); \
	else \
		echo "[ONLINE] AVISO: wheelhouse ausente/incompleto."; \
		echo "AVISO: Fazendo fallback para PyPI. Conexões de rede serão iniciadas..."; \
		$(VENV_PATH)/bin/pip install --upgrade pip wheel setuptools; \
		$(VENV_PATH)/bin/pip install -r $(REQUIREMENTS); \
	fi

# -----------------------------------------------------------------------------
# validate: Check prerequisites (silencia erros se já OK)
# -----------------------------------------------------------------------------
validate:
	@echo "Validando pré-requisitos..."
	@-$(PYTHON) $(PROJECT_ROOT)/check_docker.py 2>/dev/null || echo "[AVISO] Docker não validado - continuando..."
	@echo "$(GREEN)Validação OK$(RESET)"

# -----------------------------------------------------------------------------
# venv: Create sealed virtual environment
# -----------------------------------------------------------------------------
venv:
	@echo "Criando virtual environment..."
	@[ -d $(VENV_PATH) ] || $(PYTHON) -m venv $(VENV_PATH)

# -----------------------------------------------------------------------------
# data_dir: Create data directory
# -----------------------------------------------------------------------------
data_dir:
	@echo "Criando diretório de dados..."
	@mkdir -p $(DATA_DIR)
	@echo "$(GREEN)Diretório $(DATA_DIR) criado$(RESET)"

# -----------------------------------------------------------------------------
# prebundle: Baixa dependências para modo offline
# -----------------------------------------------------------------------------
prebundle:
	@echo "Executando prebundle..."
	@bash $(PROJECT_ROOT)/prebundle.sh

# -----------------------------------------------------------------------------
# clean: Remove artifacts
# -----------------------------------------------------------------------------
clean:
	@echo "Removendo artefatos..."
	@rm -rf $(VENV_PATH)
	@rm -f $(PROJECT_ROOT)/.env
	@echo "$(GREEN)Artefatos removidos$(RESET)"

# -----------------------------------------------------------------------------
# test: Run unit tests
# -----------------------------------------------------------------------------
test:
	@echo "Executando testes..."
	@cd $(PROJECT_ROOT) && $(PYTHON) -m pytest tests/unit/ -v --tb=short

# -----------------------------------------------------------------------------
# status: Quick status check
# -----------------------------------------------------------------------------
status:
	@echo "Verificando status..."
	@$(PYTHON) $(PROJECT_ROOT)/xenosys_cli.py status