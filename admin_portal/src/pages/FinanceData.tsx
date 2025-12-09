import { Fragment, useEffect, useMemo, useState } from "react";
import dayjs from "dayjs";
import {
  fetchFinanceRecords,
  fetchFinanceStats,
  fetchFinanceSyncLogs,
  fetchTaskStatus,
  triggerFinanceSync,
} from "@/services/adminOps";
import type { FinanceRecord, FinanceStats, FinanceSyncLog } from "@/types/admin";

const TERMINAL_STATES = ["SUCCESS", "FAILURE", "REVOKED"];

// 子公司数据结构（从 raw_payload.subCompany 解析）
interface SubCompany {
  id: number;
  companyNo: string;
  companyName: string;
  typeNo: string;
  typeName?: string;
  currentAmt: number | null;
  lastYearAmt: number | null;
  addAmt: number | null;
  addRate: number | null;
  thisYearTotalAmt: number | null;
  lastYearTotalAmt: number | null;
  yearAddAmt: number | null;
  yearAddRate: number | null;
  level: string;
}

function formatAmount(num: number | null | undefined): string {
  if (num === null || num === undefined) return "-";
  return Number(num).toLocaleString("zh-CN", { maximumFractionDigits: 2 });
}

function formatPercent(num: number | null | undefined): string {
  if (num === null || num === undefined) return "-";
  const val = Number(num);
  // API 返回的可能是小数形式（0.23）或百分比形式（23）
  const pct = Math.abs(val) > 1 ? val : val * 100;
  return `${pct >= 0 ? "+" : ""}${pct.toFixed(2)}%`;
}

function getSubCompanies(record: FinanceRecord): SubCompany[] {
  const raw = record.raw_payload;
  if (!raw || !Array.isArray(raw.subCompany)) return [];
  return raw.subCompany as SubCompany[];
}

