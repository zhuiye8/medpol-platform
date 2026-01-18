/**
 * Subcomponents for chat message rendering
 * - DataFrameRenderer: Table display for SQL query results
 * - ChartRenderer: Plotly visualization (mobile-friendly, lazy loaded)
 * - SearchResultsRenderer: Policy document search results
 */
import { useState, lazy, Suspense } from "react";
import type { Data, Layout, Config } from "plotly.js";
import type { DataFrameData, ChartData, SearchResult, SearchResultsData, AggregateResultData } from "./types";

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

/**
 * 导出 CSV 文件（支持中文，Excel 兼容）
 */
function exportToCsv(columns: string[], rows: Record<string, unknown>[], title?: string) {
  const escapeCsvCell = (val: unknown): string => {
    if (val === null || val === undefined) return "";
    const str = String(val);
    if (str.includes(",") || str.includes("\n") || str.includes('"')) {
      return `"${str.replace(/"/g, '""')}"`;
    }
    return str;
  };

  const headerRow = columns.map(escapeCsvCell).join(",");
  const dataRows = rows.map((row) =>
    columns.map((col) => escapeCsvCell(row[col])).join(",")
  );
  const csvContent = [headerRow, ...dataRows].join("\n");

  const BOM = "\uFEFF";
  const blob = new Blob([BOM + csvContent], { type: "text/csv;charset=utf-8" });

  const timestamp = new Date().toISOString().slice(0, 19).replace(/[:-]/g, "");
  const filename = `${title || "数据导出"}_${timestamp}.csv`;

  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

export function DataFrameRenderer({ data, title }: DataFrameProps) {
  const { columns, rows, row_count, column_labels } = data;

  // 🔧 截断逻辑（防止大数据量卡顿）
  const MAX_DISPLAY_ROWS = 500;
  const isTruncated = rows.length > MAX_DISPLAY_ROWS;
  const displayRows = isTruncated ? rows.slice(0, MAX_DISPLAY_ROWS) : rows;

  if (!columns || !rows || rows.length === 0) {
    return <div className="chat-empty">暂无数据</div>;
  }

  // 获取列的显示名称（优先使用 column_labels 中的中文名）
  const getColumnLabel = (col: string): string => {
    return column_labels?.[col] || col;
  };

  const handleExport = () => {
    // 导出时使用完整数据，不受截断影响
    exportToCsv(columns, rows, title);
  };

  return (
    <div className="chat-card chat-dataframe">
      <div className="chat-card__header">
        <h4 className="chat-card__title">{title || "数据表"}</h4>
        <div className="chat-card__actions">
          <button
            type="button"
            className="chat-dataframe__export-btn"
            onClick={handleExport}
            title="导出 CSV"
          >
            ⬇ 导出
          </button>
          <span className="chat-chip">共 {row_count} 条</span>
        </div>
      </div>

      {/* 🔧 截断警告 */}
      {isTruncated && (
        <div className="chat-warning">
          ⚠ 数据量过大，仅显示前 {MAX_DISPLAY_ROWS} 条。
          建议添加筛选条件（如公司名称、部门）以减少结果数量。
          点击"导出"按钮可下载完整数据。
        </div>
      )}

      <div className="chat-dataframe__wrapper">
        <table className="chat-dataframe__table">
          <thead>
            <tr>
              {columns.map((col) => (
                <th key={col}>{getColumnLabel(col)}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {displayRows.map((row, i) => (
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
        {isTruncated
          ? `显示 ${displayRows.length} / ${rows.length} 条（已截断）`
          : rows.length < row_count
            ? `显示 ${rows.length} / ${row_count} 条记录`
            : `共 ${row_count} 条记录`}
      </p>
    </div>
  );
}

function formatCellValue(val: unknown): string {
  if (val === null || val === undefined) return "-";
  if (typeof val === "boolean") {
    return val ? "是" : "否";
  }
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

// ======================== AggregateResultRenderer ========================

interface AggregateResultProps {
  data: AggregateResultData;
  title?: string;
}

export function AggregateResultRenderer({ data, title }: AggregateResultProps) {
  const formatValue = (value: number | string, format?: string): string => {
    if (typeof value === "number") {
      if (format === "percent") {
        return `${value.toFixed(2)}%`;
      }
      if (format === "currency") {
        return `¥${value.toLocaleString("zh-CN", { minimumFractionDigits: 2 })}`;
      }
      return value.toLocaleString("zh-CN");
    }
    return String(value);
  };

  return (
    <div className="chat-card chat-aggregate">
      <div className="chat-card__header">
        <h4 className="chat-card__title">{title || "统计结果"}</h4>
      </div>
      <div className="chat-aggregate__content">
        <div className="chat-aggregate__value">
          {formatValue(data.value, data.format)}
        </div>
        <div className="chat-aggregate__label">{data.label}</div>
      </div>
    </div>
  );
}

// ======================== Component Router ========================

interface ChatComponentRendererProps {
  type: "dataframe" | "chart" | "search_results" | "aggregate_result";
  data: DataFrameData | ChartData | SearchResultsData | AggregateResultData;
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
    case "aggregate_result":
      return <AggregateResultRenderer data={data as AggregateResultData} title={title} />;
    default:
      return null;
  }
}

export default ChatComponentRenderer;
