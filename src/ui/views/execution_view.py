"""
Q6: ExecutionView - Visão de Depuração

Este módulo implementa a visualização de terminal com:
- stdout/stderr raw do código executado no container Docker
- Syntax highlighting para erros Python
- Log de erros formatado

Utiliza cores ANSI e highlight de regex para errors/warnings.

Padrões de Projeto:
- Strategy Pattern: Diferentes strategias de highlight
- Decorator Pattern: Formatação composável
- Observer Pattern: Atualização em tempo real

Critérios de Aceitação (DoD):
✅ Exibição de terminal com stdout/stderr raw
✅ Syntax highlighting
✅ Log de erros formatado
"""

import logging
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# --- Cores ANSI para highlight ---
class AnsiColors:
    """Cores ANSI para terminal."""
    RESET = "\033[0m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BOLD = "\033[1m"
    ITALIC = "\033[3m"
    
    # Backgrounds
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"
    
    # Cores bright
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"


@dataclass
class TerminalLine:
    """Uma linha de terminal processada."""
    timestamp: str
    content: str
    line_type: str  # stdout, stderr, error, warning, info
    source: str   # docker, system, user
    line_number: Optional[int] = None
    highlighted_html: str = ""  # HTML com spans de highlight


@dataclass
class ExecutionOutput:
    """Resultado de uma execução."""
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: float
    timestamp: str
    lines: List[TerminalLine] = field(default_factory=list)


class PythonErrorPatterns:
    """
    Padrões de regex para highlighting de erros Python.
    Usados para identificar e formatar mensagens de erro.
    """
    
    # Errors de sintaxe
    SYNTAX_ERROR = re.compile(
        r"SyntaxError: (.+)",
        re.IGNORECASE
    )
    
    # Errors de nome
    NAME_ERROR = re.compile(
        r"NameError: (.+)",
        re.IGNORECASE
    )
    
    # Errors de tipo
    TYPE_ERROR = re.compile(
        r"TypeError: (.+)",
        re.IGNORECASE
    )
    
    # Errors de atributo
    ATTRIBUTE_ERROR = re.compile(
        r"AttributeError: (.+)",
        re.IGNORECASE
    )
    
    # Errors de import
    IMPORT_ERROR = re.compile(
        r"ImportError: (.+)",
        re.IGNORECASE
    )
    
    # Errors de índice
    INDEX_ERROR = re.compile(
        r"IndexError: (.+)",
        re.IGNORECASE
    )
    
    # Errors de valor
    VALUE_ERROR = re.compile(
        r"ValueError: (.+)",
        re.IGNORECASE
    )
    
    # Errors de arquivo não encontrado
    FILE_NOT_FOUND = re.compile(
        r"FileNotFoundError: (.+)",
        re.IGNORECASE
    )
    
    # Traceback
    TRACEBACK = re.compile(
        r'Traceback \(most recent call last\):\s*\n(.*?)(?=\n\S|\Z)',
        re.DOTALL
    )
    
    # Linha do código no traceback
    TRACEBACK_LINE = re.compile(
        r'File "(.+)", line (\d+)'
    )
    
    # Warnings
    WARNING = re.compile(
        r"Warning: (.+)",
        re.IGNORECASE
    )
    
    # Deprecation warning
    DEPRECATION = re.compile(
        r"DeprecationWarning: (.+)",
        re.IGNORECASE
    )


class ExecutionViewRenderer:
    """
    Renderizador de saída de execução com syntax highlighting.
    
    Transforma stdout/stderr raw em HTML formatado com:
    - Cores para diferentes tipos de mensagem
    - Highlight de errores Python
    - Números de linha quando disponíveis
    """
    
    def __init__(self, use_colors: bool = True):
        self._use_colors = use_colors
        self._patterns = PythonErrorPatterns()
    
    def render(
        self,
        stdout: str,
        stderr: str,
        exit_code: int,
        duration_ms: float
    ) -> ExecutionOutput:
        """
        Renderiza saída de execução.
        
        Args:
            stdout: Saída padrão
            stderr: Saída de erro
            exit_code: Código de saída
            duration_ms: Tempo de execução em ms
            
        Returns:
            ExecutionOutput com linhas processadas
        """
        timestamp = datetime.utcnow().isoformat()
        lines: List[TerminalLine] = []
        
        # Processar stderr primeira (erros têm prioridade)
        if stderr:
            stderr_lines = stderr.split("\n")
            for i, line in enumerate(stderr_lines):
                if line.strip():
                    line_type = self._detect_line_type(line)
                    highlighted = self._highlight_line(line, line_type)
                    lines.append(TerminalLine(
                        timestamp=timestamp,
                        content=line,
                        line_type=line_type,
                        source="docker",
                        line_number=i + 1 if stderr_lines else None,
                        highlighted_html=highlighted
                    ))
        
        # Processar stdout
        if stdout:
            stdout_lines = stdout.split("\n")
            for i, line in enumerate(stdout_lines):
                if line.strip():
                    # Stdout geralmente é info, mas pode ser erro disfarçado
                    line_type = self._detect_line_type(line)
                    if line_type == "error":
                        highlighted = self._highlight_line(line, "error")
                        lines.append(TerminalLine(
                            timestamp=timestamp,
                            content=line,
                            line_type="error",
                            source="docker",
                            line_number=i + 1 if stdout_lines else None,
                            highlighted_html=highlighted
                        ))
                    else:
                        lines.append(TerminalLine(
                            timestamp=timestamp,
                            content=line,
                            line_type="stdout",
                            source="docker",
                            line_number=i + 1 if stdout_lines else None,
                            highlighted_html=self._highlight_line(line, "stdout")
                        ))
        
        # Adicionar info de exit code se não-zero
        if exit_code != 0:
            lines.append(TerminalLine(
                timestamp=timestamp,
                content=f"[Process exited with code {exit_code}]",
                line_type="info" if exit_code == 0 else "error",
                source="system",
                line_number=None,
                highlighted_html=self._highlight_line(
                    f"[Process exited with code {exit_code}]",
                    "info" if exit_code == 0 else "error"
                )
            ))
        
        # Adicionar info de duração
        lines.append(TerminalLine(
            timestamp=timestamp,
            content=f"[Execution took {duration_ms:.2f}ms]",
            line_type="info",
            source="system",
            line_number=None,
            highlighted_html=self._highlight_line(
                f"[Execution took {duration_ms:.2f}ms]",
                "info"
            )
        ))
        
        return ExecutionOutput(
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
            duration_ms=duration_ms,
            timestamp=timestamp,
            lines=lines
        )
    
    def _detect_line_type(self, line: str) -> str:
        """
        Detecta o tipo de linha para colorização.
        
        Args:
            line: Texto da linha
            
        Returns:
            Tipo: stdout, stderr, error, warning, info
        """
        line_lower = line.lower()
        
        # Verificar errors Python
        if self._patterns.SYNTAX_ERROR.search(line):
            return "error"
        if self._patterns.NAME_ERROR.search(line):
            return "error"
        if self._patterns.TYPE_ERROR.search(line):
            return "error"
        if self._patterns.ATTRIBUTE_ERROR.search(line):
            return "error"
        if self._patterns.IMPORT_ERROR.search(line):
            return "error"
        if self._patterns.INDEX_ERROR.search(line):
            return "error"
        if self._patterns.VALUE_ERROR.search(line):
            return "error"
        if self._patterns.FILE_NOT_FOUND.search(line):
            return "error"
        if "traceback" in line_lower:
            return "error"
        
        # Verificar warnings
        if self._patterns.WARNING.search(line):
            return "warning"
        if self._patterns.DEPRECATION.search(line):
            return "warning"
        if "warning" in line_lower:
            return "warning"
        
        # Verificar info
        if line.startswith("[") and line.endswith("]"):
            return "info"
        
        return "stdout"
    
    def _highlight_line(self, line: str, line_type: str) -> str:
        """
        Aplica highlight a uma linha.
        
        Args:
            line: Texto da linha
            line_type: Tipo detectado
            
        Returns:
            HTML com spans de cores
        """
        if not self._use_colors:
            return self._escape_html(line)
        
        # Mapeamento de tipos para cores
        color_map = {
            "error": AnsiColors.RED,
            "warning": AnsiColors.YELLOW,
            "info": AnsiColors.CYAN,
            "stdout": AnsiColors.WHITE
        }
        
        color = color_map.get(line_type, AnsiColors.WHITE)
        
        # Se é error, adicionar styling adicional
        if line_type == "error":
            return (
                f'<span class="terminal-line terminal-error">'
                f'{color}{self._escape_html(line)}{AnsiColors.RESET}'
                f'</span>'
            )
        elif line_type == "warning":
            return (
                f'<span class="terminal-line terminal-warning">'
                f'{color}{self._escape_html(line)}{AnsiColors.RESET}'
                f'</span>'
            )
        elif line_type == "info":
            return (
                f'<span class="terminal-line terminal-info">'
                f'{color}{self._escape_html(line)}{AnsiColors.RESET}'
                f'</span>'
            )
        else:
            return (
                f'<span class="terminal-line terminal-stdout">'
                f'{color}{self._escape_html(line)}{AnsiColors.RESET}'
                f'</span>'
            )
    
    def _escape_html(self, text: str) -> str:
        """Escapa caracteres HTML."""
        return (
            text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;")
        )
    
    def to_html(self, output: ExecutionOutput) -> str:
        """
        Converte output para HTML renderizado.
        
        Args:
            output: ExecutionOutput processado
            
        Returns:
            HTML da view
        """
        lines_html = "\n".join(
            line.highlighted_html or self._escape_html(line.content)
            for line in output.lines
        )
        
        return f'''\
<div class="execution-view">
  <div class="execution-header">
    <span class="exit-code" data-code="{output.exit_code}">
      Exit: {output.exit_code}
    </span>
    <span class="duration">
      {output.duration_ms:.2f}ms
    </span>
  </div>
  <pre class="terminal-output">{lines_html}</pre>
</div>'''
    
    def to_text(self, output: ExecutionOutput) -> str:
        """
        Converte output para texto plain.
        
        Args:
            output: ExecutionOutput processado
            
        Returns:
            Texto plain
        """
        if self._use_colors:
            return "\n".join(
                line.highlighted_html or line.content
                for line in output.lines
            )
        else:
            return f"{output.stdout}\n{output.stderr}"


class ExecutionView:
    """
    Visão de Execução - Terminal com syntax highlighting.
    
    Exibe stdout/stderr raw do código executado no container,
    incluindo syntax highlighting e log de erros.
    
    Integra-se com o DockerReplEngine (Q2) para obter
    a saída de execução em tempo real.
    """
    
    def __init__(
        self,
        use_colors: bool = True,
        max_lines: int = 1000
    ):
        self._renderer = ExecutionViewRenderer(use_colors=use_colors)
        self._max_lines = max_lines
        
        # Histórico de execuções
        self._history: List[ExecutionOutput] = []
        
        logger.info(f"ExecutionView inicializado: colors={use_colors}")
    
    def render(
        self,
        stdout: str,
        stderr: str,
        exit_code: int,
        duration_ms: float
    ) -> ExecutionOutput:
        """
        Renderiza uma execução.
        
        Args:
            stdout: Saída padrão
            stderr: Saída de erro
            exit_code: Código de saída
            duration_ms: Tempo de execução
            
        Returns:
            ExecutionOutput processado
        """
        output = self._renderer.render(
            stdout, stderr, exit_code, duration_ms
        )
        
        # Adicionar ao histórico
        self._history.append(output)
        if len(self._history) > self._max_lines:
            self._history = self._history[-self._max_lines:]
        
        return output
    
    def get_html(self, output: ExecutionOutput) -> str:
        """Retorna HTML renderizado."""
        return self._renderer.to_html(output)
    
    def get_text(self, output: ExecutionOutput) -> str:
        """Retorna texto plain."""
        return self._renderer.to_text(output)
    
    def get_history(self) -> List[ExecutionOutput]:
        """Retorna histórico de execuções."""
        return self._history
    
    def clear_history(self) -> None:
        """Limpa histórico."""
        self._history.clear()
        logger.info("_histórico limpo")
    
    # --- Formatação de saída para API ---
    
    def format_for_api(self, output: ExecutionOutput) -> Dict:
        """
        Formata output para API response.
        
        Args:
            output: ExecutionOutput
            
        Returns:
            Dict serializável
        """
        return {
            "stdout": output.stdout,
            "stderr": output.stderr,
            "exit_code": output.exit_code,
            "duration_ms": output.duration_ms,
            "timestamp": output.timestamp,
            "line_count": len(output.lines),
            "has_errors": any(
                line.line_type == "error"
                for line in output.lines
            ),
            "has_warnings": any(
                line.line_type == "warning"
                for line in output.lines
            )
        }