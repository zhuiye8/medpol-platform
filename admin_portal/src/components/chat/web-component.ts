/**
 * Web Component wrapper for MedpolChat
 *
 * Usage in external apps:
 * <script src="https://your-domain.com/medpol-chat.js"></script>
 * <medpol-chat
 *   api-base="https://api.example.com/v1/ai"
 *   mode="hybrid"
 * ></medpol-chat>
 */
import React from "react";
import { createRoot, Root } from "react-dom/client";
import { MedpolChat, MedpolChatProps } from "./MedpolChat";

// Import styles
import "./MedpolChat.css";

class MedpolChatElement extends HTMLElement {
  private root: Root | null = null;
  private mountPoint: HTMLDivElement | null = null;

  // Observed attributes
  static get observedAttributes() {
    return ["api-base", "mode", "height", "welcome-message", "placeholder"];
  }

  constructor() {
    super();
    // Create shadow DOM for style isolation
    this.attachShadow({ mode: "open" });
  }

  connectedCallback() {
    this.render();
  }

  disconnectedCallback() {
    if (this.root) {
      this.root.unmount();
      this.root = null;
    }
  }

  attributeChangedCallback() {
    this.render();
  }

  private getProps(): MedpolChatProps {
    return {
      apiBase: this.getAttribute("api-base") || undefined,
      mode: (this.getAttribute("mode") as "rag" | "sql" | "hybrid") || "hybrid",
      height: this.getAttribute("height") || "500px",
      welcomeMessage: this.getAttribute("welcome-message") || undefined,
      placeholder: this.getAttribute("placeholder") || undefined,
    };
  }

  private render() {
    if (!this.shadowRoot) return;

    // Create mount point if not exists
    if (!this.mountPoint) {
      // Inject styles into shadow DOM
      const style = document.createElement("style");
      style.textContent = this.getStyles();
      this.shadowRoot.appendChild(style);

      this.mountPoint = document.createElement("div");
      this.mountPoint.className = "medpol-chat-root";
      this.shadowRoot.appendChild(this.mountPoint);

      this.root = createRoot(this.mountPoint);
    }

    // Render React component
    this.root?.render(React.createElement(MedpolChat, this.getProps()));
  }

