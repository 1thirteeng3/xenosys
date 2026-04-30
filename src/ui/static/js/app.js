/**
 * XenoSys UI - SPA Client
 * 
 * Toggle via JavaScript (SPA) - não re-renderização server-side.
 * Preserva estado do terminal entre alternâncias.
 */

(function() {
    'use strict';
    
    // Estado global
    let state = {
        currentView: 'execution',
        theme: 'light',
        terminalBuffer: '',
        graphStats: null
    };
    
    // Elementos DOM
    const elements = {};
    
    /**
     * Inicializar UI.
     */
    function init() {
        cacheElements();
        setupEventListeners();
        loadInitialState();
        startPolling();
    }
    
    /**
     * Cache elementos DOM para performance.
     */
    function cacheElements() {
        elements.app = document.getElementById('app');
        elements.btnExecution = document.getElementById('btn-execution');
        elements.btnGraph = document.getElementById('btn-graph');
        elements.btnTheme = document.getElementById('btn-theme');
        elements.viewExecution = document.getElementById('view-execution');
        elements.viewGraph = document.getElementById('view-graph');
        elements.terminalOutput = document.getElementById('terminal-output');
        elements.graphStats = document.getElementById('graph-stats');
        elements.graphContainer = document.getElementById('graph-container');
        elements.nodePanel = document.getElementById('node-panel');
        elements.panelContent = document.getElementById('panel-content');
    }
    
    /**
     * Setup event listeners.
     */
    function setupEventListeners() {
        // Botões de toggle de view
        elements.btnExecution.addEventListener('click', () => setView('execution'));
        elements.btnGraph.addEventListener('click', () => setView('graph'));
        
        // Botão de theme
        elements.btnTheme.addEventListener('click', toggleTheme);
        
        // Botão defechar panel
        document.getElementById('btn-close-panel').addEventListener('click', closeNodePanel);
    }
    
    /**
     * Carrega estado inicial.
     */
    async function loadInitialState() {
        try {
            const resp = await fetch('/api/state');
            state = await resp.json();
            
            // Aplicar theme
            if (state.theme === 'dark') {
                document.body.classList.add('dark');
            }
            
            // Setar view inicial
            setView(state.current_view || 'execution', false);
            
            // Carregar execution se ativo
            if (state.current_view === 'execution') {
                loadExecution();
            }
            
            console.log('State loaded:', state);
        } catch (e) {
            console.error('State load failed:', e);
        }
    }
    
    /**
     * Setar visualização ativa via JavaScript (SPA).
     * O estado do terminal préservado porque não re-renderiza.
     */
    function setView(view, fetchData = true) {
        state.currentView = view;
        
        // Atualizar botões
        elements.btnExecution.classList.toggle('active', view === 'execution');
        elements.btnGraph.classList.toggle('active', view === 'graph');
        
        // Atualizar views (mostrar/esconder via DOM)
        elements.viewExecution.classList.toggle('active', view === 'execution');
        elements.viewGraph.classList.toggle('active', view === 'graph');
        
        // Carregar dados se necessário
        if (fetchData) {
            if (view === 'execution') {
                loadExecution();
            } else {
                loadGraph();
            }
        }
        
        console.log('View set to:', view);
    }
    
    /**
     * Carregar dados de execução.
     */
    async function loadExecution() {
        try {
            const resp = await fetch('/api/execution');
            const data = await resp.json();
            
            // Preservar buffer do terminal
            const output = data.last_stdout || data.last_stderr || '[Aguardando execução...]';
            state.terminalBuffer = output;
            
            elements.terminalOutput.textContent = output;
            
            // Atualizar exit code
            if (data.last_exit_code !== 0) {
                elements.terminalOutput.innerHTML += `\n[Exit: ${data.last_exit_code}]`;
            }
        } catch (e) {
            console.error('Execution load failed:', e);
        }
    }
    
    /**
     * Carregar dados do grafo.
     */
    async function loadGraph() {
        try {
            const resp = await fetch('/api/graph');
            const data = await resp.json();
            
            state.graphStats = data.stats;
            
            if (elements.graphStats) {
                elements.graphStats.textContent = `${data.stats.node_count} nós, ${data.stats.edge_count} arestas`;
            }
            
            // Se iframe vazio, recarregar
            const iframe = elements.graphContainer.querySelector('iframe');
            if (iframe && !iframe.src) {
                iframe.src = '/api/graph/render';
            }
        } catch (e) {
            console.error('Graph load failed:', e);
        }
    }
    
    /**
     * Alternar tema.
     */
    async function toggleTheme() {
        try {
            await fetch('/api/theme/toggle', {method: 'POST'});
            
            document.body.classList.toggle('dark');
            state.theme = state.theme === 'light' ? 'dark' : 'light';
        } catch (e) {
            console.error('Theme toggle failed:', e);
        }
    }
    
    /**
     * Abrir nó no painel lateral.
     * SEGURANÇA: Usa textContent para previnir XSS.
     */
    async function openNodePanel(nodeId) {
        try {
            const resp = await fetch(`/api/graph/node/${nodeId}`);
            const data = await resp.json();
            
            // Limpar conteúdo anterior - SEGURANÇA XSS
            elements.panelContent.innerHTML = '';
            
            // Criar elementos via DOM API (textContent previne XSS)
            const pre = document.createElement('pre');
            pre.textContent = data.content;  // ⚠️ textContent - não innerHTML
            elements.panelContent.appendChild(pre);
            
            // Metadata
            const meta = document.createElement('div');
            meta.className = 'panel-meta';
            meta.innerHTML = `
                <p><strong>ID:</strong> ${escapeHtml(data.id)}</p>
                <p><strong>Criado:</strong> ${escapeHtml(data.created_at)}</p>
            `;
            elements.panelContent.appendChild(meta);
            
            elements.nodePanel.classList.add('active');
        } catch (e) {
            console.error('Node load failed:', e);
        }
    }
    
    /**
     * Fechar painel.
     */
    function closeNodePanel() {
        elements.nodePanel.classList.remove('active');
    }
    
    /**
     * Escapar HTML.
     */
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    /**
     * Polling para atualizações.
     * SEGURANÇA: Respeita Page Visibility API para previnir vazamento.
     */
    let pollingInterval = null;
    
    function startPolling() {
        if (pollingInterval) return;  // Já rodando
        
        pollingInterval = setInterval(async () => {
            try {
                const resp = await fetch('/api/state');
                const newState = await resp.json();
                
                if (state.currentView === 'execution') {
                    const execState = await fetch('/api/execution');
                    const data = await execState.json();
                    
                    if (data.last_stdout !== state.terminalBuffer) {
                        state.terminalBuffer = data.last_stdout;
                        elements.terminalOutput.textContent = data.last_stdout || data.last_stderr;
                    }
                }
            } catch (e) {
                // Silently ignore polling errors
            }
        }, 3000);
    }
    
    function stopPolling() {
        if (pollingInterval) {
            clearInterval(pollingInterval);
            pollingInterval = null;
        }
    }
    
    // Page Visibility API - pauses polling quando aba oculta
    document.addEventListener("visibilitychange", function() {
        if (document.hidden) {
            stopPolling();
            console.log('Polling pausado (aba oculta)');
        } else {
            startPolling();
            console.log('Polling retomado');
        }
    });
    
    /**
     * Expor API global para debugging.
     */
    window.xenosys = {
        setView,
        toggleTheme,
        loadExecution,
        loadGraph,
        openNodePanel,
        closeNodePanel,
        getState: () => state
    };
    
    // Inicializar quando DOM pronto
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
    
    // Listener para mensagens do iframe (IPC)
// SEGURANÇA: Valida origin antes de processar
    window.addEventListener('message', function(event) {
        // ⚠️ Origin check - Zero Trust
        if (event.origin !== window.location.origin) {
            console.warn('postMessage rejected: invalid origin', event.origin);
            return;
        }
        
        // Verificar tipo de mensagem
        if (event.data && event.data.type === 'node_click') {
            openNodePanel(event.data.nodeId);
        }
    });
    
    // Lifecycle: limpar polling ao sair
    window.addEventListener('beforeunload', function() {
        if (pollingInterval) {
            clearInterval(pollingInterval);
        }
    });
})();