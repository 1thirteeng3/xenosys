/**
 * MCPWidgetRenderer - Higher Order Component for rendering MCP tool results
 * 
 * Dynamically decides which UI component to render based on tool payload:
 * - email_list -> EmailListWidget
 * - file_browser -> FileBrowserWidget
 * - code_execution -> CodeResultWidget
 * - search_results -> SearchResultsWidget
 * - default -> GenericToolWidget
 */

import React from 'react';

// Tool payload types
export interface EmailItem {
  id: string;
  from: string;
  subject: string;
  preview: string;
  timestamp: string;
  read: boolean;
}

export interface FileItem {
  name: string;
  path: string;
  type: 'file' | 'directory';
  size?: number;
  modified?: string;
}

export interface SearchResult {
  title: string;
  url: string;
  snippet: string;
  score?: number;
}

export interface CodeResult {
  language: string;
  output?: string;
  error?: string;
  exitCode?: number;
  executionTime?: number;
}

export type ToolPayload = 
  | { type: 'email_list'; data: EmailItem[] }
  | { type: 'file_browser'; data: FileItem[]; currentPath: string }
  | { type: 'search_results'; data: SearchResult[] }
  | { type: 'code_execution'; data: CodeResult }
  | { type: 'generic'; data: unknown };

// Email List Widget
const EmailListWidget: React.FC<{ data: EmailItem[] }> = ({ data }) => (
  <div className="space-y-2">
    {data.map((email) => (
      <div
        key={email.id}
        className="p-3 bg-xeno-bg border border-xeno-border rounded hover:border-xeno-accent-cloud/50 transition-colors"
      >
        <div className="flex justify-between items-start mb-1">
          <span className="font-semibold text-xeno-accent-active">{email.from}</span>
          <span className="text-xs text-xeno-border">{email.timestamp}</span>
        </div>
        <div className="text-sm text-gray-300">{email.subject}</div>
        <div className="text-xs text-gray-500 mt-1 truncate">{email.preview}</div>
        <button className="mt-2 text-xs text-xeno-accent-cloud hover:underline">
          Reply
        </button>
      </div>
    ))}
  </div>
);

// File Browser Widget
const FileBrowserWidget: React.FC<{ data: FileItem[]; currentPath: string }> = ({ 
  data, 
  currentPath 
}) => (
  <div>
    <div className="text-xs text-xeno-border mb-2 font-mono">{currentPath}</div>
    <div className="space-y-1">
      {data.map((file, i) => (
        <div
          key={i}
          className="flex items-center gap-2 p-2 hover:bg-xeno-bg rounded text-sm"
        >
          <span className={file.type === 'directory' ? 'text-xeno-accent-alert' : 'text-xeno-accent-active'}>
            {file.type === 'directory' ? '📁' : '📄'}
          </span>
          <span className="text-gray-300">{file.name}</span>
          {file.size && (
            <span className="text-xs text-xeno-border ml-auto">
              {(file.size / 1024).toFixed(1)} KB
            </span>
          )}
        </div>
      ))}
    </div>
  </div>
);

// Search Results Widget
const SearchResultsWidget: React.FC<{ data: SearchResult[] }> = ({ data }) => (
  <div className="space-y-3">
    {data.map((result, i) => (
      <div key={i} className="border-b border-xeno-border pb-2 last:border-0">
        <a 
          href={result.url} 
          target="_blank" 
          rel="noopener noreferrer"
          className="text-xeno-accent-cloud hover:underline font-medium"
        >
          {result.title}
        </a>
        <p className="text-sm text-gray-400 mt-1 line-clamp-2">{result.snippet}</p>
        {result.score !== undefined && (
          <span className="text-xs text-xeno-border">
            Relevance: {Math.round(result.score * 100)}%
          </span>
        )}
      </div>
    ))}
  </div>
);

// Code Execution Widget
const CodeResultWidget: React.FC<{ data: CodeResult }> = ({ data }) => (
  <div>
    <div className="flex items-center gap-2 mb-2">
      <span className="text-xs text-xeno-border bg-xeno-bg px-2 py-0.5 rounded">
        {data.language}
      </span>
      {data.executionTime !== undefined && (
        <span className="text-xs text-xeno-border">
          {data.executionTime}ms
        </span>
      )}
      {data.exitCode !== undefined && (
        <span className={data.exitCode === 0 ? 'text-xeno-accent-active' : 'text-xeno-accent-error'}>
          Exit: {data.exitCode}
        </span>
      )}
    </div>
    {data.output && (
      <pre className="bg-[#050505] p-3 rounded text-xs font-mono overflow-x-auto text-gray-300">
        {data.output}
      </pre>
    )}
    {data.error && (
      <pre className="bg-xeno-accent-error/10 border border-xeno-accent-error/30 p-3 rounded text-xs font-mono overflow-x-auto text-xeno-accent-error">
        {data.error}
      </pre>
    )}
  </div>
);

// Generic Fallback Widget
const GenericToolWidget: React.FC<{ data: unknown }> = ({ data }) => (
  <pre className="bg-[#050505] p-3 rounded text-xs font-mono overflow-x-auto text-gray-400">
    {JSON.stringify(data, null, 2)}
  </pre>
);

// Main Renderer Component
interface MCPWidgetRendererProps {
  payload: ToolPayload;
}

export const MCPWidgetRenderer: React.FC<MCPWidgetRendererProps> = ({ payload }) => {
  switch (payload.type) {
    case 'email_list':
      return <EmailListWidget data={payload.data} />;
    case 'file_browser':
      return <FileBrowserWidget data={payload.data} currentPath={payload.currentPath} />;
    case 'search_results':
      return <SearchResultsWidget data={payload.data} />;
    case 'code_execution':
      return <CodeResultWidget data={payload.data} />;
    default:
      return <GenericToolWidget data={payload.data} />;
  }
};

export default MCPWidgetRenderer;