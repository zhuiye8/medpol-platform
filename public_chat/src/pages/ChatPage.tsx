/**
 * ChatPage - 主对话页面（含侧边栏和主题切换）
 *
 * 功能：
 * - 对话历史侧边栏
 * - 深色/浅色主题切换
 * - PC端优化布局（最大宽度 1200px）
 * - 仅支持知识库问答模式
 */
import { useCallback, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { MedpolChat } from "@/components/chat";
import { Sidebar } from "@/components/Sidebar";
import { ThemeToggle } from "@/components/ThemeToggle";
import { useConversationHistory } from "@/hooks/useConversationHistory";
import { useTheme } from "@/stores/themeStore";
import type { ChatMessage } from "@/components/chat/types";

export function ChatPage() {
  // 初始化主题
  useTheme();

  // 读取 URL 参数控制侧边栏显示（用于 iframe 嵌入）
  const [searchParams] = useSearchParams();
  const showSidebar = searchParams.get("sidebar") !== "false";

  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  const {
    conversations,
    activeConversation,
    activeConversationId,
    updateMessages,
    switchConversation,
    deleteConversation,
    startNewChat,
  } = useConversationHistory();

  // 处理对话组件的消息变化
  const handleMessagesChange = useCallback(
    (messages: ChatMessage[], conversationId: string | null) => {
      updateMessages(messages, conversationId);
    },
    [updateMessages]
  );

  // 处理新建对话
  const handleNewChat = useCallback(() => {
    startNewChat();
  }, [startNewChat]);

  // 处理对话选择
  const handleSelectConversation = useCallback(
    (id: string) => {
      switchConversation(id);
    },
    [switchConversation]
  );

  // 处理对话删除
  const handleDeleteConversation = useCallback(
    (id: string) => {
      deleteConversation(id);
    },
    [deleteConversation]
  );

  return (
    <div className={`chat-page ${!showSidebar ? "chat-page--no-sidebar" : ""}`}>
      {/* 侧边栏 - 可通过 URL 参数 sidebar=false 隐藏 */}
      {showSidebar && (
        <Sidebar
          conversations={conversations}
          activeConversationId={activeConversationId}
          onNewChat={handleNewChat}
          onSelectConversation={handleSelectConversation}
          onDeleteConversation={handleDeleteConversation}
          isCollapsed={sidebarCollapsed}
          onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
        />
      )}

      {/* 主内容区 */}
      <main className="chat-page__main">
        {/* 顶部栏 */}
        <header className="chat-page__header">
          <div className="chat-page__header-left">
            {/* 仅当侧边栏启用且收起时显示菜单按钮 */}
            {showSidebar && sidebarCollapsed && (
              <button
                className="chat-page__menu-btn"
                onClick={() => setSidebarCollapsed(false)}
                title="展开侧边栏"
              >
                <svg
                  width="20"
                  height="20"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <line x1="3" y1="12" x2="21" y2="12" />
                  <line x1="3" y1="6" x2="21" y2="6" />
                  <line x1="3" y1="18" x2="21" y2="18" />
                </svg>
              </button>
            )}
            <h1 className="chat-page__title">联环集团 · 医药政策助手</h1>
          </div>
          <div className="chat-page__header-right">
            <ThemeToggle />
          </div>
        </header>

        {/* 对话容器 */}
        <div className="chat-page__container">
          <div className="chat-page__chat-wrapper">
            <MedpolChat
              mode="rag"
              welcomeMessage="您好！我是医疗政策助手，专注政策法规检索。您可以向我咨询医药政策相关问题，例如：

• 最新的医保政策有哪些变化？
• 药品集采相关政策
• 医疗器械监管规定"
              placeholder="输入您的问题..."
              height="100%"
              defaultFontSize="normal"
              showFontSizeToggle={true}
              initialMessages={activeConversation?.messages}
              initialConversationId={activeConversationId}
              onMessagesChange={handleMessagesChange}
              key={activeConversationId || "new"}
            />
          </div>
        </div>
      </main>
    </div>
  );
}

export default ChatPage;
