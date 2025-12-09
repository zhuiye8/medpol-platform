import { useEffect, useMemo, useState } from "react";
import dayjs from "dayjs";
import {
  fetchEmbeddingArticleDetail,
  fetchEmbeddingArticles,
  fetchEmbeddingStats,
  fetchTaskStatus,
  triggerEmbeddingIndex,
} from "@/services/adminOps";
import type { EmbeddingArticle, EmbeddingChunk, EmbeddingStats } from "@/types/admin";

const TERMINAL_STATES = ["SUCCESS", "FAILURE", "REVOKED"];

export default function EmbeddingsPage() {
  const [stats, setStats] = useState<EmbeddingStats | null>(null);
  const [articles, setArticles] = useState<EmbeddingArticle[]>([]);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [chunksMap, setChunksMap] = useState<Record<string, EmbeddingChunk[]>>({});
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [taskId, setTaskId] = useState<string | null>(null);
  const [taskState, setTaskState] = useState<string | null>(null);
  const [indexing, setIndexing] = useState(false);

  const embeddedRate = useMemo(() => {
    if (!stats) return "-";
    if (!stats.total_articles) return "0%";
    const pct = ((stats.embedded_articles / stats.total_articles) * 100).toFixed(1);
    return `${pct}%`;
  }, [stats]);

  async function loadData() {
    setLoading(true);
    setError(null);
    try {
      const [s, arts] = await Promise.all([fetchEmbeddingStats(), fetchEmbeddingArticles(50)]);
      setStats(s);
      setArticles(arts);
    } catch (err) {
      setError((err as Error).message || "加载失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadData();
  }, []);

  useEffect(() => {
    if (!taskId) return;
    setIndexing(true);
    setTaskState("PENDING");
    const timer = setInterval(async () => {
      try {
        const res = await fetchTaskStatus(taskId);
        setTaskState(res.state);
        if (TERMINAL_STATES.includes(res.state)) {
          clearInterval(timer);
          setIndexing(false);
          loadData();
        }
      } catch (err) {
        setTaskState("FAILED");
        setError((err as Error).message || "任务状态获取失败");
        clearInterval(timer);
        setIndexing(false);
      }
    }, 2000);
    return () => clearInterval(timer);
  }, [taskId]);

  function toggleSelect(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }

  async function toggleExpand(articleId: string) {
    if (expanded === articleId) {
      setExpanded(null);
      return;
    }
    setExpanded(articleId);
    if (chunksMap[articleId]) return;
    try {
      const chunks = await fetchEmbeddingArticleDetail(articleId);
      setChunksMap((prev) => ({ ...prev, [articleId]: chunks }));
    } catch (err) {
      setError((err as Error).message || "获取切片失败");
    }
  }

  async function handleIndex() {
    setError(null);
    try {
      const payload =
        selected.size > 0 ? { article_ids: Array.from(selected), all: false } : { all: true };
      const res = await triggerEmbeddingIndex(payload);
      setTaskId(res.task_id);
    } catch (err) {
      setError((err as Error).message || "触发向量化失败");
    }
  }

  function toggleSelectAll() {
    if (!articles.length) return;
    setSelected((prev) => {
      if (prev.size === articles.length) {
        return new Set();
      }
      return new Set(articles.map((a) => a.id));
    });
  }

  return (
    <div>
      <div className="page-header">
        <h1>向量化管理</h1>
        <p style={{ color: "#475569", margin: 0 }}>查看文章索引覆盖率，支持选中文章或全量重新向量化</p>
      </div>

      <div className="toolbar">
        <div style={{ display: "flex", gap: 12 }}>
          <div className="panel small">
            <div className="panel__title">文章总数</div>
            <div className="panel__value">{stats?.total_articles ?? "--"}</div>
          </div>
          <div className="panel small">
            <div className="panel__title">已向量化文章</div>
            <div className="panel__value">{stats?.embedded_articles ?? "--"}</div>
          </div>
          <div className="panel small">
            <div className="panel__title">切片总数</div>
            <div className="panel__value">{stats?.total_chunks ?? "--"}</div>
          </div>
          <div className="panel small">
            <div className="panel__title">覆盖率</div>
            <div className="panel__value">{embeddedRate}</div>
          </div>
          <div className="panel small">
            <div className="panel__title">任务状态</div>
            <div className="panel__value">{taskState || "未触发"}</div>
          </div>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button onClick={handleIndex} disabled={indexing}>
            {indexing ? "向量化中..." : selected.size ? `向量化选中(${selected.size})` : "全量向量化"}
          </button>
          <button className="ghost" onClick={loadData} disabled={loading}>
            刷新
          </button>
        </div>
      </div>

      {error ? <div className="error-banner">错误：{error}</div> : null}

      <div className="panel" style={{ marginTop: 12 }}>
        <div className="panel__title">文章列表（最新 50 条）</div>
        {!articles.length ? (
          <div className="empty-state">暂无文章</div>
        ) : (
          <table className="list-table">
            <thead>
              <tr>
                <th>
                  <input
                    type="checkbox"
                    checked={selected.size === articles.length && articles.length > 0}
                    onChange={toggleSelectAll}
                  />
                </th>
                <th>标题</th>
                <th>分类</th>
                <th>发布时间</th>
                <th>来源</th>
                <th>已向量化</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {articles.map((art) => (
                <tr key={art.id}>
                  <td>
                    <input
                      type="checkbox"
                      checked={selected.has(art.id)}
                      onChange={() => toggleSelect(art.id)}
                    />
                  </td>
                  <td>{art.title}</td>
                  <td>{art.category || "-"}</td>
                  <td>{art.publish_time ? dayjs(art.publish_time).format("YYYY-MM-DD") : "-"}</td>
                  <td>{art.source_name || "-"}</td>
                  <td>{art.embedded ? "是" : "否"}</td>
                  <td>
                    <button className="ghost" onClick={() => toggleExpand(art.id)}>
                      {expanded === art.id ? "收起切片" : "查看切片"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {expanded ? (
          <div className="panel" style={{ marginTop: 12, background: "#f8fafc" }}>
            <div className="panel__title">切片详情</div>
            {!chunksMap[expanded]?.length ? (
              <div className="empty-state">暂无切片数据</div>
            ) : (
              <table className="list-table sub">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>模型</th>
                    <th>内容</th>
                  </tr>
                </thead>
                <tbody>
                  {chunksMap[expanded].map((c) => (
                    <tr key={c.chunk_index}>
                      <td>{c.chunk_index}</td>
                      <td>{c.model_name || "-"}</td>
                      <td style={{ maxWidth: 720, whiteSpace: "pre-wrap" }}>{c.chunk_text}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        ) : null}
      </div>
    </div>
  );
}
