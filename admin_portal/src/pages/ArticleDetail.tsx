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
    <div>
      <div className="page-header">
        <h1>文章详情</h1>
        <span style={{ color: "#64748b" }}>文章 ID：{articleId}</span>
        <Link to="/articles" className="ghost" style={{ marginTop: 8 }}>
          返回列表
        </Link>
      </div>
      {loading ? (
        <div className="panel">加载中...</div>
      ) : error ? (
        <div className="panel" style={{ color: "#b91c1c" }}>
          {error}
        </div>
      ) : detail ? (
        <>
          <div className="panel">
            <h2>{detail.translated_title || detail.title}</h2>
            <p style={{ color: "#64748b" }}>
              来源：{detail.source_name} · 发布时间：{new Date(detail.publish_time).toLocaleString()}
            </p>
            <div dangerouslySetInnerHTML={{ __html: detail.content_html }} />
          </div>
          {detail.translated_content_html ? (
            <div className="panel" style={{ marginTop: 24 }}>
              <h3>AI 翻译（{detail.original_source_language || "auto"}）</h3>
              <div dangerouslySetInnerHTML={{ __html: detail.translated_content_html }} />
            </div>
          ) : null}
          {detail.ai_analysis ? (
            <div className="panel" style={{ marginTop: 24 }}>
              <h3>AI 分析</h3>
              {detail.ai_analysis.content ? (
                <p style={{ whiteSpace: "pre-wrap", marginTop: 8 }}>{detail.ai_analysis.content}</p>
              ) : null}
              {detail.ai_analysis.is_positive_policy !== undefined &&
              detail.ai_analysis.is_positive_policy !== null ? (
                <p style={{ color: detail.ai_analysis.is_positive_policy ? "#16a34a" : "#b91c1c" }}>
                  {detail.ai_analysis.is_positive_policy ? "利好政策" : "中性/不利"}
                </p>
              ) : null}
            </div>
          ) : null}
          <div className="panel" style={{ marginTop: 24 }}>
            <h3>模型调用记录</h3>
            {!detail.ai_results.length ? (
              <div className="empty-state">暂无记录</div>
            ) : (
              <table className="table">
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
          </div>
        </>
      ) : null}
    </div>
  );
}
