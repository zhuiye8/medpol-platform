import dayjs from "dayjs";
import type { Article } from "@/types/api";
import { getCategoryLabel, getStatusOptions } from "@/constants/categories";

interface ArticleTableProps {
  items: Article[];
  loading?: boolean;
  emptyText?: string;
  onView?: (article: Article) => void;
}

export function ArticleTable({
  items,
  loading = false,
  emptyText = "暂无数据",
  onView,
}: ArticleTableProps) {
  if (loading) {
    return (
      <div className="empty-state">
        <div className="loading-spinner" style={{ margin: "0 auto" }} />
        <div style={{ marginTop: 12 }}>加载中...</div>
      </div>
    );
  }
  if (!items.length) {
    return <div className="empty-state">{emptyText}</div>;
  }
  return (
    <table className="list-table">
      <thead>
        <tr>
          <th>标题</th>
          <th>分类 / 状态</th>
          <th>来源</th>
          <th>发布时间</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        {items.map((article) => (
          <tr key={article.id}>
            <td style={{ maxWidth: 360 }}>
              <div style={{ fontWeight: 500 }}>{article.title}</div>
              {article.translated_title ? (
                <div className="muted small" style={{ marginTop: 4 }}>{article.translated_title}</div>
              ) : null}
              {article.is_positive_policy !== null && article.is_positive_policy !== undefined ? (
                <span
                  className={`pill ${article.is_positive_policy ? "pill--ok" : "pill--warn"}`}
                  style={{ marginTop: 6 }}
                >
                  {article.is_positive_policy ? "利好" : "中性/不利"}
                </span>
              ) : null}
            </td>
            <td>
              <div style={{ fontWeight: 500 }}>{getCategoryLabel(article.category)}</div>
              {article.status ? (
                <div className="muted small" style={{ marginTop: 4 }}>
                  {getStatusOptions(article.category).find((s) => s.value === article.status)?.label ??
                    article.status}
                </div>
              ) : null}
            </td>
            <td>{article.source_name}</td>
            <td>{dayjs(article.publish_time).format("YYYY-MM-DD HH:mm")}</td>
            <td className="table-actions">
              <button className="link-btn" onClick={() => window.open(article.source_url, "_blank")}>
                原文
              </button>
              {onView ? (
                <button className="link-btn" onClick={() => onView(article)}>
                  详情
                </button>
              ) : null}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
