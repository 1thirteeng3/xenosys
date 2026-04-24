/**
 * MCPWidgetRenderer - Higher Order Component for rendering MCP tool results
 * 
 * SECURE VERSION with:
 * - Zod schema validation on all inputs
 * - DOMPurify sanitization for all text output
 * - Defensive error handling for bad payloads
 */

import React from 'react';
import { z } from 'zod';
import DOMPurify from 'dompurify';

// Tool payload types - Strictly define accepted schemas
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

// Zod Schemas for strict validation
const EmailItemSchema = z.object({
  id: z.string(),
  from: z.string(),
  subject: z.string(),
  preview: z.string(),
  timestamp: z.string(),
  read: z.boolean(),
});

const FileItemSchema = z.object({
  name: z.string(),
  path: z.string(),
  type: z.enum(['file', 'directory']),
  size: z.number().optional(),
  modified: z.string().optional(),
});

const SearchResultSchema = z.object({
  title: z.string(),
  url: z.string(),
  snippet: z.string(),
  score: z.number().optional(),
});

const CodeResultSchema = z.object({
  language: z.string(),
  output: z.string().optional(),
  error: z.string().optional(),
  exitCode: z.number().optional(),
  executionTime: z.number().optional(),
});

// Main payload schema
const ToolPayloadSchema = z.object({
  type: z.enum(['email_list', 'file_browser', 'search_results', 'code_execution', 'generic']),
  data: z.unknown(),
});

// Data sanitization helper
const sanitizeText = (text: string): string => {
  return DOMPurify.sanitize(text, {
    ALLOWED_TAGS: ['b', 'i', 'em', 'strong', 'a'],
    ALLOWED_ATTR: ['href', 'target'],
  });
};

const sanitizeUrl = (url: string): string => {
  const sanitized = DOMPurify.sanitize(url, { ALLOWED_TAGS: [] });
  // Only allow http/https
  if (!sanitized.startsWith('http://') && !sanitized.startsWith('https://')) {
    return '';
  }
  return sanitized;
};

// Email List Widget
const EmailListWidget: React.FC<{ data: EmailItem[] }> = ({ data }) => (
  <div className="space-y-2">
    {data.map((email) => (
      <div
        key={sanitizeText(email.id)}
        className="p-3 bg-xeno-bg border border-xeno-border rounded hover:border-xeno-accent-cloud/50 transition-colors"
      >
        <div className="flex justify-between items-start mb-1">
          <span className="font-semibold text-xeno-accent-active">
            {sanitizeText(email.from)}
          </span>
          <span className="text-xs text-xeno-border">
            {sanitizeText(email.timestamp)}
          </span>
        </div>
        <div className="text-sm text-gray-300">
          {sanitizeText(email.subject)}
        </div>
        <div className="text-xs text-gray-500 mt-1 truncate">
          {sanitizeText(email.preview)}
        </div>
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
    <div className="text-xs text-xeno-border mb-2 font-mono">
      {sanitizeText(currentPath)}
    </div>
    <div className="space-y-1">
      {data.map((file, i) => (
        <div
          key={i}
          className="flex items-center gap-2 p-2 hover:bg-xeno-bg rounded text-sm"
        >
          <span className={file.type === 'directory' ? 'text-xeno-accent-alert' : 'text-xeno-accent-active'}>
            {file.type === 'directory' ? '📁' : '📄'}
          </span>
          <span className="text-gray-300">{sanitizeText(file.name)}</span>
          {file.size !== undefined && (
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
          href={sanitizeUrl(result.url)}
          target="_blank" 
          rel="noopener noreferrer"
          className="text-xeno-accent-cloud hover:underline font-medium"
        >
          {sanitizeText(result.title)}
        </a>
        <p className="text-sm text-gray-400 mt-1 line-clamp-2">
          {sanitizeText(result.snippet)}
        </p>
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
        {sanitizeText(data.language)}
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
        {sanitizeText(data.output)}
      </pre>
    )}
    {data.error && (
      <pre className="bg-xeno-accent-error/10 border border-xeno-accent-error/30 p-3 rounded text-xs font-mono overflow-x-auto text-xeno-accent-error">
        {sanitizeText(data.error)}
      </pre>
    )}
  </div>
);

// Generic Fallback Widget
const GenericToolWidget: React.FC<{ data: unknown }> = ({ data }) => (
  <pre className="bg-[#050505] p-3 rounded text-xs font-mono overflow-x-auto text-gray-400">
    {sanitizeText(JSON.stringify(data, null, 2))}
  </pre>
);

// Main Renderer Component with schema validation
interface MCPWidgetRendererProps {
  payload: unknown;
}

export const MCPWidgetRenderer: React.FC<MCPWidgetRendererProps> = ({ payload }) => {
  // Step 1: Schema validation
  const validationResult = ToolPayloadSchema.safeParse(payload);
  
  if (!validationResult.success) {
    // Silent UI failure - log error, show safe message
    console.error('MCP Widget: Invalid payload schema', validationResult.error);
    return (
      <div className="text-xeno-accent-error text-xs p-2">
        Error: Incompatible payload rendered by the agent.
      </div>
    );
  }

  const validatedPayload = validationResult.data;

  // Step 2: Type-specific validation with data sanitization
  try {
    switch (validatedPayload.type) {
      case 'email_list':
        const emailResult = z.array(EmailItemSchema).safeParse(validatedPayload.data);
        if (!emailResult.success) throw new Error('Invalid email data');
        return <EmailListWidget data={emailResult.data} />;
        
      case 'file_browser':
        if (!validatedPayload.data || typeof validatedPayload.data !== 'object') {
          throw new Error('Invalid file_browser data');
        }
        const fbData = validatedPayload.data as { files?: FileItem[]; currentPath?: string };
        const filesResult = z.array(FileItemSchema).safeParse(fbData.files || []);
        if (!filesResult.success) throw new Error('Invalid file data');
        return <FileBrowserWidget data={filesResult.data} currentPath={fbData.currentPath || ''} />;
        
      case 'search_results':
        const searchResult = z.array(SearchResultSchema).safeParse(validatedPayload.data);
        if (!searchResult.success) throw new Error('Invalid search data');
        return <SearchResultsWidget data={searchResult.data} />;
        
      case 'code_execution':
        const codeResult = CodeResultSchema.safeParse(validatedPayload.data);
        if (!codeResult.success) throw new Error('Invalid code result');
        return <CodeResultWidget data={codeResult.data} />;
        
      default:
        return <GenericToolWidget data={validatedPayload.data} />;
    }
  } catch (err) {
    console.error('MCP Widget: Rendering error', err);
    return (
      <div className="text-xeno-accent-error text-xs p-2">
        Error: Widget rendering failed.
      </div>
    );
  }
};

export default MCPWidgetRenderer;