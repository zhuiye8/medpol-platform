/**
 * MedpolChat - Main AI Chat Component with SSE Streaming
 *
 * Features:
 * - SSE streaming for real-time responses
 * - Rich component rendering (tables, charts, search results)
 * - Mobile-friendly responsive design
 * - Markdown support for text messages
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { useChatStream } from "./useChatStream";
import { ChatComponentRenderer } from "./ChatComponents";
import { MarkdownRenderer } from "./MarkdownRenderer";
import { ArticleModal } from "./ArticleModal";
import type { ChatMessage, ChatOptions } from "./types";
import "./MedpolChat.css";

export type FontSize = "small" | "normal" | "large" | "xlarge";

export interface MedpolChatProps extends ChatOptions {
  /** Initial welcome message */
  welcomeMessage?: string;
  /** Placeholder text for input */
  placeholder?: string;
  /** Height of the chat container */
  height?: string | number;
  /** UI variant, mobile = compact layout */
  variant?: "desktop" | "mobile";
  /** Custom class name */
  className?: string;
  /** Default font size */
  defaultFontSize?: FontSize;
  /** Show font size toggle */
  showFontSizeToggle?: boolean;
}

const FONT_SIZE_LABELS: Record<FontSize, string> = {
  small: "小",
  normal: "中",
  large: "大",
  xlarge: "特大",
};

const FONT_SIZES: FontSize[] = ["small", "normal", "large", "xlarge"];

