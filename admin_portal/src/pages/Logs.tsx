import { LogViewer } from "@/components/LogViewer";
import { useLogs } from "@/hooks/useLogs";

export default function LogsPage() {
  const { lines, loading, refresh, lastUpdated, truncated, error } = useLogs({
    limit: 400,
    autoRefreshMs: 20000,
  });

  return (
    <div>
      <div className="page-header">
        <h1>运行日志</h1>
        <span style={{ color: "#64748b" }}>聚合脚本日志尾部（数据来自 test.log）</span>
      </div>
      <LogViewer
        lines={lines}
        loading={loading}
        onRefresh={refresh}
        lastUpdated={lastUpdated}
        truncated={truncated}
        error={error}
      />
    </div>
  );
}
