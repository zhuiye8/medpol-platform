/**
 * Types for AI Chat SSE streaming
 */

// SSE Event Types
export type SSEEventType =
  | "session"
  | "status"
  | "tool_start"
  | "tool_result"
  | "text_delta"
  | "component"
  | "done"
  | "error";

// Base event interface
export interface SSEEventBase {
  type: SSEEventType;
}

export interface SSESessionEvent extends SSEEventBase {
  type: "session";
  conversation_id: string;
}

export interface SSEStatusEvent extends SSEEventBase {
  type: "status";
  content: string;
}

export interface SSEToolStartEvent extends SSEEventBase {
  type: "tool_start";
  tool: string;
  args?: Record<string, unknown>;
}

export interface SSEToolResultEvent extends SSEEventBase {
  type: "tool_result";
  tool: string;
  success: boolean;
  data?: Record<string, unknown>;
}

export interface SSETextDeltaEvent extends SSEEventBase {
  type: "text_delta";
  content: string;
}

export interface SSEComponentEvent extends SSEEventBase {
  type: "component";
  component_type: "dataframe" | "chart" | "search_results";
  data: Record<string, unknown>;
  title?: string;
}

export interface ToolCall {
  tool: string;
  arguments: Record<string, unknown>;
  result: unknown;
}

export interface SSEDoneEvent extends SSEEventBase {
  type: "done";
  conversation_id: string;
  tool_calls?: ToolCall[];
}

export interface SSEErrorEvent extends SSEEventBase {
  type: "error";
  message: string;
  code?: number;
}

export type SSEEvent =
  | SSESessionEvent
  | SSEStatusEvent
  | SSEToolStartEvent
  | SSEToolResultEvent
  | SSETextDeltaEvent
  | SSEComponentEvent
  | SSEDoneEvent
  | SSEErrorEvent;

// Component Data Types
export interface DataFrameData {
  columns: string[];
  rows: Record<string, unknown>[];
  row_count: number;
}

export interface ChartData {
  chart_type: string;
  config: Record<string, unknown>;
}

export interface SearchResult {
  article_id: string;
  title: string;
  source_name?: string;
  publish_time?: string;
  text: string;
  score: number;
}

export interface SearchResultsData {
  results: SearchResult[];
}

// Chat Message Types
export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  components?: ChatComponent[];
  status?: "pending" | "streaming" | "complete" | "error" | "cancelled";
  timestamp: Date;
}

export interface ChatComponent {
  type: "dataframe" | "chart" | "search_results";
  data: DataFrameData | ChartData | SearchResultsData;
  title?: string;
}

// Hook State
export interface ChatStreamState {
  conversationId: string | null;
  messages: ChatMessage[];
  isStreaming: boolean;
  currentStatus: string | null;
  currentTool: string | null;
  error: string | null;
}

// Chat Options
export interface ChatOptions {
  apiBase?: string;
  mode?: "rag" | "sql" | "hybrid";
  onMessage?: (message: ChatMessage) => void;
  onError?: (error: Error) => void;
  onDone?: (result: { conversationId: string; toolCalls?: ToolCall[] }) => void;
}
