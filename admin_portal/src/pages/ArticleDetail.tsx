import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { fetchArticleDetail } from "@/services/api";
import type { ArticleDetail } from "@/types/api";

export default function ArticleDetailPage() {
  const { articleId } = useParams<{ articleId: string }>();
  const [detail, setDetail] = useState<ArticleDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!articleId) {
      return;
    }
    setLoading(true);
    fetchArticleDetail(articleId)
      .then(setDetail)
      .catch((err) => setError(err instanceof Error ? err.message : "加载失败"))
      .finally(() => setLoading(false));
  }, [articleId]);

  if (!articleId) {
    return <div className="panel">缺少文章 ID</div>;
  }

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>文章详情</h1>
          <p className="muted">文章 ID：{articleId}</p>
        </div>
        <Link to="/articles" className="ghost" style={{ textDecoration: "none" }}>
          <button className="ghost">返回列表</button>
        </Link>
      </div>
      {loading ? (
        <div className="empty-state">
          <div className="loading-spinner" style={{ margin: "0 auto" }} />
          <div style={{ marginTop: 12 }}>加载中...</div>
        </div>
      ) : error ? (
        <div className="error">{error}</div>
      ) : detail ? (
        <>
          <section className="panel">
            <h2 style={{ marginTop: 0, fontSize: 20, fontWeight: 600 }}>{detail.translated_title || detail.title}</h2>
            <p className="muted" style={{ marginBottom: 16 }}>
              来源：{detail.source_name} · 发布时间：{new Date(detail.publish_time).toLocaleString()}
            </p>
            <div className="article-content" dangerouslySetInnerHTML={{ __html: detail.content_html }} />
          </section>
          {detail.translated_content_html ? (
            <section className="panel">
              <div className="panel__header">
                <h3>AI 翻译（{detail.original_source_language || "auto"}）</h3>
              </div>
              <div className="article-content" dangerouslySetInnerHTML={{ __html: detail.translated_content_html }} />
            </section>
          ) : null}
          {detail.ai_analysis ? (
            <section className="panel">
              <div className="panel__header">
                <h3>AI 分析</h3>
              </div>
              {detail.ai_analysis.content ? (
                <p style={{ whiteSpace: "pre-wrap", lineHeight: 1.6 }}>{detail.ai_analysis.content}</p>
              ) : null}
              {detail.ai_analysis.is_positive_policy !== undefined &&
              detail.ai_analysis.is_positive_policy !== null ? (
                <span className={`pill ${detail.ai_analysis.is_positive_policy ? "pill--ok" : "pill--warn"}`}>
                  {detail.ai_analysis.is_positive_policy ? "利好政策" : "中性/不利"}
                </span>
              ) : null}
            </section>
          ) : null}
          <section className="panel">
            <div className="panel__header">
              <h3>模型调用记录</h3>
            </div>
            {!detail.ai_results.length ? (
              <div className="empty-state">暂无记录</div>
            ) : (
              <table className="list-table">
                <thead>
                  <tr>
                    <th>任务</th>
                    <th>Provider</th>
                    <th>模型</th>
                    <th>时间</th>
                  </tr>
                </thead>
                <tbody>
                  {detail.ai_results.map((item) => (
                    <tr key={item.id}>
                      <td>{item.task_type}</td>
                      <td>{item.provider}</td>
                      <td>{item.model}</td>
                      <td>{new Date(item.created_at).toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>
        </>
      ) : null}
    </div>
  );
}
