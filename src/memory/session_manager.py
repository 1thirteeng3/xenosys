"""
Q4: Stateful Memory System - Session Manager

Gerencia o estado entre sessões, mantendo variáveis em RAM
e persistindo via checkpointing com msgpack + lz4.

CRÍTICO: Proibido usar pickle - usa msgpack para segurança.
"""

import asyncio
import logging
import os
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

# Tentar importar lz4 (opcional)
try:
    import lz4.frame
    HAS_LZ4 = True
except ImportError:
    HAS_LZ4 = False
    logger.warning("lz4 não disponível - compressão desabilitada")

# --- CORREÇÃO: Lazy Import com Fail-Fast de Runtime ---
try:
    import msgpack
    HAS_MSGPACK = True
except ImportError:
    msgpack = None  # Lazy - não bloqueia importação
    HAS_MSGPACK = False


def _ensure_msgpack():
    """Fail-Fast: levanta RuntimeError só em runtime, não import."""
    global msgpack
    if msgpack is None:
        try:
            import msgpack as _mp
            msgpack = _mp
        except ImportError:
            raise RuntimeError(
                "msgpack é obrigatório para checkpoints. "
                "Execute: pip install msgpack"
            )
    return msgpack


# --- Constantes de Configuração ---
DEFAULT_CHECKPOINT_INTERVAL = 300  # 5 minutos
DEFAULT_TOKEN_LIMIT = 8192
DEFAULT_COMPRESSION_THRESHOLD = 0.80  # 80% do token limit
STATE_DIR = "/tmp/xenosys"  # tmpfs


@dataclass
class SessionState:
    """Estado de uma sessão."""
    session_id: str
    created_at: str
    updated_at: str
    checkpoint_count: int = 0
    variables: Dict[str, Any] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)
    history: List[Dict[str, Any]] = field(default_factory=list)
    is_active: bool = True


