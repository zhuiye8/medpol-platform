/**
 * useConversationHistory - 对话历史管理钩子（基于 localStorage）
 *
 * 功能：
 * - 保存对话到 localStorage
 * - 加载对话历史
 * - 切换对话
 * - 删除对话
 * - 自动从首条消息生成标题
 * - 最多保存 20 条对话
 */
import { useState, useCallback, useEffect } from "react";
import type { ChatMessage } from "@/components/chat/types";

const STORAGE_KEY = "medpol_chat_history";
const MAX_CONVERSATIONS = 20;

export interface Conversation {
  id: string;
  title: string;
  createdAt: number;
  updatedAt: number;
  messages: ChatMessage[];
}

export interface ConversationHistory {
  conversations: Conversation[];
  activeConversationId: string | null;
}

function generateConversationId(): string {
  return `conv_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
}

function generateTitle(messages: ChatMessage[]): string {
  const firstUserMessage = messages.find((m) => m.role === "user");
  if (!firstUserMessage) return "新对话";

  const content = firstUserMessage.content.trim();
  if (content.length <= 30) return content;
  return content.slice(0, 30) + "...";
}

function loadFromStorage(): ConversationHistory {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (!stored) {
      return { conversations: [], activeConversationId: null };
    }
    const parsed = JSON.parse(stored);
    // 恢复 Date 对象
    parsed.conversations = parsed.conversations.map((conv: any) => ({
      ...conv,
      messages: conv.messages.map((msg: any) => ({
        ...msg,
        timestamp: new Date(msg.timestamp),
      })),
    }));
    return parsed;
  } catch (err) {
    console.error("加载对话历史失败:", err);
    return { conversations: [], activeConversationId: null };
  }
}

function saveToStorage(history: ConversationHistory): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(history));
  } catch (err) {
    console.error("保存对话历史失败:", err);
    // 存储已满时，尝试删除最旧的对话
    if (err instanceof DOMException && err.name === "QuotaExceededError") {
      const trimmed = {
        ...history,
        conversations: history.conversations.slice(-10), // Keep only last 10
      };
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(trimmed));
      } catch {
        console.error("裁剪后仍然保存失败");
      }
    }
  }
}

export function useConversationHistory() {
  const [history, setHistory] = useState<ConversationHistory>(() => loadFromStorage());

  // 历史变化时持久化到 localStorage
  useEffect(() => {
    saveToStorage(history);
  }, [history]);

  // 获取当前活动对话
  const activeConversation = history.activeConversationId
    ? history.conversations.find((c) => c.id === history.activeConversationId)
    : null;

  // 创建新对话
  const createConversation = useCallback((): Conversation => {
    const newConv: Conversation = {
      id: generateConversationId(),
      title: "新对话",
      createdAt: Date.now(),
      updatedAt: Date.now(),
      messages: [],
    };

    setHistory((prev) => {
      let conversations = [newConv, ...prev.conversations];
      // 限制最大对话数
      if (conversations.length > MAX_CONVERSATIONS) {
        conversations = conversations.slice(0, MAX_CONVERSATIONS);
      }
      return {
        conversations,
        activeConversationId: newConv.id,
      };
    });

    return newConv;
  }, []);

  // 更新当前对话的消息
  const updateMessages = useCallback(
    (messages: ChatMessage[], conversationId: string | null) => {
      setHistory((prev) => {
        let convId = conversationId || prev.activeConversationId;

        if (!convId && messages.length === 0) {
          return prev;
        }

        // 如果没有活动对话但有消息，则创建新对话
        if (!convId && messages.length > 0) {
          const newConv: Conversation = {
            id: generateConversationId(),
            title: generateTitle(messages),
            createdAt: Date.now(),
            updatedAt: Date.now(),
            messages,
          };
          let conversations = [newConv, ...prev.conversations];
          if (conversations.length > MAX_CONVERSATIONS) {
            conversations = conversations.slice(0, MAX_CONVERSATIONS);
          }
          return {
            conversations,
            activeConversationId: newConv.id,
          };
        }

        const exists = convId
          ? prev.conversations.some((conv) => conv.id === convId)
          : false;

        // 如果传入了会话 ID 但不存在，则创建新对话
        if (convId && !exists && messages.length > 0) {
          const newConv: Conversation = {
            id: convId,
            title: generateTitle(messages),
            createdAt: Date.now(),
            updatedAt: Date.now(),
            messages,
          };
          let conversations = [newConv, ...prev.conversations];
          if (conversations.length > MAX_CONVERSATIONS) {
            conversations = conversations.slice(0, MAX_CONVERSATIONS);
          }
          return {
            conversations,
            activeConversationId: convId,
          };
        }

        // 更新现有对话
        const conversations = prev.conversations.map((conv) => {
          if (conv.id === convId) {
            return {
              ...conv,
              title: conv.title === "新对话" ? generateTitle(messages) : conv.title,
              updatedAt: Date.now(),
              messages,
            };
          }
          return conv;
        });

        return {
          ...prev,
          conversations,
        };
      });
    },
    []
  );

  // 切换到其他对话
  const switchConversation = useCallback((conversationId: string) => {
    setHistory((prev) => ({
      ...prev,
      activeConversationId: conversationId,
    }));
  }, []);

  // 删除对话
  const deleteConversation = useCallback((conversationId: string) => {
    setHistory((prev) => {
      const conversations = prev.conversations.filter((c) => c.id !== conversationId);
      let activeConversationId = prev.activeConversationId;

      // 如果删除的是当前对话，切换到第一个或置空
      if (activeConversationId === conversationId) {
        activeConversationId = conversations.length > 0 ? conversations[0].id : null;
      }

      return {
        conversations,
        activeConversationId,
      };
    });
  }, []);

  // 清空所有对话
  const clearAllConversations = useCallback(() => {
    setHistory({
      conversations: [],
      activeConversationId: null,
    });
  }, []);

  // 开始新对话（创建新对话并切换）
  const startNewChat = useCallback(() => {
    createConversation();
  }, [createConversation]);

  return {
    conversations: history.conversations,
    activeConversation,
    activeConversationId: history.activeConversationId,
    createConversation,
    updateMessages,
    switchConversation,
    deleteConversation,
    clearAllConversations,
    startNewChat,
  };
}

export default useConversationHistory;
