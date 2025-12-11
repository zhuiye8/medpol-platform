/**
 * LLMMarkdown - Optimized Markdown renderer for LLM streaming output
 *
 * Uses @llm-ui/react to handle:
 * - Incomplete markdown syntax during streaming
 * - GFM tables, lists, code blocks
 * - Smooth rendering without jank
 */
import { useLLMOutput, type LLMOutputComponent } from "@llm-ui/react";
import { markdownLookBack } from "@llm-ui/markdown";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Components } from "react-markdown";

// Custom components for ReactMarkdown
const markdownComponents: Components = {
  // Wrap tables for horizontal scrolling
  table: ({ children }) => (
    <div className="md-table-wrapper">
      <table>{children}</table>
    </div>
  ),
  // Open links in new tab
  a: ({ href, children }) => (
    <a href={href} target="_blank" rel="noopener noreferrer">
      {children}
    </a>
  ),
  // Code styling
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
  pre: ({ children }) => <pre className="md-pre">{children}</pre>,
};

// Markdown block component for llm-ui
const MarkdownBlock: LLMOutputComponent = ({ blockMatch }) => {
  return (
    <ReactMarkdown
      className="markdown-content"
      remarkPlugins={[remarkGfm]}
      components={markdownComponents}
    >
      {blockMatch.output}
    </ReactMarkdown>
  );
};

export interface LLMMarkdownProps {
  /** The markdown content to render */
  content: string;
  /** Whether the content is still streaming */
  isStreaming?: boolean;
  /** Additional CSS class */
  className?: string;
}

/**
 * LLMMarkdown component - handles LLM output with proper markdown rendering
 *
 * @example
 * <LLMMarkdown content={message.content} isStreaming={message.status === 'streaming'} />
 */
export function LLMMarkdown({
  content,
  isStreaming = false,
  className = "",
}: LLMMarkdownProps) {
  const { blockMatches } = useLLMOutput({
    llmOutput: content,
    blocks: [],
    fallbackBlock: {
      component: MarkdownBlock,
      lookBack: markdownLookBack(),
    },
    isStreamFinished: !isStreaming,
  });

  if (!content) return null;

  return (
    <div className={className}>
      {blockMatches.map((blockMatch, index) => {
        const Component = blockMatch.block.component;
        return <Component key={index} blockMatch={blockMatch} />;
      })}
    </div>
  );
}

export default LLMMarkdown;
