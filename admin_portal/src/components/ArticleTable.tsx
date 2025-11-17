import dayjs from "dayjs";
import type { Article } from "@/types/api";
import { getCategoryLabel } from "@/constants/categories";

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
            <th>分类</th>
            <th>来源</th>
            <th>发布时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {items.map((article) => (
            <tr key={article.id}>
              <td style={{ maxWidth: 360 }}>{article.title}</td>
              <td>{getCategoryLabel(article.category)}</td>
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
