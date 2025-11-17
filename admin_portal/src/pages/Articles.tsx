import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArticleTable } from "@/components/ArticleTable";
import { useArticles } from "@/hooks/useArticles";
import type { ArticleCategory } from "@/types/api";
import { CATEGORY_OPTIONS } from "@/constants/categories";

export default function ArticlesPage() {
  const navigate = useNavigate();
  const [category, setCategory] = useState<ArticleCategory | "">("");
  const { items, loading, refresh, error } = useArticles({
    pageSize: 100,
    category: category || undefined,
  });

  return (
    <div>
      <div className="page-header">
        <h1>文章列表</h1>
        <span style={{ color: "#64748b" }}>查询最新格式化入库的政策内容</span>
      </div>

      <div className="toolbar" style={{ justifyContent: "space-between" }}>
        <select
          value={category}
          onChange={(event) => setCategory(event.target.value as ArticleCategory | "")}
          style={{
            borderRadius: 8,
            border: "1px solid #cbd5f5",
            padding: "8px 12px",
            minWidth: 220,
          }}
        >
          <option value="">全部分类</option>
          {CATEGORY_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        <button className="primary" onClick={refresh}>
          刷新
        </button>
      </div>
      {error ? <div style={{ color: "#b91c1c", marginBottom: 12 }}>加载失败：{error}</div> : null}
      <ArticleTable
        items={items}
        loading={loading}
        emptyText="暂无文章，请稍后再试"
        onView={(article) => navigate(`/articles/${article.id}`)}
      />
    </div>
  );
}
