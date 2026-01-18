/**
 * React hook for SSE streaming chat
 */
import { useCallback, useRef, useState } from "react";
import type {
  ChatMessage,
  ChatComponent,
  ChatOptions,
  ChatStreamState,
  SSEEvent,
  ToolCall,
} from "./types";

// 优先使用 public_chat 专用的 API 地址，回退到通用配置
const DEFAULT_API_BASE =
  import.meta.env.VITE_PUBLIC_CHAT_API_BASE ||
  import.meta.env.VITE_API_BASE ||
  "http://localhost:8000";

function generateId(): string {
  return `msg_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
}

export function useChatStream(options: ChatOptions = {}) {
  const {
    apiBase = DEFAULT_API_BASE,
    mode = "rag",
    onMessage,
    onError,
    onDone,
  } = options;

  const [state, setState] = useState<ChatStreamState>({
    conversationId: null,
    messages: [],
    isStreaming: false,
    currentStatus: null,
    currentTool: null,
    error: null,
  });

  const abortControllerRef = useRef<AbortController | null>(null);

  const sendMessage = useCallback(
    async (content: string) => {
      // Cancel any existing stream
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }

      const abortController = new AbortController();
      abortControllerRef.current = abortController;

      // Add user message
      const userMessage: ChatMessage = {
        id: generateId(),
        role: "user",
        content,
        status: "complete",
        timestamp: new Date(),
      };

      // Create placeholder assistant message
      const assistantMessage: ChatMessage = {
        id: generateId(),
        role: "assistant",
        content: "",
        components: [],
        status: "pending",
        timestamp: new Date(),
      };

      setState((prev) => ({
        ...prev,
        messages: [...prev.messages, userMessage, assistantMessage],
        isStreaming: true,
        currentStatus: null,
        currentTool: null,
        error: null,
      }));

      try {
        // 从 sessionStorage 读取访问码
        const accessCode = sessionStorage.getItem("medpol_access_code");

        // Build URL with token
        const url = new URL(`${apiBase}/v1/ai/chat/stream`);
        if (accessCode) {
          url.searchParams.set("token", accessCode);
        }

        const response = await fetch(url.toString(), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            messages: [{ role: "user", content }],
            mode,
            conversation_id: state.conversationId,
          }),
          signal: abortController.signal,
        });

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const reader = response.body?.getReader();
        if (!reader) {
          throw new Error("No response body");
        }

        const decoder = new TextDecoder();
        let buffer = "";
        let accumulatedText = "";
        const components: ChatComponent[] = [];
        let conversationId = state.conversationId;
        let toolCalls: ToolCall[] = [];

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            if (!line.startsWith("data: ")) continue;
            const data = line.slice(6).trim();
            if (data === "[DONE]") continue;

            try {
              const event: SSEEvent = JSON.parse(data);

              switch (event.type) {
                case "session":
                  conversationId = event.conversation_id;
                  setState((prev) => ({
                    ...prev,
                    conversationId: event.conversation_id,
                  }));
                  break;

                case "status":
                  setState((prev) => ({
                    ...prev,
                    currentStatus: prev.currentTool ? prev.currentStatus : event.content,
                  }));
                  break;

                case "tool_start": {
                  const friendlyStatus: Record<string, string> = {
                    search_policy_articles: "正在检索政策文档...",
                    query_finance_sql: "正在查询财务数据...",
                    generate_finance_chart: "正在生成图表...",
                  };
                  setState((prev) => ({
                    ...prev,
                    currentTool: event.tool,
                    currentStatus: friendlyStatus[event.tool] || "正在处理...",
                  }));
                  break;
                }

                case "text_delta":
                  accumulatedText += event.content;
                  setState((prev) => ({
                    ...prev,
                    messages: prev.messages.map((msg) =>
                      msg.id === assistantMessage.id
                        ? { ...msg, content: accumulatedText, status: "streaming" }
                        : msg
                    ),
                  }));
                  break;

                case "component":
                  components.push({
                    type: event.component_type,
                    data: event.data as ChatComponent["data"],
                    title: event.title,
                  });
                  setState((prev) => ({
                    ...prev,
                    messages: prev.messages.map((msg) =>
                      msg.id === assistantMessage.id
                        ? { ...msg, components: [...components] }
                        : msg
                    ),
                  }));
                  break;

                case "done":
                  conversationId = event.conversation_id;
                  toolCalls = event.tool_calls || [];
                  break;

                case "error":
                  throw new Error(event.message);
              }
            } catch (parseErr) {
              console.warn("Failed to parse SSE event:", data, parseErr);
            }
          }
        }

        // Finalize message
        const finalMessage: ChatMessage = {
          ...assistantMessage,
          content: accumulatedText || "暂无回复",
          components,
          status: "complete",
        };

        setState((prev) => ({
          ...prev,
          conversationId,
          messages: prev.messages.map((msg) =>
            msg.id === assistantMessage.id ? finalMessage : msg
          ),
          isStreaming: false,
          currentStatus: null,
          currentTool: null,
        }));

        onMessage?.(finalMessage);
        onDone?.({ conversationId: conversationId || "", toolCalls });
      } catch (err) {
        if ((err as Error).name === "AbortError") {
          return; // User cancelled
        }

        const errorMessage = (err as Error).message || "请求失败";
        setState((prev) => ({
          ...prev,
          messages: prev.messages.map((msg) =>
            msg.id === assistantMessage.id
              ? { ...msg, content: `错误: ${errorMessage}`, status: "error" }
              : msg
          ),
          isStreaming: false,
          currentStatus: null,
          currentTool: null,
          error: errorMessage,
        }));

        onError?.(err as Error);
      } finally {
        abortControllerRef.current = null;
      }
    },
    [apiBase, mode, state.conversationId, onMessage, onError, onDone]
  );

  const cancelStream = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
      setState((prev) => ({
        ...prev,
        isStreaming: false,
        currentStatus: null,
        currentTool: null,
        messages: prev.messages.map((msg) => {
          if (
            msg.role === "assistant" &&
            (msg.status === "pending" || msg.status === "streaming")
          ) {
            return {
              ...msg,
              content: msg.content || "",
              status: "cancelled" as const,
            };
          }
          return msg;
        }),
      }));
    }
  }, []);

  const clearMessages = useCallback(() => {
    setState({
      conversationId: null,
      messages: [],
      isStreaming: false,
      currentStatus: null,
      currentTool: null,
      error: null,
    });
  }, []);

  // Load messages from history
  const loadMessages = useCallback((messages: ChatMessage[], conversationId: string | null) => {
    setState({
      conversationId,
      messages,
      isStreaming: false,
      currentStatus: null,
      currentTool: null,
      error: null,
    });
  }, []);

  return {
    ...state,
    sendMessage,
    cancelStream,
    clearMessages,
    loadMessages,
  };
}

export default useChatStream;