  private getStyles(): string {
    // Include critical styles inline for shadow DOM
    return `
      .medpol-chat-root {
        width: 100%;
        height: 100%;
      }

      /* ======================== Container ======================== */
      .medpol-chat {
        display: flex;
        flex-direction: column;
        background: #f8fafc;
        border-radius: 12px;
        overflow: hidden;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      }

      .medpol-chat__messages {
        flex: 1;
        overflow-y: auto;
        padding: 16px;
        display: flex;
        flex-direction: column;
        gap: 16px;
      }

      .medpol-chat__welcome,
      .medpol-chat__message {
        display: flex;
        gap: 10px;
        align-items: flex-start;
        max-width: 90%;
      }

      .medpol-chat__message--user {
        align-self: flex-end;
        flex-direction: row-reverse;
      }

      .medpol-chat__message--assistant {
        align-self: flex-start;
      }

      .medpol-chat__avatar {
        width: 36px;
        height: 36px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 12px;
        font-weight: 600;
        flex-shrink: 0;
      }

      .medpol-chat__avatar--user {
        background: #3b82f6;
        color: white;
      }

      .medpol-chat__avatar--assistant {
        background: #10b981;
        color: white;
      }

      .medpol-chat__content {
        display: flex;
        flex-direction: column;
        gap: 8px;
        max-width: calc(100% - 46px);
      }

      .medpol-chat__bubble {
        padding: 12px 16px;
        border-radius: 16px;
        line-height: 1.5;
        word-wrap: break-word;
        white-space: normal;
      }

      .medpol-chat__bubble--user {
        background: #3b82f6;
        color: white;
        border-bottom-right-radius: 4px;
        white-space: pre-wrap;
      }

      .medpol-chat__bubble--assistant {
        background: white;
        color: #1e293b;
        border-bottom-left-radius: 4px;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
      }

      .medpol-chat__bubble--streaming {
        animation: pulse 1.5s ease-in-out infinite;
      }

      /* Markdown 内容行距与缩进 */
      .markdown-content {
        line-height: 1.5;
        font-size: 14px;
        white-space: normal;
      }

      .markdown-content p {
        margin: 0.25em 0;
      }

      .markdown-content p + p {
        margin-top: 0.25em;
      }

      .markdown-content ul,
      .markdown-content ol {
        margin: 0.25em 0;
        padding-left: 1.25em;
        list-style-position: outside;
      }

      .markdown-content li {
        margin: 0.15em 0;
        line-height: 1.45;
      }

      .markdown-content strong {
        font-weight: 600;
      }

      @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.8; }
      }

      .medpol-chat__typing {
        color: #64748b;
        font-style: italic;
      }

      .medpol-chat__cursor {
        display: inline-block;
        width: 2px;
        height: 1em;
        background: #3b82f6;
        margin-left: 2px;
        animation: blink 1s step-end infinite;
      }

      @keyframes blink {
        0%, 100% { opacity: 1; }
        50% { opacity: 0; }
      }

      .medpol-chat__components {
        display: flex;
        flex-direction: column;
        gap: 12px;
      }

      .medpol-chat__component {
        background: white;
        border-radius: 12px;
        overflow: hidden;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
      }

      .medpol-chat__status {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 8px 16px;
        color: #64748b;
        font-size: 13px;
      }

      .medpol-chat__status-dot {
        width: 8px;
        height: 8px;
        background: #3b82f6;
        border-radius: 50%;
        animation: pulse 1s ease-in-out infinite;
      }

      .medpol-chat__tool-badge {
        padding: 2px 8px;
        background: #e0f2fe;
        color: #0369a1;
        border-radius: 4px;
        font-size: 11px;
        font-weight: 500;
      }

      .medpol-chat__error {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 12px 16px;
        background: #fee2e2;
        color: #991b1b;
        border-radius: 8px;
        font-size: 13px;
      }

      .medpol-chat__error button {
        padding: 4px 12px;
        background: white;
        border: 1px solid #ef4444;
        color: #ef4444;
        border-radius: 4px;
        cursor: pointer;
        font-size: 12px;
      }

      .medpol-chat__input-area {
        display: flex;
        gap: 8px;
        padding: 12px 16px;
        background: white;
        border-top: 1px solid #e2e8f0;
      }

      .medpol-chat__input {
        flex: 1;
        padding: 10px 14px;
        border: 1px solid #e2e8f0;
        border-radius: 20px;
        font-size: 14px;
        line-height: 1.4;
        resize: none;
        outline: none;
        max-height: 150px;
        font-family: inherit;
      }

      .medpol-chat__input:focus {
        border-color: #3b82f6;
        box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
      }

      .medpol-chat__input:disabled {
        background: #f1f5f9;
        cursor: not-allowed;
      }

      .medpol-chat__actions {
        display: flex;
        align-items: flex-end;
      }

      .medpol-chat__btn {
        padding: 10px 20px;
        border: none;
        border-radius: 20px;
        font-size: 14px;
        font-weight: 500;
        cursor: pointer;
        transition: all 0.2s;
      }

      .medpol-chat__btn--send {
        background: #3b82f6;
        color: white;
      }

      .medpol-chat__btn--send:hover:not(:disabled) {
        background: #2563eb;
      }

      .medpol-chat__btn--send:disabled {
        background: #cbd5e1;
        cursor: not-allowed;
      }

      .medpol-chat__btn--cancel {
        background: #ef4444;
        color: white;
      }

      .medpol-chat__btn--cancel:hover {
        background: #dc2626;
      }

      /* DataFrame, Chart, Search Results styles... */
      .chat-dataframe,
      .chat-chart,
      .chat-search-results {
        padding: 12px;
      }

      .chat-dataframe__title,
      .chat-chart__title,
      .chat-search-results__title {
        margin: 0 0 12px;
        font-size: 14px;
        font-weight: 600;
        color: #1e293b;
      }

      .chat-dataframe__wrapper {
        overflow-x: auto;
        -webkit-overflow-scrolling: touch;
      }

      .chat-dataframe__table {
        width: 100%;
        border-collapse: collapse;
        font-size: 13px;
      }

      .chat-dataframe__table th,
      .chat-dataframe__table td {
        padding: 8px 12px;
        text-align: left;
        border-bottom: 1px solid #e2e8f0;
        white-space: nowrap;
      }

      .chat-dataframe__table th {
        background: #f8fafc;
        font-weight: 600;
        color: #475569;
      }

      .chat-dataframe__count {
        margin: 8px 0 0;
        font-size: 12px;
        color: #64748b;
      }

      .chat-chart__container {
        min-height: 250px;
      }

      .chat-search-results__list {
        display: flex;
        flex-direction: column;
        gap: 12px;
      }

      .chat-search-item {
        padding: 12px;
        background: #f8fafc;
        border-radius: 8px;
        border-left: 3px solid #3b82f6;
      }

      .chat-search-item__header {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        gap: 8px;
        margin-bottom: 8px;
      }

      .chat-search-item__title {
        font-size: 14px;
        font-weight: 500;
        color: #1e40af;
        text-decoration: none;
      }

      .chat-search-item__score {
        padding: 2px 6px;
        background: #dbeafe;
        color: #1e40af;
        border-radius: 4px;
        font-size: 11px;
      }

      .chat-search-item__text {
        margin: 0 0 8px;
        font-size: 13px;
        color: #475569;
        line-height: 1.5;
      }

      .chat-search-item__meta {
        display: flex;
        gap: 12px;
        font-size: 12px;
        color: #64748b;
      }

      .chat-empty {
        padding: 24px;
        text-align: center;
        color: #64748b;
      }

      /* Mobile optimization */
      @media (max-width: 480px) {
        .medpol-chat__messages {
          padding: 12px;
        }

        .medpol-chat__message {
          max-width: 95%;
        }

        .medpol-chat__bubble {
          padding: 10px 14px;
          font-size: 14px;
        }

        .medpol-chat__avatar {
          width: 32px;
          height: 32px;
          font-size: 11px;
        }
      }
    `;
  }
}

// Register custom element
export function registerMedpolChatElement() {
  if (!customElements.get("medpol-chat")) {
    customElements.define("medpol-chat", MedpolChatElement);
  }
}

// Auto-register if running in browser
if (typeof window !== "undefined") {
  registerMedpolChatElement();
}

export default MedpolChatElement;
