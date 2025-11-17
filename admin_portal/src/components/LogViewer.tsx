import type { LogLine } from "@/types/api";

interface LogViewerProps {
  lines: LogLine[];
  loading?: boolean;
  onRefresh?: () => void;
  lastUpdated?: Date;
  truncated?: boolean;
  error?: string | null;
}

export function LogViewer({
  lines,
  loading = false,
  onRefresh,
  lastUpdated,
  truncated = false,
  error,
}: LogViewerProps) {
  return (
    <div className="panel">
      <div className="toolbar">
        {lastUpdated ? (
          <span style={{ fontSize: 12, color: "#475569" }}>
            最近更新：{lastUpdated.toLocaleTimeString()}
          </span>
        ) : null}
        <button className="ghost" onClick={onRefresh}>
          手动刷新
        </button>
      </div>
      {error ? <div style={{ color: "#b91c1c" }}>{error}</div> : null}
      <div className="log-viewer">
        {loading && <div style={{ marginBottom: 8 }}>加载中...</div>}
        {truncated ? (
          <div style={{ color: "#fbbf24", marginBottom: 8 }}>仅展示最新的部分日志</div>
        ) : null}
        {!lines.length && !loading ? (
          <div className="log-line__text">暂无日志</div>
        ) : (
          lines.map((line) => (
            <div className="log-line" key={line.idx}>
              <div className="log-line__idx">#{line.idx}</div>
              <div className="log-line__text">{line.content}</div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
