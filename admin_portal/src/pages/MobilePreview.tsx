/**
 * MobilePreview - Preview page for embedded chat in admin portal
 *
 * Features:
 * - Clean device frame (no fake notch blocking content)
 * - Mode switcher
 * - Configurable token
 * - Side-by-side preview for multiple modes
 */
import { useState } from "react";
import "./MobilePreview.css";

type ChatMode = "rag" | "sql" | "hybrid";

const MODE_OPTIONS: { value: ChatMode; label: string; desc: string }[] = [
  { value: "sql", label: "财务查询", desc: "查询财务数据" },
  { value: "rag", label: "知识检索", desc: "政策法规检索" },
  { value: "hybrid", label: "混合模式", desc: "财务+政策综合" },
];

// Default token for development
const DEFAULT_TOKEN = "dev-token-123";

export default function MobilePreviewPage() {
  const [mode, setMode] = useState<ChatMode>("sql");
  const [token, setToken] = useState(DEFAULT_TOKEN);
  const [showSettings, setShowSettings] = useState(false);

  // Build embed URL
  const embedUrl = `/embed/chat?mode=${mode}&token=${encodeURIComponent(token)}`;
  const fullUrl = `${window.location.origin}${embedUrl}`;

  return (
    <div className="mobile-preview">
      <div className="page-header">
        <h1>移动端预览</h1>
        <p style={{ color: "#475569", margin: 0 }}>
          模拟 APP WebView 嵌入效果，测试聊天组件在移动端的显示效果。
        </p>
      </div>

      {/* Toolbar */}
      <div className="toolbar" style={{ marginTop: 12 }}>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <span style={{ fontSize: 13, color: "#64748b" }}>对话模式：</span>
          {MODE_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              className={`mobile-preview__mode-btn ${mode === opt.value ? "is-active" : ""}`}
              onClick={() => setMode(opt.value)}
              title={opt.desc}
            >
              {opt.label}
            </button>
          ))}
        </div>
        <button
          className="ghost"
          onClick={() => setShowSettings(!showSettings)}
          style={{ fontSize: 13 }}
        >
          {showSettings ? "隐藏设置" : "显示设置"}
        </button>
      </div>

      {/* Settings panel */}
      {showSettings && (
        <div className="panel" style={{ marginTop: 12, padding: 16 }}>
          <div style={{ marginBottom: 12 }}>
            <label style={{ display: "block", fontSize: 13, color: "#64748b", marginBottom: 4 }}>
              访问令牌 (Token)
            </label>
            <input
              type="text"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              placeholder="输入访问令牌"
              style={{ width: "100%", maxWidth: 400 }}
            />
          </div>
          <div>
            <label style={{ display: "block", fontSize: 13, color: "#64748b", marginBottom: 4 }}>
              嵌入 URL（可直接复制给客户）
            </label>
            <div className="mobile-preview__url-box">
              <code>{fullUrl}</code>
              <button
                className="mobile-preview__copy-btn"
                onClick={() => {
                  navigator.clipboard.writeText(fullUrl);
                }}
                title="复制 URL"
              >
                复制
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Preview container */}
      <div className="mobile-preview__container">
        {/* Device frame - clean design without fake notch */}
        <div className="mobile-preview__device">
          <div className="mobile-preview__status-bar">
            <span className="mobile-preview__time">9:41</span>
            <div className="mobile-preview__status-icons">
              <span>📶</span>
              <span>🔋</span>
            </div>
          </div>
          <iframe
            src={embedUrl}
            className="mobile-preview__iframe"
            title="Mobile Chat Preview"
          />
          <div className="mobile-preview__home-bar" />
        </div>

        {/* Info panel */}
        <div className="mobile-preview__info">
          <h3>客户集成说明</h3>
          <p>将以下 URL 嵌入到 APP 的 WebView 中：</p>
          <code className="mobile-preview__url mobile-preview__url--block">{fullUrl}</code>

          <h4>URL 参数</h4>
          <table className="mobile-preview__params-table">
            <tbody>
              <tr>
                <td><code>mode</code></td>
                <td>
                  <code>rag</code>（知识检索）<br />
                  <code>sql</code>（财务查询）<br />
                  <code>hybrid</code>（混合模式）
                </td>
              </tr>
              <tr>
                <td><code>token</code></td>
                <td>访问令牌（必填）</td>
              </tr>
            </tbody>
          </table>

          <h4>示例问题</h4>
          <ul className="mobile-preview__examples">
            {mode === "rag" && (
              <>
                <li>最新的药品网售政策？</li>
                <li>江苏省医保局关于集采的通知？</li>
              </>
            )}
            {mode === "sql" && (
              <>
                <li>联环集团 2024 年 9 月营业收入？</li>
                <li>对比联环药业各月利润变化</li>
              </>
            )}
            {mode === "hybrid" && (
              <>
                <li>联环集团今年的营收情况？</li>
                <li>结合政策分析营收下降原因</li>
              </>
            )}
          </ul>

          <h4>WebView 配置建议</h4>
          <ul className="mobile-preview__tips">
            <li>iOS: 设置 <code>webView.scrollView.contentInsetAdjustmentBehavior = .never</code></li>
            <li>Android: 设置 <code>webView.settings.useWideViewPort = true</code></li>
            <li>启用 JavaScript 和 DOM Storage</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