export function MedpolChat({
  apiBase,
  mode = "hybrid",
  token,
  welcomeMessage = "您好！我是医药政策与财务分析助理。您可以向我咨询政策法规或财务数据相关问题。",
  placeholder = "输入您的问题...",
  height = "100%",
  variant = "desktop",
  className = "",
  defaultFontSize = "normal",
  showFontSizeToggle = true,
  onMessage,
  onError,
  onDone,
}: MedpolChatProps) {
  const [inputValue, setInputValue] = useState("");
  const [fontSize, setFontSize] = useState<FontSize>(defaultFontSize);
  const [viewingArticleId, setViewingArticleId] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const {
    messages,
    isStreaming,
    currentStatus,
    currentTool,
    error,
    sendMessage,
    cancelStream,
    clearMessages,
  } = useChatStream({
    apiBase,
    mode,
    token,
    onMessage,
    onError,
    onDone,
  });

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, currentStatus]);

  // Handle form submission
  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      const trimmed = inputValue.trim();
      if (!trimmed || isStreaming) return;

      sendMessage(trimmed);
      setInputValue("");
    },
    [inputValue, isStreaming, sendMessage]
  );

  // Handle Enter key (Shift+Enter for new line)
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSubmit(e);
      }
    },
    [handleSubmit]
  );

  // Auto-resize textarea
  const handleInput = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInputValue(e.target.value);
    const textarea = e.target;
    textarea.style.height = "auto";
    textarea.style.height = `${Math.min(textarea.scrollHeight, 150)}px`;
  }, []);

  const fontSizeClass = fontSize !== "normal" ? `medpol-chat--font-${fontSize}` : "";

  const cycleFontSize = useCallback(() => {
    setFontSize((prev) => {
      const idx = FONT_SIZES.indexOf(prev);
      return FONT_SIZES[(idx + 1) % FONT_SIZES.length];
    });
  }, []);

  // Handle article modal
  const handleViewArticle = useCallback((articleId: string) => {
    setViewingArticleId(articleId);
  }, []);

  const handleCloseArticle = useCallback(() => {
    setViewingArticleId(null);
  }, []);

  return (
    <div
      className={`medpol-chat ${variant === "mobile" ? "medpol-chat--mobile" : ""} ${fontSizeClass} ${className}`}
      style={{ height: typeof height === "number" ? `${height}px` : height }}
    >
      {/* Messages Area */}
      <div className="medpol-chat__messages">
        {/* Welcome message */}
        {messages.length === 0 && welcomeMessage && (
          <div className="medpol-chat__welcome">
            <div className="medpol-chat__avatar medpol-chat__avatar--assistant">AI</div>
            <div className="medpol-chat__bubble medpol-chat__bubble--assistant">
              {welcomeMessage}
            </div>
          </div>
        )}

        {/* Message list */}
        {messages.map((msg, idx) => {
          // 如果是最后一条消息且是pending状态，同时有工具状态，则不显示（避免重复）
          const isLastPending = idx === messages.length - 1 && msg.status === "pending";
          if (isLastPending && currentStatus) return null;
          return <MessageBubble key={msg.id} message={msg} onViewArticle={handleViewArticle} />;
        })}

        {/* Streaming status */}
        {isStreaming && currentStatus && (
          <ToolStatusCard tool={currentTool} status={currentStatus} />
        )}

        {/* Error display */}
        {error && !isStreaming && (
          <div className="medpol-chat__error">
            <span>错误: {error}</span>
            <button onClick={clearMessages}>清空对话</button>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <form className="medpol-chat__input-area" onSubmit={handleSubmit}>
        {/* Font Size FAB */}
        {showFontSizeToggle && (
          <button
            type="button"
            className="medpol-chat__font-fab"
            onClick={cycleFontSize}
            title={`字体: ${FONT_SIZE_LABELS[fontSize]}`}
          >
            <span className="medpol-chat__font-fab-icon">Aa</span>
          </button>
        )}
        <textarea
          ref={inputRef}
          value={inputValue}
          onChange={handleInput}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={isStreaming}
          rows={1}
          className="medpol-chat__input"
        />
        <div className="medpol-chat__actions">
          {isStreaming ? (
            <button
              type="button"
              onClick={cancelStream}
              className="medpol-chat__btn medpol-chat__btn--cancel"
            >
              停止
            </button>
          ) : (
            <button
              type="submit"
              disabled={!inputValue.trim()}
              className="medpol-chat__btn medpol-chat__btn--send"
            >
              发送
            </button>
          )}
        </div>
      </form>

      {/* Article Detail Modal */}
      <ArticleModal
        articleId={viewingArticleId}
        onClose={handleCloseArticle}
        apiBase={apiBase}
      />
    </div>
  );
}

// ======================== MessageBubble Component ========================

interface MessageBubbleProps {
  message: ChatMessage;
  onViewArticle?: (articleId: string) => void;
}

function MessageBubble({ message, onViewArticle }: MessageBubbleProps) {
  const { role, content, components, status } = message;
  const isAssistant = role === "assistant";

  return (
    <div className={`medpol-chat__message medpol-chat__message--${role}`}>
      <div className={`medpol-chat__avatar medpol-chat__avatar--${role}`}>
        {isAssistant ? "AI" : "U"}
      </div>
      <div className={`medpol-chat__content`}>
        {/* Text content */}
        <div
          className={`medpol-chat__bubble medpol-chat__bubble--${role} ${
            status === "streaming" ? "medpol-chat__bubble--streaming" : ""
          }`}
        >
          {content ? (
            isAssistant ? (
              <MarkdownRenderer content={content} />
            ) : (
              content
            )
          ) : (
            status === "pending" && <ThinkingIndicator />
          )}
          {status === "streaming" && <span className="medpol-chat__cursor" />}
        </div>

        {/* Rich components */}
        {components && components.length > 0 && (
          <div className="medpol-chat__components">
            {components.map((comp, i) => (
              <div key={i} className="medpol-chat__component">
                <ChatComponentRenderer
                  type={comp.type}
                  data={comp.data}
                  title={comp.title}
                  onViewArticle={onViewArticle}
                />
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ======================== ThinkingIndicator Component ========================

function ThinkingIndicator() {
  return (
    <span className="medpol-chat__thinking">
      <span className="medpol-chat__thinking-dot" />
      <span className="medpol-chat__thinking-dot" />
      <span className="medpol-chat__thinking-dot" />
    </span>
  );
}

// ======================== ToolStatusCard Component ========================

interface ToolStatusCardProps {
  tool: string | null;
  status: string;
}

const TOOL_CONFIG: Record<string, { icon: string; label: string }> = {
  search_policy_articles: { icon: "📄", label: "政策检索" },
  query_finance_sql: { icon: "📊", label: "数据查询" },
  generate_finance_chart: { icon: "📈", label: "图表生成" },
};

function ToolStatusCard({ tool, status }: ToolStatusCardProps) {
  const config = tool ? TOOL_CONFIG[tool] : null;

  return (
    <div className="medpol-chat__message medpol-chat__message--assistant">
      <div className="medpol-chat__avatar medpol-chat__avatar--assistant">AI</div>
      <div className="medpol-chat__content">
        <div className="medpol-chat__tool-status">
          <span className="medpol-chat__tool-status-icon">{config?.icon || "💭"}</span>
          <span className="medpol-chat__tool-status-text">
            {config?.label || status}...
          </span>
          <span className="medpol-chat__tool-status-spinner" />
        </div>
      </div>
    </div>
  );
}

export default MedpolChat;
