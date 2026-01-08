/**
 * Subcomponents for chat message rendering
 * - DataFrameRenderer: Table display for SQL query results
 * - ChartRenderer: Plotly visualization (mobile-friendly, lazy loaded)
 * - SearchResultsRenderer: Policy document search results
 */
import { useState, lazy, Suspense } from "react";
import type { Data, Layout, Config } from "plotly.js";
import type { DataFrameData, ChartData, SearchResult, SearchResultsData } from "./types";

// Lazy load Plotly (about 3MB)
const Plot = lazy(async () => {
  const mod = await import("react-plotly.js");
  await import("plotly.js/dist/plotly-locale-zh-cn");
  if (typeof window !== "undefined" && (window as any).Plotly?.setPlotConfig) {
    (window as any).Plotly.setPlotConfig({ locale: "zh-CN" });
  }
  return { default: mod.default };
});

// ======================== DataFrameRenderer ========================

interface DataFrameProps {
  data: DataFrameData;
  title?: string;
}

export function DataFrameRenderer({ data, title }: DataFrameProps) {
  const { columns, rows, row_count } = data;

  if (!columns || !rows || rows.length === 0) {
    return <div className="chat-empty">暂无数据</div>;
  }

  return (
    <div className="chat-card chat-dataframe">
      <div className="chat-card__header">
        <h4 className="chat-card__title">{title || "数据表"}</h4>
        <span className="chat-chip">共 {row_count} 条</span>
      </div>
      <div className="chat-dataframe__wrapper">
        <table className="chat-dataframe__table">
          <thead>
            <tr>
              {columns.map((col) => (
                <th key={col}>{col}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={i}>
                {columns.map((col) => (
                  <td key={col}>{formatCellValue(row[col])}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="chat-dataframe__count">
        {rows.length < row_count ? `显示 ${rows.length} / ${row_count} 条记录` : `共${row_count} 条记录`}
      </p>
    </div>
  );
}

function formatCellValue(val: unknown): string {
  if (val === null || val === undefined) return "-";
  if (typeof val === "number") {
    return val.toLocaleString("zh-CN", { maximumFractionDigits: 2 });
  }
  return String(val);
}

// ======================== ChartRenderer (Plotly) ========================

interface ChartProps {
  data: ChartData;
  title?: string;
}

export function ChartRenderer({ data, title }: ChartProps) {
  const { config } = data;
  const [isFullscreen, setIsFullscreen] = useState(false);

  const plotlyData = (config as { data?: Data[] }).data || [];
  const plotlyLayout = (config as { layout?: Partial<Layout> }).layout || {};

  const seriesCount = plotlyData.length;
  const hasRightLegend = seriesCount > 3;

  const mergedLayout: Partial<Layout> = {
    ...plotlyLayout,
    autosize: true,
    title: undefined,
    font: { family: "system-ui, -apple-system, sans-serif", size: 11 },
    margin: {
      l: 50,
      r: hasRightLegend ? 110 : 15,
      t: 10,
      b: hasRightLegend ? 60 : 70,
    },
    xaxis: {
      ...(plotlyLayout.xaxis || {}),
      tickfont: { size: 10 },
      title: { ...(plotlyLayout.xaxis?.title || {}), font: { size: 11 } },
    },
    yaxis: {
      ...(plotlyLayout.yaxis || {}),
      tickfont: { size: 10 },
      title: { ...(plotlyLayout.yaxis?.title || {}), font: { size: 11 } },
    },
    legend: plotlyLayout.legend || {
      font: { size: 10 },
      orientation: "h",
      y: -0.25,
      x: 0.5,
      xanchor: "center",
    },
  };

  const plotlyConfig: Partial<Config> = {
    responsive: true,
    locale: "zh-CN",
    displayModeBar: false,
    scrollZoom: false,
    doubleClick: "reset",
  };

  return (
    <>
      <div className="chat-card chat-chart">
        <div className="chat-card__header">
          <h4 className="chat-card__title">{title || "数据可视化"}</h4>
          <button
            type="button"
            className="chat-chart__fullscreen-btn"
            onClick={() => setIsFullscreen(true)}
            title="全屏查看"
          >
            ⛶
          </button>
        </div>
        <div className="chat-chart__container">
          <Suspense fallback={<div className="chat-chart__loading">图表加载中...</div>}>
            <Plot
              data={plotlyData}
              layout={mergedLayout}
              config={plotlyConfig}
              style={{ width: "100%", height: "100%" }}
              useResizeHandler
            />
          </Suspense>
        </div>
      </div>

      {isFullscreen && (
        <ChartFullscreenModal
          data={plotlyData}
          layout={plotlyLayout}
          title={title || "数据可视化"}
          onClose={() => setIsFullscreen(false)}
        />
      )}
    </>
  );
}

// ======================== ChartFullscreenModal ========================

interface ChartFullscreenModalProps {
  data: Data[];
  layout: Partial<Layout>;
  title: string;
  onClose: () => void;
}

function ChartFullscreenModal({ data, layout, title, onClose }: ChartFullscreenModalProps) {
  const fullscreenLayout: Partial<Layout> = {
    ...layout,
    autosize: true,
    title: undefined,
    font: { family: "system-ui, -apple-system, sans-serif", size: 12 },
    margin: { l: 60, r: 120, t: 20, b: 80 },
    dragmode: "pan",
    legend: {
      orientation: "v",
      x: 1.02,
      y: 1,
      xanchor: "left",
      font: { size: 11 },
    },
    xaxis: {
      ...(layout.xaxis || {}),
      tickfont: { size: 11 },
    },
    yaxis: {
      ...(layout.yaxis || {}),
      tickfont: { size: 11 },
    },
  };

  const fullscreenConfig: Partial<Config> = {
    responsive: true,
    locale: "zh-CN",
    displayModeBar: true,
    scrollZoom: true,
    displaylogo: false,
    modeBarButtonsToRemove: ["lasso2d", "select2d"],
  };

  return (
    <div className="chart-fullscreen-modal" onClick={onClose}>
      <div className="chart-fullscreen-modal__content" onClick={(e) => e.stopPropagation()}>
        <div className="chart-fullscreen-modal__header">
          <h3 className="chart-fullscreen-modal__title">{title}</h3>
          <button
            type="button"
            className="chart-fullscreen-modal__close"
            onClick={onClose}
          >
            ✕
          </button>
        </div>
        <div className="chart-fullscreen-modal__body">
          <Suspense fallback={<div className="chat-chart__loading">图表加载中...</div>}>
            <Plot
              data={data}
              layout={fullscreenLayout}
              config={fullscreenConfig}
              style={{ width: "100%", height: "100%" }}
              useResizeHandler
            />
          </Suspense>
        </div>
      </div>
    </div>
  );
}

// ======================== SearchResultsRenderer ========================

interface SearchResultsProps {
  data: SearchResultsData;
  onViewArticle?: (articleId: string) => void;
}

export function SearchResultsRenderer({ data, onViewArticle }: SearchResultsProps) {
  const { results } = data;
  const [isExpanded, setIsExpanded] = useState(false);

  if (!results || results.length === 0) {
    return <div className="chat-empty">未找到相关文档</div>;
  }

  return (
    <div className="chat-card chat-search-results">
      <button className="chat-search-results__toggle" onClick={() => setIsExpanded(!isExpanded)}>
        <span className="chat-search-results__toggle-icon">{isExpanded ? "▲" : "▼"}</span>
        <span className="chat-search-results__title">相关政策文档 ({results.length})</span>
      </button>
      {isExpanded && (
        <div className="chat-search-results__list">
          {results.map((result, i) => (
            <SearchResultItem key={`${result.article_id}-${i}`} result={result} onViewArticle={onViewArticle} />
          ))}
        </div>
      )}
    </div>
  );
}

function stripHtml(html: string): string {
  if (!html) return "";
  let text = html.replace(/<[^>]*>/g, " ");
  text = text.replace(/\s+/g, " ").trim();
  if (text.length > 150) {
    text = text.slice(0, 150) + "...";
  }
  return text;
}

interface SearchResultItemProps {
  result: SearchResult;
  onViewArticle?: (articleId: string) => void;
}

function SearchResultItem({ result, onViewArticle }: SearchResultItemProps) {
  const { article_id, title, source_name, publish_time, text, score } = result;
  const cleanText = stripHtml(text);
  const scorePercent = Math.round(score * 100);

  const handleClick = () => {
    if (onViewArticle && article_id) {
      onViewArticle(article_id);
    }
  };

  return (
    <div className="chat-search-item">
      <div className="chat-search-item__badge">
        <span className="chat-search-item__score-bar" style={{ width: `${scorePercent}%` }} />
        <span className="chat-search-item__score-text">{scorePercent}%</span>
      </div>
      <button type="button" className="chat-search-item__title" onClick={handleClick}>
        {title}
      </button>
      {cleanText && <p className="chat-search-item__text">{cleanText}</p>}
      <div className="chat-search-item__meta">
        {source_name && <span className="chat-search-item__source">📰 {source_name}</span>}
        {publish_time && (
          <span className="chat-search-item__date">
            📅 {new Date(publish_time).toLocaleDateString("zh-CN")}
          </span>
        )}
      </div>
    </div>
  );
}

// ======================== Component Router ========================

interface ChatComponentRendererProps {
  type: "dataframe" | "chart" | "search_results";
  data: DataFrameData | ChartData | SearchResultsData;
  title?: string;
  onViewArticle?: (articleId: string) => void;
}

export function ChatComponentRenderer({ type, data, title, onViewArticle }: ChatComponentRendererProps) {
  switch (type) {
    case "dataframe":
      return <DataFrameRenderer data={data as DataFrameData} title={title} />;
    case "chart":
      return <ChartRenderer data={data as ChartData} title={title} />;
    case "search_results":
      return <SearchResultsRenderer data={data as SearchResultsData} onViewArticle={onViewArticle} />;
    default:
      return null;
  }
}

export default ChatComponentRenderer;
