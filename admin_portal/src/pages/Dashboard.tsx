import dayjs from "dayjs";
import { StatsCard } from "@/components/StatsCard";
import { ArticleTable } from "@/components/ArticleTable";
import { useArticles } from "@/hooks/useArticles";
import { CATEGORY_LABEL_MAP } from "@/constants/categories";
import type { ArticleCategory } from "@/types/api";

function formatTopCategories(stats: Record<ArticleCategory, number>) {
  return Object.entries(stats)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 4)
    .map(([category, count]) => ({
      label: CATEGORY_LABEL_MAP[category as ArticleCategory] ?? category,
      value: count,
    }));
}

export default function DashboardPage() {
  const { items, loading, stats, lastUpdated, refresh } = useArticles({
    pageSize: 50,
    autoRefreshMs: 60000,
  });

  const topCategories = formatTopCategories(stats.categories as Record<ArticleCategory, number>);

  return (
    <div className="page">
      <div className="page-header">
        <h1>运行概览</h1>
        <p className="muted">最新采集与 AI 加工情况总览</p>
      </div>

      <div className="toolbar">
        <div className="toolbar__left">
          {lastUpdated ? (
            <span className="muted small">
              最近同步：{dayjs(lastUpdated).format("YYYY-MM-DD HH:mm:ss")}
            </span>
          ) : null}
        </div>
        <div className="toolbar__right">
          <button className="ghost" onClick={refresh}>
            手动刷新
          </button>
        </div>
      </div>

      <div className="stats-grid">
        <StatsCard
          label="最新文章来源"
          value={items.length ? items[0].source_name : "--"}
          description={items.length ? dayjs(items[0].publish_time).format("MM-DD HH:mm") : ""}
        />
        <StatsCard label="近 50 条采集" value={items.length} description="用于实时抽样监控" />
        <StatsCard label="分类覆盖数" value={topCategories.length || "--"} description="Top 分类计数" />
      </div>

      <section className="panel">
        <div className="panel__header">
          <h3>分类热度</h3>
        </div>
        {!topCategories.length && !loading ? (
          <div className="empty-state">暂无分类统计</div>
        ) : (
          <div className="stats-grid">
            {topCategories.map((item) => (
              <StatsCard key={item.label} label={item.label} value={item.value} description="近一批次数量" />
            ))}
          </div>
        )}
      </section>

      <section className="panel">
        <div className="panel__header">
          <h3>最新文章</h3>
        </div>
        <ArticleTable items={items.slice(0, 10)} loading={loading} emptyText="暂无可用文章" />
      </section>
    </div>
  );
}