class SessionManager:
    """
    Gerenciador de estado de sessão persistente.
    
    Funcionalidades:
    - Variáveis em RAM (SessionState)
    - Checkpointing periódico com msgpack + lz4
    - Restore automático em novas sessões
    - Compressão de contexto quando > 80% token limit
    
    Arquitetura:
    SessionManager
    ├── SessionState (RAM)
    │   ├── variables: Dict[str, Any]
    │   ├── context: Dict[str, Any]
    │   └── history: List[Dict]
    ├── VariableRegistry
    └── Checkpoint Manager
        └── State files em /tmp/xenosys/
    """
    
    def __init__(
        self,
        checkpoint_interval: int = DEFAULT_CHECKPOINT_INTERVAL,
        token_limit: int = DEFAULT_TOKEN_LIMIT,
        compress_threshold: float = DEFAULT_COMPRESSION_THRESHOLD,
        state_dir: str = STATE_DIR,
        auto_restore: bool = True,
        tokenizer: Optional[Callable[[str], int]] = None  # Injetável (Q3 → Q4)
    ):
        self.checkpoint_interval = checkpoint_interval
        self.token_limit = token_limit
        self.compress_threshold = compress_threshold
        self.state_dir = state_dir
        self.auto_restore = auto_restore
        self._tokenizer = tokenizer  # Injeção de dependência
        
        self._sessions: Dict[str, SessionState] = {}
        self._active_session: Optional[str] = None
        self._checkpoint_tasks: Dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()
        
        # --- CORREÇÃO 2: Per-session locks para atomicidade ---
        self._session_locks: Dict[str, asyncio.Lock] = {}
        
        # Criar diretório de state (dinâmico via config)
        os.makedirs(state_dir, exist_ok=True)
        
        logger.info(
            f"SessionManager inicializado: "
            f"checkpoint={checkpoint_interval}s, "
            f"token_limit={token_limit}, "
            f"state_dir={state_dir}, "
            f"tokenizer={'injected' if tokenizer else 'heuristic'}"
        )
    
    # --- Criação de Sessão ---
    
    async def create_session(
        self,
        session_id: Optional[str] = None,
        restore_from: Optional[str] = None
    ) -> str:
        """
        Cria uma nova sessão.
        
        Args:
            session_id: ID opcional (gera se None)
            restore_from: ID de sessão para restaurar
            
        Returns:
            session_id da nova sessão
        """
        sid = session_id or str(uuid.uuid4())
        
        now = datetime.now(timezone.utc).isoformat()
        
        async with self._lock:
            # Verificar se já existe
            if sid in self._sessions:
                logger.warning(f"Sessão {sid} já existe")
                return sid
            
            # Restaurar de outra sessão se especificado
            variables = {}
            context = {}
            history = []
            
            if restore_from and restore_from in self._sessions:
                src = self._sessions[restore_from]
                variables = src.variables.copy()
                context = src.context.copy()
                history = src.history.copy()
                logger.info(f"Restaurando estado de {restore_from}")
            
            state = SessionState(
                session_id=sid,
                created_at=now,
                updated_at=now,
                variables=variables,
                context=context,
                history=history
            )
            
            self._sessions[sid] = state
            self._active_session = sid
            
            # Auto-restaurar de checkpoint se existir
            if self.auto_restore:
                await self._try_restore(sid)
            
            # Iniciar checkpoint periódico
            self._start_checkpoint(sid)
            
            logger.info(f"Sessão criada: {sid}")
            return sid
    
    async def _try_restore(self, session_id: str) -> bool:
        """Tenta restaurar de checkpoint."""
        checkpoint_file = self._get_checkpoint_path(session_id)
        
        if not checkpoint_file.exists():
            return False
        
        try:
            await self.restore_from_checkpoint(session_id)
            logger.info(f"Restaurado de checkpoint: {session_id}")
            return True
        except Exception as e:
            logger.error(f"Falha ao restaurar: {e}")
            return False
    
    # --- Gerenciamento de Sessão ---
    
    async def get_session(self, session_id: Optional[str] = None) -> Optional[SessionState]:
        """Obtém estado de uma sessão."""
        sid = session_id or self._active_session
        if not sid:
            return None
        return self._sessions.get(sid)
    
    async def set_active_session(self, session_id: str) -> bool:
        """Define sessão ativa."""
        if session_id not in self._sessions:
            return False
        self._active_session = session_id
        return True
    
    async def list_sessions(self) -> List[str]:
        """Lista IDs de sessões."""
        return list(self._sessions.keys())
    
    async def close_session(self, session_id: Optional[str] = None) -> bool:
        """Fecha uma sessão (para checkpoint e cleanup)."""
        sid = session_id or self._active_session
        if not sid or sid not in self._sessions:
            return False
        
        # Cancelar task de checkpoint
        if sid in self._checkpoint_tasks:
            self._checkpoint_tasks[sid].cancel()
            del self._checkpoint_tasks[sid]
        
        #Checkpoint final
        await self._write_checkpoint(sid)
        
        # Marcar como inativa
        self._sessions[sid].is_active = False
        
        if sid == self._active_session:
            self._active_session = None
        
        logger.info(f"Sessão fechada: {sid}")
        return True
    
    async def delete_session(self, session_id: str) -> bool:
        """Deleta uma sessão completamente."""
        await self.close_session(session_id)
        
        async with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                
                # Deletar checkpoint
                checkpoint_file = self._get_checkpoint_path(session_id)
                if checkpoint_file.exists():
                    checkpoint_file.unlink()
                
                logger.info(f"Sessão deletada: {session_id}")
                return True
        return False
    
    # --- Variáveis ---
    
    async def set_variable(
        self,
        name: str,
        value: Any,
        session_id: Optional[str] = None
    ) -> None:
        """Define uma variável na sessão."""
        sid = session_id or self._active_session
        if not sid or sid not in self._sessions:
            raise ValueError("Sessão não encontrada")
        
        state = self._sessions[sid]
        state.variables[name] = value
        state.updated_at = datetime.now(timezone.utc).isoformat()
        
        logger.debug(f"Variável definida: {name}")
    
    async def get_variable(
        self,
        name: str,
        session_id: Optional[str] = None,
        default: Any = None
    ) -> Any:
        """Obtém uma variável da sessão."""
        sid = session_id or self._active_session
        if not sid or sid not in self._sessions:
            return default
        
        return self._sessions[sid].variables.get(name, default)
    
    async def delete_variable(
        self,
        name: str,
        session_id: Optional[str] = None
    ) -> bool:
        """Remove uma variável."""
        sid = session_id or self._active_session
        if not sid or sid not in self._sessions:
            return False
        
        if name in self._sessions[sid].variables:
            del self._sessions[sid].variables[name]
            self._sessions[sid].updated_at = datetime.now(timezone.utc).isoformat()
            return True
        return False
    
    async def list_variables(
        self,
        session_id: Optional[str] = None
    ) -> List[str]:
        """Lista variáveis da sessão."""
        sid = session_id or self._active_session
        if not sid or sid not in self._sessions:
            return []
        return list(self._sessions[sid].variables.keys())
    
    # --- Contexto ---
    
    async def set_context(
        self,
        key: str,
        value: Any,
        session_id: Optional[str] = None
    ) -> None:
        """Define contexto da sessão."""
        sid = session_id or self._active_session
        if not sid or sid not in self._sessions:
            raise ValueError("Sessão não encontrada")
        
        state = self._sessions[sid]
        state.context[key] = value
        state.updated_at = datetime.now(timezone.utc).isoformat()
    
    async def get_context(
        self,
        key: str,
        session_id: Optional[str] = None,
        default: Any = None
    ) -> Any:
        """Obtém contexto."""
        sid = session_id or self._active_session
        if not sid or sid not in self._sessions:
            return default
        return self._sessions[sid].context.get(key, default)
    
    # --- Correções de Compressão ---
    
    def _estimate_tokens(self, text: str) -> int:
        """Estima tokens usando tokenizer injetado ou fallback."""
        if self._tokenizer:
            return self._tokenizer(text)
        return len(text.encode()) // 4  # Fallback bytes/4
    
    async def _compress_context_internal(self, state: SessionState) -> bool:
        """
        Compressão interna para uso em add_history.
        
        Versão light: não obtém lock (chamador deve ter lock).
        Usa slicing O(1) ao invés de set() O(N).
        """
        if not state.history:
            return False
        
        total = len(state.history)
        pinned_head = max(1, total // 10)  # 10% - PINNED
        pinned_tail = max(1, total // 5)   # 20% - PINNED
        
        # --- CORREÇÃO: Slicing O(1) ao invés de set() O(N) ---
        head = state.history[:pinned_head]
        tail = state.history[-pinned_tail:] if pinned_tail > 0 else []
        new_history = head + tail
        
        state.history = new_history
        state.context["_compressed"] = True
        state.context["_compression_method"] = "middle-out"
        state.context["_history_truncated"] = len(new_history)
        
        logger.info(
            f"Compressão proativa: {total}→{len(new_history)} "
            f"(head={pinned_head}, tail={pinned_tail})"
        )
        return True
    
    async def compress_context(
        self,
        session_id: Optional[str] = None
    ) -> bool:
        """
        Comprime contexto quando > threshold usando Middle-Out Truncation.
        
        CRÍTICO: Protege as primeiras mensagens (System Prompt + User Goal).
        Mantém as últimas mensagens (contexto imediato).
        Descarta apenas as intermediárias (tentativas do meio).
        
        Middle-Out:
        - [0:N] = PINNED (System Prompt, Goals) - NUNCA/delete
        - [N:M] = DISCARDABLE (tentativas, loops)
        - [M:] = ACTIVE (contexto recente) - PINNED
        """
        sid = session_id or self._active_session
        if not sid or sid not in self._sessions:
            return False
        
        state = self._sessions[sid]
        
        # --- CORREÇÃO 3: Usar tokenizer injetado ou fallback com alerta ---
        context_str = str(state.context)
        if self._tokenizer:
            estimated_tokens = self._tokenizer(context_str)
            token_method = "injected"
        else:
            estimated_tokens = len(context_str.encode()) // 4  # bytes → tokens
            token_method = "heuristic"
            logger.warning(
                f"Tokenização precisa indisponível. "
                f"Utilizando heurística de bytes (risk: context overflow). "
                f" Injete um tokenizer via SessionManager(tokenizer=...)"
            )
        
        if estimated_tokens < self.token_limit * self.compress_threshold:
            return False
        
        if not state.history:
            return False
        
        # --- CORREÇÃO 1: Middle-Out Truncation ---
        total = len(state.history)
        pinned_head = max(1, total // 10)  # Primeiro 10% - PINNED (System + Goals)
        pinned_tail = max(1, total // 5)   # Último 20% - PINNED (contexto recente)
        pinned_middle = pinned_head + pinned_tail
        
        pinned_indices = set(range(pinned_head)) | set(range(total - pinned_tail, total))
        
        # Criar novo histórico: apenas entradas pinneadas e intermediárias
        new_history = [state.history[i] for i in range(total) if i in pinned_indices]
        
        state.history = new_history
        state.context["_compressed"] = True
        state.context["_compression_method"] = "middle-out"
        state.context["_history_truncated"] = len(new_history)
        state.context["_token_method"] = token_method
        
        logger.info(
            f"Contexto comprimido: {total}→{len(new_history)} entradas "
            f"(pinned head={pinned_head}, tail={pinned_tail}, method={token_method})"
        )
        return True
    
    # --- Checkpoint ---
    
    def _get_checkpoint_path(self, session_id: str) -> Path:
        """Caminho do arquivo de checkpoint."""
        return Path(self.state_dir) / f"{session_id}.checkpoint"
    
    def _start_checkpoint(self, session_id: str) -> None:
        """Inicia task de checkpoint periódico."""
        
        async def checkpoint_loop():
            while session_id in self._sessions:
                await asyncio.sleep(self.checkpoint_interval)
                if session_id in self._sessions:
                    await self._write_checkpoint(session_id)
        
        task = asyncio.create_task(checkpoint_loop())
        self._checkpoint_tasks[session_id] = task
    
    async def _write_checkpoint(self, session_id: str) -> bool:
        """Escreve checkpoint para disco."""
        if session_id not in self._sessions:
            return False
        
        state = self._sessions[session_id]
        checkpoint_path = self._get_checkpoint_path(session_id)
        
        try:
            # Serializar para dicionário
            data = {
                "session_id": state.session_id,
                "created_at": state.created_at,
                "updated_at": state.updated_at,
                "checkpoint_count": state.checkpoint_count + 1,
                "variables": state.variables,
                "context": state.context,
                "history": state.history,
                "is_active": state.is_active
            }
            
            # Serializar com msgpack via _ensure_msgpack()
            mp = _ensure_msgpack()
            packed = mp.packb(data, use_bin_type=True)
            
            # Comprimir com lz4
            if HAS_LZ4:
                compressed = lz4.frame.compress(packed)
                to_write = compressed
            else:
                to_write = packed
            
            # Escrever atomically
            tmp_path = checkpoint_path.with_suffix('.tmp')
            tmp_path.write_bytes(to_write)
            tmp_path.replace(checkpoint_path)
            
            state.checkpoint_count += 1
            logger.debug(f"Checkpoint {state.checkpoint_count}: {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao escrever checkpoint: {e}")
            return False
    
    async def restore_from_checkpoint(self, session_id: str) -> bool:
        """Restaura de checkpoint."""
        checkpoint_path = self._get_checkpoint_path(session_id)
        
        if not checkpoint_path.exists():
            return False
        
        try:
            data = checkpoint_path.read_bytes()
            
            # Decomprimir
            if HAS_LZ4:
                try:
                    data = lz4.frame.decompress(data)
                except:
                    pass  # Não estava comprimido
            
            # Deserializar com msgpack via _ensure_msgpack()
            mp = _ensure_msgpack()
            unpacked = mp.unpackb(data, raw=False)
            
            # Criar/restaurar sessão
            if session_id not in self._sessions:
                state = SessionState(
                    session_id=session_id,
                    created_at=unpacked["created_at"],
                    updated_at=unpacked["updated_at"],
                    checkpoint_count=unpacked["checkpoint_count"],
                    variables=unpacked["variables"],
                    context=unpacked["context"],
                    history=unpacked["history"],
                    is_active=unpacked["is_active"]
                )
                self._sessions[session_id] = state
            else:
                state = self._sessions[session_id]
                state.variables = unpacked["variables"]
                state.context = unpacked["context"]
                state.history = unpacked["history"]
                state.updated_at = unpacked["updated_at"]
                state.checkpoint_count = unpacked["checkpoint_count"]
            
            logger.info(f"Restaurado: {session_id} (checkpoint #{state.checkpoint_count})")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao restaurar: {e}")
            return False
    
    # --- Histórico ---
    
    async def add_history(
        self,
        action: str,
        data: Dict[str, Any],
        session_id: Optional[str] = None
    ) -> None:
        """
        Adiciona entrada ao histórico com compressão proativa.
        
        CRÍTICO: Avalia PROJEÇÃO do estado futuro ANTES de inserir.
        Se (atual + nova) > 80% token limit, comprime primeiro.
        
       _atomic: Usa lock para prevenir race conditions.
        """
        sid = session_id or self._active_session
        if not sid or sid not in self._sessions:
            return
        
        # Obter lock da sessão (cria se não existir)
        session_lock = self._session_locks.get(sid)
        if session_lock is None:
            session_lock = asyncio.Lock()
            self._session_locks[sid] = session_lock
        
        async with session_lock:
            state = self._sessions[sid]
            
            # --- CORREÇÃO 1: Projeção de estado futuro ---
            entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "action": action,
                **data
            }
            
            # Estimar tokens da nova entrada
            new_entry_tokens = self._estimate_tokens(str(entry))
            current_tokens = self._estimate_tokens(str(state.context))
            
            # PROJEÇÃO: se exceder 80%, comprimir ANTES de inserir
            if (current_tokens + new_entry_tokens) > (self.token_limit * self.compress_threshold):
                logger.info(
                    f"Compressão proativa disparada: "
                    f"{current_tokens}+{new_entry_tokens} > {self.token_limit * 0.8}"
                )
                await self._compress_context_internal(state)
            
            # Inserir APÓS compressão
            state.history.append(entry)
            
            # Manter máximo 1000 entradas
            if len(state.history) > 1000:
                state.history = state.history[-1000:]
    
    # --- Estatísticas ---
    
    async def get_stats(
        self,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Retorna estatísticas."""
        sid = session_id or self._active_session
        
        if not sid or sid not in self._sessions:
            return {
                "active_sessions": len(self._sessions),
                "session_count": len(self._sessions)
            }
        
        state = self._sessions[sid]
        
        # Estimar tokens do contexto
        context_str = str(state.context)
        estimated_tokens = len(context_str) // 4
        
        return {
            "session_id": sid,
            "is_active": state.is_active,
            "variable_count": len(state.variables),
            "history_count": len(state.history),
            "checkpoint_count": state.checkpoint_count,
            "estimated_tokens": estimated_tokens,
            "token_limit": self.token_limit,
            "token_usage_pct": (estimated_tokens / self.token_limit) * 100,
            "created_at": state.created_at,
            "updated_at": state.updated_at
        }
    
    # --- Cleanup ---
    
    async def shutdown(self) -> None:
        """Finaliza o gerenciador (graceful shutdown)."""
        logger.info("Iniciando shutdown...")
        
        # Cancelar todas as tasks de checkpoint
        for task in self._checkpoint_tasks.values():
            task.cancel()
        self._checkpoint_tasks.clear()
        
        # Escrever checkpoints finais
        for sid in list(self._sessions.keys()):
            await self.close_session(sid)
        
        logger.info("Shutdown completo")
    
    # --- Properties ---
    
    @property
    def active_session_id(self) -> Optional[str]:
        return self._active_session
    
    @property
    def session_count(self) -> int:
        return len(self._sessions)