export default function FinanceDataPage() {
  const [stats, setStats] = useState<FinanceStats | null>(null);
  const [records, setRecords] = useState<FinanceRecord[]>([]);
  const [logs, setLogs] = useState<FinanceSyncLog[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const [taskId, setTaskId] = useState<string | null>(null);
  const [taskState, setTaskState] = useState<string | null>(null);
  const [syncing, setSyncing] = useState(false);

  const [companyFilter, setCompanyFilter] = useState("");
  const [limit, setLimit] = useState(50);

  // Tab 状态：logs | data
  const [activeTab, setActiveTab] = useState<"logs" | "data">("data");

  const coverageText = useMemo(() => {
    if (!stats?.date_coverage) return "-";
    const { min, max } = stats.date_coverage;
    if (!min && !max) return "-";
    return `${min ?? "?"} ~ ${max ?? "?"}`;
  }, [stats]);

  async function loadData() {
    setLoading(true);
    setError(null);
    try {
      const [statsResp, recordsResp, logsResp] = await Promise.all([
        fetchFinanceStats(),
        fetchFinanceRecords({
          company_no: companyFilter || undefined,
          limit,
        }),
        fetchFinanceSyncLogs(50),
      ]);
      setStats(statsResp);
      setRecords(recordsResp);
      setLogs(logsResp);
    } catch (err) {
      setError((err as Error).message || "加载失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!taskId) return;
    setSyncing(true);
    setTaskState("PENDING");
    const timer = setInterval(async () => {
      try {
        const res = await fetchTaskStatus(taskId);
        setTaskState(res.state);
        if (TERMINAL_STATES.includes(res.state)) {
          clearInterval(timer);
          setSyncing(false);
          loadData();
        }
      } catch (err) {
        setTaskState("FAILED");
        setError((err as Error).message || "任务状态获取失败");
        clearInterval(timer);
        setSyncing(false);
      }
    }, 2000);
    return () => clearInterval(timer);
  }, [taskId]);

  async function handleSync() {
    setError(null);
    try {
      const res = await triggerFinanceSync();
      setTaskId(res.task_id);
    } catch (err) {
      setError((err as Error).message || "触发同步失败");
    }
  }

  async function handleFilterApply() {
    await loadData();
  }

  function toggleExpand(id: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }

  return (
    <div>
      <div className="page-header">
        <h1>财务数据</h1>
        <p style={{ color: "#475569", margin: 0 }}>查看/刷新财务流水，同步任务状态可在此监控</p>
      </div>

      {/* 统计卡片 */}
      <div className="stats-grid" style={{ marginTop: 12 }}>
        <div className="panel">
          <div className="panel__title">总记录数</div>
          <div className="panel__value">{stats?.total_records ?? "--"}</div>
        </div>
        <div className="panel">
          <div className="panel__title">最近同步</div>
          <div className="panel__value">
            {stats?.latest_sync ? dayjs(stats.latest_sync).format("MM-DD HH:mm") : "--"}
          </div>
        </div>
        <div className="panel">
          <div className="panel__title">日期覆盖</div>
          <div className="panel__value">{coverageText}</div>
        </div>
        <div className="panel">
          <div className="panel__title">任务状态</div>
          <div className="panel__value" style={{ color: taskState === "SUCCESS" ? "#22c55e" : taskState === "FAILURE" ? "#ef4444" : undefined }}>
            {taskState || "未触发"}
          </div>
        </div>
      </div>

      {/* 工具栏 */}
      <div className="toolbar" style={{ marginTop: 16 }}>
        <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
          <label style={{ fontSize: 13 }}>
            公司编号：
            <input
              value={companyFilter}
              onChange={(e) => setCompanyFilter(e.target.value)}
              placeholder="如 lhjt"
              style={{ marginLeft: 6, width: 100 }}
            />
          </label>
          <label style={{ fontSize: 13 }}>
            条数：
            <input
              type="number"
              min={1}
              max={500}
              value={limit}
              onChange={(e) => setLimit(Number(e.target.value) || 50)}
              style={{ marginLeft: 6, width: 60 }}
            />
          </label>
          <button className="ghost" onClick={handleFilterApply} disabled={loading}>
            查询
          </button>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button onClick={handleSync} disabled={syncing}>
            {syncing ? "同步中..." : "一键同步"}
          </button>
          <button className="ghost" onClick={loadData} disabled={loading}>
            刷新
          </button>
        </div>
      </div>

      {error ? <div className="error-banner">错误：{error}</div> : null}

      {/* Tab 切换 */}
      <div style={{ display: "flex", gap: 0, marginTop: 16, borderBottom: "2px solid #e2e8f0" }}>
        <button
          onClick={() => setActiveTab("data")}
          style={{
            padding: "10px 20px",
            border: "none",
            background: activeTab === "data" ? "#3b82f6" : "transparent",
            color: activeTab === "data" ? "#fff" : "#64748b",
            fontWeight: 600,
            cursor: "pointer",
            borderRadius: "8px 8px 0 0",
          }}
        >
          财务数据 ({records.length})
        </button>
        <button
          onClick={() => setActiveTab("logs")}
          style={{
            padding: "10px 20px",
            border: "none",
            background: activeTab === "logs" ? "#3b82f6" : "transparent",
            color: activeTab === "logs" ? "#fff" : "#64748b",
            fontWeight: 600,
            cursor: "pointer",
            borderRadius: "8px 8px 0 0",
          }}
        >
          同步日志 ({logs.length})
        </button>
      </div>

      {/* Tab 内容 */}
      {activeTab === "data" ? (
        <div className="panel" style={{ marginTop: 0, borderTopLeftRadius: 0 }}>
          {!records.length ? (
            <div className="empty-state">暂无数据</div>
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table className="list-table" style={{ minWidth: 900 }}>
                <thead>
                  <tr>
                    <th style={{ width: 50 }} />
                    <th>记账日期</th>
                    <th>公司名称</th>
                    <th>科目类型</th>
                    <th style={{ textAlign: "right" }}>本期金额</th>
                    <th style={{ textAlign: "right" }}>去年同期</th>
                    <th style={{ textAlign: "right" }}>同比增长</th>
                    <th>子公司</th>
                  </tr>
                </thead>
                <tbody>
                  {records.map((rec) => {
                    const subs = getSubCompanies(rec);
                    const isExpanded = expanded.has(rec.id);
                    return (
                      <Fragment key={rec.id}>
                        {/* 父公司行 */}
                        <tr style={{ background: rec.level === "0" ? "#f8fafc" : undefined }}>
                          <td>
                            {subs.length > 0 && (
                              <button
                                className="ghost"
                                onClick={() => toggleExpand(rec.id)}
                                style={{ padding: "2px 8px", fontSize: 12 }}
                              >
                                {isExpanded ? "▼" : "▶"}
                              </button>
                            )}
                          </td>
                          <td>{rec.keep_date ? dayjs(rec.keep_date).format("YYYY-MM-DD") : "-"}</td>
                          <td>
                            <strong>{rec.company_name || rec.company_no || "-"}</strong>
                            {rec.level === "0" && <span style={{ marginLeft: 6, fontSize: 11, color: "#3b82f6" }}>[一级]</span>}
                          </td>
                          <td>{rec.type_name || `类型${rec.type_no}` || "-"}</td>
                          <td style={{ textAlign: "right", fontFamily: "monospace" }}>{formatAmount(rec.current_amount)}</td>
                          <td style={{ textAlign: "right", fontFamily: "monospace" }}>{formatAmount(rec.last_year_amount)}</td>
                          <td style={{ textAlign: "right", fontFamily: "monospace", color: (rec.add_rate ?? 0) >= 0 ? "#22c55e" : "#ef4444" }}>
                            {formatPercent(rec.add_rate)}
                          </td>
                          <td style={{ color: "#64748b", fontSize: 12 }}>
                            {subs.length > 0 ? `${subs.length} 家` : "-"}
                          </td>
                        </tr>

                        {/* 子公司嵌套表格 */}
                        {isExpanded && subs.length > 0 && (
                          <tr>
                            <td colSpan={8} style={{ padding: 0, background: "#f1f5f9" }}>
                              <div style={{ padding: "12px 16px 12px 50px" }}>
                                <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8, color: "#475569" }}>
                                  子公司明细
                                </div>
                                <table className="list-table" style={{ background: "#fff", margin: 0 }}>
                                  <thead>
                                    <tr>
                                      <th>公司名称</th>
                                      <th>科目类型</th>
                                      <th style={{ textAlign: "right" }}>本期金额</th>
                                      <th style={{ textAlign: "right" }}>去年同期</th>
                                      <th style={{ textAlign: "right" }}>月同比</th>
                                      <th style={{ textAlign: "right" }}>本年累计</th>
                                      <th style={{ textAlign: "right" }}>年同比</th>
                                    </tr>
                                  </thead>
                                  <tbody>
                                    {subs.map((sub, idx) => (
                                      <tr key={sub.id || idx}>
                                        <td>
                                          {sub.companyName || sub.companyNo}
                                          {sub.level === "1" && <span style={{ marginLeft: 6, fontSize: 11, color: "#64748b" }}>[二级]</span>}
                                        </td>
                                        <td>{sub.typeName || `类型${sub.typeNo}` || "-"}</td>
                                        <td style={{ textAlign: "right", fontFamily: "monospace" }}>{formatAmount(sub.currentAmt)}</td>
                                        <td style={{ textAlign: "right", fontFamily: "monospace" }}>{formatAmount(sub.lastYearAmt)}</td>
                                        <td style={{ textAlign: "right", fontFamily: "monospace", color: (sub.addRate ?? 0) >= 0 ? "#22c55e" : "#ef4444" }}>
                                          {formatPercent(sub.addRate)}
                                        </td>
                                        <td style={{ textAlign: "right", fontFamily: "monospace" }}>{formatAmount(sub.thisYearTotalAmt)}</td>
                                        <td style={{ textAlign: "right", fontFamily: "monospace", color: (sub.yearAddRate ?? 0) >= 0 ? "#22c55e" : "#ef4444" }}>
                                          {formatPercent(sub.yearAddRate)}
                                        </td>
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              </div>
                            </td>
                          </tr>
                        )}
                      </Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      ) : (
        <div className="panel" style={{ marginTop: 0, borderTopLeftRadius: 0 }}>
          {!logs.length ? (
            <div className="empty-state">暂无日志</div>
          ) : (
            <table className="list-table">
              <thead>
                <tr>
                  <th>开始时间</th>
                  <th>结束时间</th>
                  <th>来源</th>
                  <th>模式</th>
                  <th>状态</th>
                  <th style={{ textAlign: "right" }}>抓取</th>
                  <th style={{ textAlign: "right" }}>新增</th>
                  <th style={{ textAlign: "right" }}>更新</th>
                  <th>错误信息</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((log) => (
                  <tr key={log.id}>
                    <td>{log.started_at ? dayjs(log.started_at).format("MM-DD HH:mm:ss") : "-"}</td>
                    <td>{log.finished_at ? dayjs(log.finished_at).format("HH:mm:ss") : "-"}</td>
                    <td>{log.source || "-"}</td>
                    <td>{log.mode || "-"}</td>
                    <td>
                      <span
                        style={{
                          padding: "2px 8px",
                          borderRadius: 4,
                          fontSize: 12,
                          background: log.status === "success" ? "#dcfce7" : log.status === "failed" ? "#fee2e2" : "#fef3c7",
                          color: log.status === "success" ? "#166534" : log.status === "failed" ? "#991b1b" : "#92400e",
                        }}
                      >
                        {log.status || "-"}
                      </span>
                    </td>
                    <td style={{ textAlign: "right" }}>{log.fetched_count ?? 0}</td>
                    <td style={{ textAlign: "right" }}>{log.inserted_count ?? 0}</td>
                    <td style={{ textAlign: "right" }}>{log.updated_count ?? 0}</td>
                    <td style={{ maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {log.error_message || "-"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}
