/**
 * EmbedChat - Embeddable chat page for WebView integration
 *
 * URL: /embed/chat?mode=rag|sql|hybrid&token=xxx
 *
 * Features:
 * - Full-screen layout (no sidebar/navigation)
 * - Token-based authentication
 * - Mode selection via URL parameter
 * - Safe area insets for notch/home indicator
 * - Dynamic viewport height for keyboard handling
 */
import { useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { MedpolChat } from "@/components/chat";
import "./EmbedChat.css";

/**
 * Setup viewport meta for safe area support
 * This ensures env(safe-area-inset-*) works correctly
 */
function useViewportSetup() {
  useEffect(() => {
    // Ensure viewport meta has viewport-fit=cover for safe area
    let meta = document.querySelector('meta[name="viewport"]');
    if (!meta) {
      meta = document.createElement("meta");
      meta.setAttribute("name", "viewport");
      document.head.appendChild(meta);
    }
    meta.setAttribute(
      "content",
      "width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover"
    );

    // Handle iOS keyboard via visualViewport
    const updateHeight = () => {
      if (window.visualViewport) {
        document.documentElement.style.setProperty(
          "--app-height",
          `${window.visualViewport.height}px`
        );
      }
    };

    window.visualViewport?.addEventListener("resize", updateHeight);
    updateHeight();

    return () => {
      window.visualViewport?.removeEventListener("resize", updateHeight);
    };
  }, []);
}

type ChatMode = "rag" | "sql" | "hybrid";

const WELCOME_MESSAGES: Record<ChatMode, string> = {
  rag: "您好！我是医疗政策助手，专注政策法规检索。有什么可以帮您的？",
  sql: "您好！我是财务分析助手，可查询联环集团及子公司的财务数据。",
  hybrid: "您好！我是医药政策与财务分析助手，可以同时回答政策与财务问题。",
};

const PLACEHOLDERS: Record<ChatMode, string> = {
  rag: "输入政策相关问题...",
  sql: "输入财务查询问题，如：联环集团9月营业收入",
  hybrid: "输入您的问题...",
};

export default function EmbedChatPage() {
  useViewportSetup();
  const [searchParams] = useSearchParams();

  const mode = (searchParams.get("mode") as ChatMode) || "hybrid";
  const token = searchParams.get("token") || "";

  // Validate mode
  const validModes: ChatMode[] = ["rag", "sql", "hybrid"];
  const safeMode = validModes.includes(mode) ? mode : "hybrid";

  // Show error if token is missing
  if (!token) {
    return (
      <div className="embed-chat embed-chat--error">
        <div className="embed-chat__error-box">
          <h2>认证错误</h2>
          <p>缺少访问令牌。请使用正确的 URL 格式：</p>
          <code>/embed/chat?mode=rag&token=YOUR_TOKEN</code>
        </div>
      </div>
    );
  }

  return (
    <div className="embed-chat">
      <MedpolChat
        mode={safeMode}
        token={token}
        variant="mobile"
        height="100%"
        welcomeMessage={WELCOME_MESSAGES[safeMode]}
        placeholder={PLACEHOLDERS[safeMode]}
        onError={(err) => console.error("[EmbedChat] Error:", err)}
      />
    </div>
  );
}
