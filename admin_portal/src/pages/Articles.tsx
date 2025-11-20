import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArticleTable } from "@/components/ArticleTable";
import { useArticles } from "@/hooks/useArticles";
import type { ArticleCategory } from "@/types/api";
import { CATEGORY_OPTIONS, getStatusOptions, getCategoryLabel } from "@/constants/categories";

export default function ArticlesPage() {
  const navigate = useNavigate();
  const [category, setCategory] = useState<ArticleCategory | "">("");
  const [status, setStatus] = useState<string>("");
  const [q, setQ] = useState<string>("");

  const { items, loading, refresh, error } = useArticles({
    pageSize: 100,
    category: category || undefined,
    status: status || undefined,
    q: q || undefined,
  });

  const statusOptions = getStatusOptions(category || undefined);

  return (
    <div>
      <div className="page-header">
        <h1>文章列表</h1>
        <span style={{ color: "#64748b" }}>按分类/状态/关键词检索</span>
      </div>

      <div className="toolbar" style={{ justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <select
            value={category}
            onChange={(event) => {
              const value = event.target.value as ArticleCategory | "";
              setCategory(value);
              setStatus("");
            }}
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
          {statusOptions.length ? (
            <select
              value={status}
              onChange={(e) => setStatus(e.target.value)}
              style={{
                borderRadius: 8,
                border: "1px solid #cbd5f5",
                padding: "8px 12px",
                minWidth: 180,
              }}
            >
              <option value="">全部状态</option>
              {statusOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          ) : null}
          <input
            value={q}
            placeholder={`在 ${getCategoryLabel(category || undefined)} 中模糊搜索`}
            onChange={(e) => setQ(e.target.value)}
            style={{ padding: "8px 12px", borderRadius: 8, border: "1px solid #cbd5f5", minWidth: 240 }}
          />
        </div>

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
