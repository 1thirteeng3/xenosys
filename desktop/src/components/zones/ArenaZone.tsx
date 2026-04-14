/**
 * Arena Zone - Home / Chat Interface
 * 
 * Split-pane layout:
 * - Left (60%): Unified chat with agent
 * - Right (40%): Log Terminal with auto-scroll
 */

import React, { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, Terminal } from 'lucide-react';
import { clsx } from 'clsx';
import { ThoughtBlock, MCPWidgetRenderer, ToolPayload } from '../atomic';
import { useUIStore } from '../../store/uiStore';

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  isProcessing?: boolean;
  toolPayload?: ToolPayload;
  thoughtLog?: string;
}

interface LogEntry {
  id: string;
  timestamp: string;
  level: 'info' | 'warn' | 'error';
  message: string;
}

const INITIAL_LOGS: LogEntry[] = [
  { id: '1', timestamp: '2024-01-15T10:23:01Z', level: 'info', message: '[Gateway] Initialized on 127.0.0.1:3000' },
  { id: '2', timestamp: '2024-01-15T10:23:02Z', level: 'info', message: '[Core] DSPy optimizer loaded' },
  { id: '3', timestamp: '2024-01-15T10:23:03Z', level: 'info', message: '[Memory] L1 Semantic cache connected' },
];

export const ArenaZone: React.FC = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: '1',
      role: 'assistant',
      content: 'XenoSys ready. How may I assist you today?',
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState('');
  const [logs, setLogs] = useState<LogEntry[]>(INITIAL_LOGS);
  const [isProcessing, setIsProcessing] = useState(false);
  const logEndRef = useRef<HTMLDivElement>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll logs
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  // Auto-scroll chat
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = () => {
    if (!input.trim() || isProcessing) return;

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: input,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsProcessing(true);

    // Simulate agent response
    setTimeout(() => {
      const assistantMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: 'Processing your request through the neural pipeline...',
        timestamp: new Date(),
        isProcessing: true,
        thoughtLog: `DSPy: Executing chain-of-thought\n- Query: ${userMessage.content}\n- Retrieved 3 contexts from L1\n- Generated response with confidence: 0.92`,
      };
      setMessages((prev) => [...prev, assistantMessage]);

      // Add log entry
      setLogs((prev) => [...prev, {
        id: Date.now().toString(),
        timestamp: new Date().toISOString(),
        level: 'info',
        message: `[Agent] Processed request in 234ms`,
      }]);

      // Complete processing
      setTimeout(() => {
        setMessages((prev) => 
          prev.map((m) => 
            m.id === assistantMessage.id 
              ? { ...m, isProcessing: false, content: 'Analysis complete. I have retrieved the relevant context and prepared a comprehensive response.' }
              : m
          )
        );
        setIsProcessing(false);
      }, 2000);
    }, 1500);
  };

  return (
    <div className="flex h-full">
      {/* Left Pane - Chat (60%) */}
      <div className="w-3/5 flex flex-col border-r border-xeno-border">
        {/* Chat Header */}
        <div className="h-12 px-4 border-b border-xeno-border flex items-center gap-2">
          <Bot className="w-5 h-5 text-xeno-accent-active" />
          <span className="font-medium">Agent Arena</span>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.map((msg) => (
            <div key={msg.id} className={clsx(
              'flex gap-3',
              msg.role === 'user' ? 'justify-end' : 'justify-start'
            )}>
              {msg.role === 'assistant' && (
                <div className="w-8 h-8 rounded-full bg-xeno-accent-active/20 flex items-center justify-center flex-shrink-0">
                  <Bot className="w-4 h-4 text-xeno-accent-active" />
                </div>
              )}
              
              <div className={clsx(
                'max-w-[70%] rounded-lg p-3',
                msg.role === 'user' 
                  ? 'bg-xeno-accent-active/10 text-xeno-accent-active' 
                  : 'bg-xeno-surface border border-xeno-border'
              )}>
                <div className="text-sm">{msg.content}</div>
                
                {/* Thought Block for processing */}
                {msg.isProcessing && msg.thoughtLog && (
                  <div className="mt-3">
                    <ThoughtBlock 
                      isProcessing={true}
                      logContent={msg.thoughtLog}
                      timestamp={msg.timestamp.toLocaleTimeString()}
                    />
                  </div>
                )}
              </div>

              {msg.role === 'user' && (
                <div className="w-8 h-8 rounded-full bg-xeno-surface border border-xeno-border flex items-center justify-center flex-shrink-0">
                  <User className="w-4 h-4 text-gray-400" />
                </div>
              )}
            </div>
          ))}
          <div ref={chatEndRef} />
        </div>

        {/* Input */}
        <div className="p-4 border-t border-xeno-border">
          <div className="flex gap-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSend()}
              placeholder="Message XenoSys..."
              className="input-field flex-1"
              disabled={isProcessing}
            />
            <button
              onClick={handleSend}
              disabled={!input.trim() || isProcessing}
              className="btn-primary flex items-center gap-2"
            >
              <Send className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Right Pane - Log Terminal (40%) */}
      <div className="w-2/5 flex flex-col bg-[#050505]">
        {/* Terminal Header */}
        <div className="h-12 px-4 border-b border-xeno-border flex items-center gap-2">
          <Terminal className="w-4 h-4 text-xeno-accent-cloud" />
          <span className="text-sm text-gray-400">Activity Feed</span>
        </div>

        {/* Logs */}
        <div className="flex-1 overflow-y-auto p-2 space-y-0.5 font-mono text-xs">
          {logs.map((log) => (
            <div 
              key={log.id} 
              className="px-2 py-1 hover:bg-xeno-border/30 rounded"
            >
              <span className="text-xeno-border mr-2">
                {log.timestamp.split('T')[1].split('.')[0]}
              </span>
              <span className={clsx(
                log.level === 'error' && 'text-xeno-accent-error',
                log.level === 'warn' && 'text-xeno-accent-alert',
                log.level === 'info' && 'text-xeno-accent-cloud'
              )}>
                [{log.level.toUpperCase()}]
              </span>
              <span className="text-gray-400 ml-2">{log.message}</span>
            </div>
          ))}
          <div ref={logEndRef} />
        </div>
      </div>
    </div>
  );
};

export default ArenaZone;