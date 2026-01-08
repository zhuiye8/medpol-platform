/**
 * Sidebar - 对话历史侧边栏
 */
import dayjs from "dayjs";
import type { Conversation } from "@/hooks/useConversationHistory";

interface SidebarProps {
  conversations: Conversation[];
  activeConversationId: string | null;
  onNewChat: () => void;
  onSelectConversation: (id: string) => void;
  onDeleteConversation: (id: string) => void;
  isCollapsed: boolean;
  onToggleCollapse: () => void;
}

export function Sidebar({
  conversations,
  activeConversationId,
  onNewChat,
  onSelectConversation,
  onDeleteConversation,
  isCollapsed,
  onToggleCollapse,
}: SidebarProps) {
  return (
    <aside className={`sidebar ${isCollapsed ? "sidebar--collapsed" : ""}`}>
      {/* Header */}
      <div className="sidebar__header">
        {!isCollapsed && (
          <>
            <div className="sidebar__logo">
              <span className="sidebar__logo-icon">🏢</span>
              <span className="sidebar__logo-text">联环集团</span>
            </div>
            <button className="sidebar__new-chat" onClick={onNewChat}>
              <svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <line x1="12" y1="5" x2="12" y2="19" />
                <line x1="5" y1="12" x2="19" y2="12" />
              </svg>
              <span>新对话</span>
            </button>
          </>
        )}
        <button
          className="sidebar__toggle"
          onClick={onToggleCollapse}
          title={isCollapsed ? "展开侧边栏" : "收起侧边栏"}
        >
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            style={{
              transform: isCollapsed ? "rotate(180deg)" : "rotate(0deg)",
              transition: "transform 0.2s ease",
            }}
          >
            <path d="M15 18l-6-6 6-6" />
          </svg>
        </button>
      </div>

      {/* Conversation List */}
      {!isCollapsed && (
        <div className="sidebar__list">
          {conversations.length === 0 ? (
            <div className="sidebar__empty">
              <p>暂无历史对话</p>
              <p className="sidebar__empty-hint">点击「新对话」开始</p>
            </div>
          ) : (
            conversations.map((conv) => (
              <ConversationItem
                key={conv.id}
                conversation={conv}
                isActive={conv.id === activeConversationId}
                onSelect={() => onSelectConversation(conv.id)}
                onDelete={() => onDeleteConversation(conv.id)}
              />
            ))
          )}
        </div>
      )}

      {/* Footer */}
      {!isCollapsed && (
        <div className="sidebar__footer">
          <p className="sidebar__footer-text">
            对话保存在本地浏览器
          </p>
        </div>
      )}
    </aside>
  );
}

interface ConversationItemProps {
  conversation: Conversation;
  isActive: boolean;
  onSelect: () => void;
  onDelete: () => void;
}

function ConversationItem({
  conversation,
  isActive,
  onSelect,
  onDelete,
}: ConversationItemProps) {
  const handleDelete = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (window.confirm("确定要删除这个对话吗？")) {
      onDelete();
    }
  };

  const timeLabel = formatTimeLabel(conversation.updatedAt);

  return (
    <div
      className={`conversation-item ${isActive ? "conversation-item--active" : ""}`}
      onClick={onSelect}
    >
      <div className="conversation-item__icon">💬</div>
      <div className="conversation-item__content">
        <div className="conversation-item__title">{conversation.title}</div>
        <div className="conversation-item__meta">
          <span className="conversation-item__time">{timeLabel}</span>
          <span className="conversation-item__count">
            {conversation.messages.filter((m) => m.role === "user").length} 条问题
          </span>
        </div>
      </div>
      <button
        className="conversation-item__delete"
        onClick={handleDelete}
        title="删除对话"
      >
        <svg
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M3 6h18" />
          <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6" />
          <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2" />
        </svg>
      </button>
    </div>
  );
}

function formatTimeLabel(timestamp: number): string {
  const now = dayjs();
  const date = dayjs(timestamp);

  if (now.isSame(date, "day")) {
    return date.format("HH:mm");
  }

  if (now.subtract(1, "day").isSame(date, "day")) {
    return "昨天";
  }

  if (now.isSame(date, "year")) {
    return date.format("M月D日");
  }

  return date.format("YYYY/M/D");
}

export default Sidebar;
