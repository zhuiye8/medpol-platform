/**
 * Subcomponents for chat message rendering
 * - DataFrameRenderer: Table display for SQL query results
 * - ChartRenderer: Plotly visualization (mobile-friendly, lazy loaded)
 * - SearchResultsRenderer: Policy document search results
 */
import { useState, lazy, Suspense } from "react";
import type { Data, Layout, Config } from "plotly.js";
import type { DataFrameData, ChartData, SearchResult, SearchResultsData } from "./types";

// 动态导入 Plotly（约 3MB），仅在需要图表时加载；同时加载中文 locale
const Plot = lazy(async () => {
  const mod = await import("react-plotly.js");
  // 注册 Plotly 中文语言包（modebar/提示语等）
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
  // 转义 CSV 单元格（处理逗号、换行、引号）
  const escapeCsvCell = (val: unknown): string => {
    if (val === null || val === undefined) return "";
    const str = String(val);
    // 如果包含特殊字符，用双引号包裹并转义内部引号
    if (str.includes(",") || str.includes("\n") || str.includes('"')) {
      return `"${str.replace(/"/g, '""')}"`;
    }
    return str;
  };

  // 构建 CSV 内容
  const headerRow = columns.map(escapeCsvCell).join(",");
  const dataRows = rows.map((row) =>
    columns.map((col) => escapeCsvCell(row[col])).join(",")
  );
  const csvContent = [headerRow, ...dataRows].join("\n");

  // 添加 BOM 以确保 Excel 正确识别 UTF-8 编码
  const BOM = "\uFEFF";
  const blob = new Blob([BOM + csvContent], { type: "text/csv;charset=utf-8" });

  // 生成文件名（包含时间戳）
  const timestamp = new Date().toISOString().slice(0, 19).replace(/[:-]/g, "");
  const filename = `${title || "数据导出"}_${timestamp}.csv`;

  // 下载文件
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

  // 🎯 折叠状态管理（默认折叠）
  const [isExpanded, setIsExpanded] = useState(false);

  if (!columns || !rows || rows.length === 0) {
    return <div className="chat-empty">暂无数据</div>;
  }

  // 获取列的显示名称（优先使用 column_labels 中的中文名）
  const getColumnLabel = (col: string): string => {
    return column_labels?.[col] || col;
  };

  const handleExport = () => {
    exportToCsv(columns, rows, title);
  };

  return (
    <div className="chat-card chat-dataframe">
      {/* 🎯 折叠/展开按钮（整个标题区域可点击） */}
      <button
        className="chat-dataframe__toggle"
        onClick={() => setIsExpanded(!isExpanded)}
        type="button"
      >
        <span className="chat-dataframe__toggle-icon">
          {isExpanded ? "▲" : "▼"}
        </span>
        <span className="chat-dataframe__toggle-title">
          {title || "数据表"} ({row_count} 条记录)
        </span>
        <div className="chat-dataframe__actions">
          {/* 导出按钮始终可见（即使折叠状态） */}
          <button
            onClick={(e) => {
              e.stopPropagation(); // 阻止冒泡，避免触发展开
              handleExport();
            }}
            className="chat-dataframe__export-btn"
            title="导出 CSV"
            type="button"
          >
            ⬇ 导出
          </button>
        </div>
      </button>

      {/* 🎯 条件渲染：只有展开时才显示表格 */}
      {isExpanded && (
        <>
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
        </>
      )}

      {/* 🎯 折叠状态下的数据摘要 */}
      {!isExpanded && (
        <p className="chat-dataframe__summary">
          包含 {columns.length} 列数据 · 点击查看详情
        </p>
      )}
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

  // Plotly config comes from backend with { data, layout } structure
  const plotlyData = (config as { data?: Data[] }).data || [];
  const plotlyLayout = (config as { layout?: Partial<Layout> }).layout || {};

  // 检测系列数量，用于智能布局
  const seriesCount = plotlyData.length;
  const hasRightLegend = seriesCount > 3;

  // Merge custom layout with defaults for mobile-friendly display
  // 保留后端的图例配置，只在后端没提供时使用默认值
  const mergedLayout: Partial<Layout> = {
    ...plotlyLayout,
    autosize: true,
    title: undefined,
    font: { family: "system-ui, -apple-system, sans-serif", size: 11 },
    // 根据图例方向动态调整边距
    margin: {
      l: 50,
      r: hasRightLegend ? 110 : 15,
      t: 10,
      b: hasRightLegend ? 60 : 70,
    },
    // X轴优化
    xaxis: {
      ...(plotlyLayout.xaxis || {}),
      tickfont: { size: 10 },
      title: { ...(plotlyLayout.xaxis?.title || {}), font: { size: 11 } },
    },
    // Y轴优化
    yaxis: {
      ...(plotlyLayout.yaxis || {}),
      tickfont: { size: 10 },
      title: { ...(plotlyLayout.yaxis?.title || {}), font: { size: 11 } },
    },
    // 保留后端图例配置（后端已根据系列数量智能配置）
    legend: plotlyLayout.legend || {
      font: { size: 10 },
      orientation: "h",
      y: -0.25,
      x: 0.5,
      xanchor: "center",
    },
  };

  // Plotly config for interactivity
  const plotlyConfig: Partial<Config> = {
    responsive: true,
    locale: "zh-CN",
    displayModeBar: false,
    scrollZoom: false,
    // 双击重置视图，可关闭 hover 浮窗
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

      {/* 全屏模态框 */}
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
  // 全屏模式下的布局优化
  const fullscreenLayout: Partial<Layout> = {
    ...layout,
    autosize: true,
    title: undefined,
    font: { family: "system-ui, -apple-system, sans-serif", size: 12 },
    margin: { l: 60, r: 120, t: 20, b: 80 },
    // 默认使用 pan 模式（dragmode 是 layout 属性，不是 config 属性）
    dragmode: "pan",
    // 全屏模式强制使用竖向图例
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
    // 移除 Plotly logo
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

// 清理HTML标签，提取纯文本
function stripHtml(html: string): string {
  if (!html) return "";
  // 移除HTML标签
  let text = html.replace(/<[^>]*>/g, " ");
  // 清理多余空白
  text = text.replace(/\s+/g, " ").trim();
  // 截断过长内容
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
