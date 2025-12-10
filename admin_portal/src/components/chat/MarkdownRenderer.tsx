/**
 * MarkdownRenderer - Renders markdown content with GFM support
 *
 * Features:
 * - Tables with responsive wrapper
 * - External links open in new tab
 * - Code blocks with syntax highlighting styles
 * - Lists, blockquotes, and other GFM elements
 */
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Components } from "react-markdown";

interface MarkdownRendererProps {
  content: string;
  className?: string;
}

const components: Components = {
  // Wrap tables for horizontal scrolling
  table: ({ children }) => (
    <div className="md-table-wrapper">
      <table>{children}</table>
    </div>
  ),
  // External links open in new tab
  a: ({ href, children }) => (
    <a href={href} target="_blank" rel="noopener noreferrer">
      {children}
    </a>
  ),
  // Code blocks with language class
  code: ({ className, children, ...props }) => {
    const isInline = !className;
    if (isInline) {
      return (
        <code className="md-inline-code" {...props}>
          {children}
        </code>
      );
    }
    return (
      <code className={`md-code-block ${className || ""}`} {...props}>
        {children}
      </code>
    );
  },
  // Pre wrapper for code blocks
  pre: ({ children }) => <pre className="md-pre">{children}</pre>,
};

export function MarkdownRenderer({ content, className = "" }: MarkdownRendererProps) {
  if (!content) return null;

  return (
    <ReactMarkdown
      className={`markdown-content ${className}`}
      remarkPlugins={[remarkGfm]}
      components={components}
    >
      {content}
    </ReactMarkdown>
  );
}

export default MarkdownRenderer;
