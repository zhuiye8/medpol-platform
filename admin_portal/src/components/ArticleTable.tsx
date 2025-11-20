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
    return <div className="panel">加载中...</div>;
  }
  if (!items.length) {
    return <div className="panel empty-state">{emptyText}</div>;
  }
  return (
    <div className="panel">
      <table className="table">
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
                <div>{article.title}</div>
                {article.translated_title ? (
                  <div style={{ color: "#64748b", fontSize: 12 }}>{article.translated_title}</div>
                ) : null}
                {article.is_positive_policy !== null && article.is_positive_policy !== undefined ? (
                  <div style={{ color: article.is_positive_policy ? "#16a34a" : "#b91c1c", fontSize: 12 }}>
                    {article.is_positive_policy ? "利好" : "中性/不利"}
                  </div>
                ) : null}
              </td>
              <td>
                <div>{getCategoryLabel(article.category)}</div>
                {article.status ? (
                  <div style={{ color: "#64748b", fontSize: 12 }}>
                    {getStatusOptions(article.category).find((s) => s.value === article.status)?.label ??
                      article.status}
                  </div>
                ) : null}
              </td>
              <td>{article.source_name}</td>
              <td>{dayjs(article.publish_time).format("YYYY-MM-DD HH:mm")}</td>
              <td style={{ display: "flex", gap: 8 }}>
                <button className="ghost" onClick={() => window.open(article.source_url, "_blank")}>
                  查看原文
                </button>
                {onView ? (
                  <button className="ghost" onClick={() => onView(article)}>
                    详情
                  </button>
                ) : null}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
