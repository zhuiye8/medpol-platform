/**
 * Article Detail Modal
 * Displays article content in a modal popup instead of navigating to detail page.
 * Shows: title, source, publish time, content, translation (if available)
 * Does NOT show: AI analysis, model call records
 */
import { useState, useEffect } from "react";

const DEFAULT_API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

interface ArticleDetail {
  id: string;
  title: string;
  translated_title?: string;
  content_html: string;
  translated_content_html?: string;
  source_name: string;
  publish_time: string;
  original_source_language?: string;
}

interface ArticleModalProps {
  articleId: string | null;
  onClose: () => void;
  apiBase?: string;
}

export function ArticleModal({ articleId, onClose, apiBase }: ArticleModalProps) {
  const [article, setArticle] = useState<ArticleDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!articleId) {
      setArticle(null);
      return;
    }

    const fetchArticle = async () => {
      setLoading(true);
      setError(null);
      try {
        const base = apiBase || DEFAULT_API_BASE;
        const resp = await fetch(`${base}/v1/articles/${articleId}`);
        if (!resp.ok) {
          throw new Error(`HTTP ${resp.status}`);
        }
        const json = await resp.json();
        if (json.code === 0 && json.data) {
          setArticle(json.data);
        } else {
          throw new Error(json.msg || "Failed to load article");
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load article");
      } finally {
        setLoading(false);
      }
    };

    fetchArticle();
  }, [articleId, apiBase]);

  if (!articleId) return null;

  const displayTitle = article?.translated_title || article?.title || "";

  // Intercept link clicks to prevent navigation
  const handleContentClick = (e: React.MouseEvent) => {
    const target = e.target as HTMLElement;
    if (target.tagName === "A" || target.closest("a")) {
      e.preventDefault();
      e.stopPropagation();
    }
  };

  return (
    <div className="article-modal__overlay" onClick={onClose}>
      <div className="article-modal__container" onClick={(e) => e.stopPropagation()}>
        <button className="article-modal__close" onClick={onClose} aria-label="Close">
          ×
        </button>

        {loading && (
          <div className="article-modal__loading">
            <div className="article-modal__spinner" />
            <span>加载中...</span>
          </div>
        )}

        {error && (
          <div className="article-modal__error">
            <span>加载失败: {error}</span>
            <button onClick={onClose}>关闭</button>
          </div>
        )}

        {article && !loading && (
          <div className="article-modal__content" onClick={handleContentClick}>
            <h2 className="article-modal__title">{displayTitle}</h2>
            <div className="article-modal__meta">
              {article.source_name && <span>📰 {article.source_name}</span>}
              {article.publish_time && (
                <span>📅 {new Date(article.publish_time).toLocaleDateString("zh-CN")}</span>
              )}
            </div>

            <div className="article-modal__divider" />

            <div
              className="article-modal__body markdown-content"
              dangerouslySetInnerHTML={{ __html: article.content_html }}
            />

            {article.translated_content_html && (
              <>
                <div className="article-modal__translation-header">
                  <span className="article-modal__translation-label">译文</span>
                  {article.original_source_language && (
                    <span className="article-modal__translation-lang">
                      原文: {article.original_source_language.toUpperCase()}
                    </span>
                  )}
                </div>
                <div
                  className="article-modal__body article-modal__translation markdown-content"
                  dangerouslySetInnerHTML={{ __html: article.translated_content_html }}
                />
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default ArticleModal;
