/**
 * MedpolChat - AI 对话主组件（SSE 流式响应）
 *
 * 功能：
 * - SSE 流式实时响应
 * - 丰富组件渲染（表格、图表、检索结果）
 * - PC端优化响应式设计
 * - Markdown 文本支持
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { useChatStream } from "./useChatStream";
import { ChatComponentRenderer } from "./ChatComponents";
import { LLMMarkdown } from "./LLMMarkdown";
import { ArticleModal } from "./ArticleModal";
import type { ChatMessage, ChatOptions } from "./types";
import "./MedpolChat.css";

export type FontSize = "small" | "normal" | "large" | "xlarge";

export interface MedpolChatProps extends ChatOptions {
  /** 初始欢迎消息 */
  welcomeMessage?: string;
  /** 输入框占位文本 */
  placeholder?: string;
  /** 对话容器高度 */
  height?: string | number;
  /** 自定义类名 */
  className?: string;
  /** 默认字体大小 */
  defaultFontSize?: FontSize;
  /** 显示字体大小切换按钮 */
  showFontSizeToggle?: boolean;
  /** 初始加载的消息 */
  initialMessages?: ChatMessage[];
  /** 初始对话 ID */
  initialConversationId?: string | null;
  /** 消息变化时的回调 */
  onMessagesChange?: (messages: ChatMessage[], conversationId: string | null) => void;
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
  mode = "rag",
  welcomeMessage = "您好！我是医疗政策助手，专注政策法规检索。您可以向我咨询医药政策相关问题。",
  placeholder = "输入您的问题...",
  height = "100%",
  className = "",
  defaultFontSize = "normal",
  showFontSizeToggle = true,
  initialMessages,
  initialConversationId,
  onMessagesChange,
  onMessage,
  onError,
  onDone,
}: MedpolChatProps) {
  const [inputValue, setInputValue] = useState("");
  const [fontSize, setFontSize] = useState<FontSize>(defaultFontSize);
  const [viewingArticleId, setViewingArticleId] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const isInitialized = useRef(false);

  const {
    messages,
    conversationId,
    isStreaming,
    currentStatus,
    currentTool,
    error,
    sendMessage,
    cancelStream,
    clearMessages,
    loadMessages,
  } = useChatStream({
    apiBase,
    mode,
    onMessage: (msg) => {
      onMessage?.(msg);
    },
    onError,
    onDone,
  });

  // 挂载时加载初始消息
  useEffect(() => {
    if (!isInitialized.current && initialMessages && initialMessages.length > 0) {
      loadMessages(initialMessages, initialConversationId || null);
      isInitialized.current = true;
    }
  }, [initialMessages, initialConversationId, loadMessages]);

  // 通知父组件消息变化
  useEffect(() => {
    if (isInitialized.current) {
      onMessagesChange?.(messages, conversationId);
    }
  }, [messages, conversationId, onMessagesChange]);

  // 新消息到达时自动滚动到底部
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, currentStatus]);

  // 处理表单提交
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

  // 处理回车键（Shift+Enter 换行）
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSubmit(e);
      }
    },
    [handleSubmit]
  );

  // 自动调整文本框高度
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

  // 处理文章弹窗
  const handleViewArticle = useCallback((articleId: string) => {
    setViewingArticleId(articleId);
  }, []);

  const handleCloseArticle = useCallback(() => {
    setViewingArticleId(null);
  }, []);

  return (
    <div
      className={`medpol-chat ${fontSizeClass} ${className}`}
      style={{ height: typeof height === "number" ? `${height}px` : height }}
    >
      {/* 消息区域 */}
      <div className="medpol-chat__messages">
        {/* 欢迎页面 - ChatGPT风格 */}
        {messages.length === 0 && (
          <div className="medpol-chat__welcome-center">
            <h1 className="medpol-chat__welcome-title">联环集团 · 医药政策助手</h1>
            <p className="medpol-chat__welcome-subtitle">有什么可以帮忙的？</p>
            <div className="medpol-chat__examples">
              {[
                "最新的医保政策有哪些变化？",
                "药品集采相关政策",
                "医疗器械监管规定",
                "DRG/DIP付费改革进展",
              ].map((question, idx) => (
                <button
                  key={idx}
                  type="button"
                  className="medpol-chat__example-btn"
                  onClick={() => {
                    setInputValue(question);
                    inputRef.current?.focus();
                  }}
                >
                  {question}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* 消息列表 */}
        {messages.map((msg, idx) => {
          const isLastPending = idx === messages.length - 1 && msg.status === "pending";
          if (isLastPending && currentStatus) return null;
          return <MessageBubble key={msg.id} message={msg} onViewArticle={handleViewArticle} />;
        })}

        {/* 流式状态 */}
        {isStreaming && currentStatus && (
          <ToolStatusCard tool={currentTool} status={currentStatus} />
        )}

        {/* 错误显示 */}
        {error && !isStreaming && (
          <div className="medpol-chat__error">
            <span>错误: {error}</span>
            <button onClick={clearMessages}>清空对话</button>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* 输入区域 - ChatGPT风格胶囊形状 */}
      <form className="medpol-chat__input-area" onSubmit={handleSubmit}>
        <div className="medpol-chat__input-wrapper">
          {/* 字体大小按钮 */}
          {showFontSizeToggle && (
            <button
              type="button"
              className="medpol-chat__font-btn"
              onClick={cycleFontSize}
              title={`字体: ${FONT_SIZE_LABELS[fontSize]}`}
            >
              <span className="medpol-chat__font-btn-icon">Aa</span>
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
          {isStreaming ? (
            <button
              type="button"
              onClick={cancelStream}
              className="medpol-chat__btn-circle medpol-chat__btn-circle--stop"
              title="停止"
            >
              ■
            </button>
          ) : (
            <button
              type="submit"
              disabled={!inputValue.trim()}
              className="medpol-chat__btn-circle"
              title="发送"
            >
              ↑
            </button>
          )}
        </div>
      </form>

      {/* 文章详情弹窗 */}
      <ArticleModal
        articleId={viewingArticleId}
        onClose={handleCloseArticle}
        apiBase={apiBase}
      />
    </div>
  );
}

// ======================== 消息气泡组件 ========================

interface MessageBubbleProps {
  message: ChatMessage;
  onViewArticle?: (articleId: string) => void;
}

function MessageBubble({ message, onViewArticle }: MessageBubbleProps) {
  const { role, content, components, status } = message;
  const isUser = role === "user";

  return (
    <div className={`medpol-chat__message medpol-chat__message--${role}`}>
      {/* 只有 AI 消息显示头像 */}
      {!isUser && (
        <div className="medpol-chat__avatar medpol-chat__avatar--assistant">
          <span className="medpol-chat__avatar-icon">✦</span>
        </div>
      )}
      <div className="medpol-chat__content">
        {/* 文本内容 */}
        <div
          className={`medpol-chat__bubble medpol-chat__bubble--${role} ${
            status === "streaming" ? "medpol-chat__bubble--streaming" : ""
          }`}
        >
          {content ? (
            !isUser ? (
              <LLMMarkdown content={content} isStreaming={status === "streaming"} />
            ) : (
              content
            )
          ) : status === "pending" ? (
            <ThinkingIndicator />
          ) : status === "cancelled" ? (
            <span className="medpol-chat__cancelled">已停止</span>
          ) : null}
          {status === "streaming" && <span className="medpol-chat__cursor" />}
        </div>

        {/* 富组件 */}
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

// ======================== 思考指示器组件 ========================

function ThinkingIndicator() {
  return (
    <span className="medpol-chat__thinking">
      <span className="medpol-chat__thinking-dot" />
      <span className="medpol-chat__thinking-dot" />
      <span className="medpol-chat__thinking-dot" />
    </span>
  );
}

// ======================== 工具状态卡片组件 ========================

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
