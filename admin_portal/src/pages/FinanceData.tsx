import { Fragment, useEffect, useMemo, useState } from "react";
import dayjs from "dayjs";
import {
  fetchFinanceMeta,
  fetchFinanceRecords,
  fetchFinanceStats,
  fetchFinanceSyncLogs,
  fetchTaskStatus,
  triggerFinanceSync,
} from "@/services/adminOps";
import type {
  FinanceMeta,
  FinanceRecord,
  FinanceStats,
  FinanceSyncLog,
} from "@/types/admin";

const TERMINAL_STATES = ["SUCCESS", "FAILURE", "REVOKED"];

// 指标类型顺序（按业务重要性排列）
const TYPE_ORDER = ["01", "02", "06", "03", "04", "05", "07", "08"];

interface CompanyData {
  company_no: string;
  company_name: string;
  level: string | null;
  metrics: Record<string, FinanceRecord>;
}

function formatAmount(num: number | null | undefined): string {
  if (num === null || num === undefined) return "-";
  return Number(num).toLocaleString("zh-CN", { maximumFractionDigits: 2 });
}

function formatPercent(num: number | null | undefined): string {
  if (num === null || num === undefined) return "-";
  const val = Number(num);
  return `${val >= 0 ? "+" : ""}${val.toFixed(2)}%`;
}

function getPercentColor(val: number | null | undefined): string {
  if (val === null || val === undefined) return "#64748b";
  return val >= 0 ? "#22c55e" : "#ef4444";
}

export default function FinanceDataPage() {
  const [stats, setStats] = useState<FinanceStats | null>(null);
  const [meta, setMeta] = useState<FinanceMeta | null>(null);
  const [records, setRecords] = useState<FinanceRecord[]>([]);
  const [logs, setLogs] = useState<FinanceSyncLog[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [taskId, setTaskId] = useState<string | null>(null);
  const [taskState, setTaskState] = useState<string | null>(null);
  const [syncing, setSyncing] = useState(false);

  // 筛选条件
  const [selectedMonth, setSelectedMonth] = useState<string>("");
  const [selectedCompany, setSelectedCompany] = useState<string>(""); // "" 表示全部

  // Tab 状态
  const [activeTab, setActiveTab] = useState<"data" | "logs">("data");

  // 加载元数据
  useEffect(() => {
    fetchFinanceMeta()
      .then((data) => {
        setMeta(data);
        // 默认选择最新月份
        if (data.months.length > 0 && !selectedMonth) {
          setSelectedMonth(data.months[0]);
        }
      })
      .catch(console.error);
  }, []);

  // 加载数据
  async function loadData() {
    if (!selectedMonth) return;

    setLoading(true);
    setError(null);
    try {
      const [statsResp, recordsResp, logsResp] = await Promise.all([
        fetchFinanceStats(),
        fetchFinanceRecords({
          month: selectedMonth,
          company_no: selectedCompany || undefined,
        }),
        fetchFinanceSyncLogs(20),
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
    if (selectedMonth) {
      loadData();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedMonth, selectedCompany]);

  // 任务轮询
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
      const res = await triggerFinanceSync(selectedMonth || undefined);
      setTaskId(res.task_id);
    } catch (err) {
      setError((err as Error).message || "触发同步失败");
    }
  }

  // 按公司分组数据
  const groupedData = useMemo(() => {
    const groups: Record<string, CompanyData> = {};

    for (const rec of records) {
      const key = rec.company_no;
      if (!groups[key]) {
        groups[key] = {
          company_no: rec.company_no,
          company_name: rec.company_name,
          level: rec.level,
          metrics: {},
        };
      }
      if (rec.type_no) {
        groups[key].metrics[rec.type_no] = rec;
      }
    }

    // 按 level 排序（一级公司在前）
    return Object.values(groups).sort((a, b) => {
      if (a.level === "0" && b.level !== "0") return -1;
      if (a.level !== "0" && b.level === "0") return 1;
      return a.company_name.localeCompare(b.company_name);
    });
  }, [records]);

  // 获取当前使用的指标类型（按顺序）
  const activeTypes = useMemo(() => {
    if (!meta?.types) return [];
    const typesMap = new Map(meta.types.map((t) => [t.type_no, t]));
    return TYPE_ORDER.filter((no) => typesMap.has(no)).map((no) => typesMap.get(no)!);
  }, [meta]);

  const coverageText = useMemo(() => {
    if (!stats?.date_coverage) return "-";
    const { min, max } = stats.date_coverage;
    if (!min && !max) return "-";
    return `${min ?? "?"} ~ ${max ?? "?"}`;
  }, [stats]);

  return (
    <div>
      <div className="page-header">
        <h1>财务数据</h1>
        <p style={{ color: "#475569", margin: 0 }}>按月份查看各公司财务指标，支持同步最新数据</p>
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
          <div className="panel__title">数据覆盖</div>
          <div className="panel__value">{coverageText}</div>
        </div>
        <div className="panel">
          <div className="panel__title">任务状态</div>
          <div
            className="panel__value"
            style={{
              color:
                taskState === "SUCCESS" ? "#22c55e" : taskState === "FAILURE" ? "#ef4444" : undefined,
            }}
          >
            {taskState || "未触发"}
          </div>
        </div>
      </div>

      {/* 筛选工具栏 */}
      <div className="toolbar" style={{ marginTop: 16 }}>
        <div style={{ display: "flex", gap: 16, alignItems: "center", flexWrap: "wrap" }}>
          <label style={{ fontSize: 13, display: "flex", alignItems: "center", gap: 6 }}>
            月份：
            <select
              value={selectedMonth}
              onChange={(e) => setSelectedMonth(e.target.value)}
              style={{ minWidth: 120 }}
            >
              {meta?.months.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </label>
          <label style={{ fontSize: 13, display: "flex", alignItems: "center", gap: 6 }}>
            公司：
            <select
              value={selectedCompany}
              onChange={(e) => setSelectedCompany(e.target.value)}
              style={{ minWidth: 140 }}
            >
              <option value="">全部公司</option>
              {meta?.companies.map((c) => (
                <option key={c.company_no} value={c.company_no}>
                  {c.company_name}
                  {c.level === "0" ? " [集团]" : ""}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button onClick={handleSync} disabled={syncing}>
            {syncing ? "同步中..." : "同步数据"}
          </button>
          <button className="ghost" onClick={loadData} disabled={loading}>
            刷新
          </button>
        </div>
      </div>

      {error && <div className="error-banner">错误：{error}</div>}

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
          财务数据 ({groupedData.length} 家)
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

      {/* 数据内容 */}
      {activeTab === "data" ? (
        <div className="panel" style={{ marginTop: 0, borderTopLeftRadius: 0 }}>
          {loading ? (
            <div className="empty-state">加载中...</div>
          ) : !groupedData.length ? (
            <div className="empty-state">暂无数据，请选择月份</div>
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table className="list-table" style={{ minWidth: 1200 }}>
                <thead>
                  <tr>
                    <th style={{ position: "sticky", left: 0, background: "#f8fafc", zIndex: 1 }}>
                      公司名称
                    </th>
                    {activeTypes.map((t) => (
                      <th key={t.type_no} colSpan={2} style={{ textAlign: "center" }}>
                        {t.type_name}
                      </th>
                    ))}
                  </tr>
                  <tr style={{ fontSize: 12, color: "#64748b" }}>
                    <th style={{ position: "sticky", left: 0, background: "#f8fafc", zIndex: 1 }} />
                    {activeTypes.map((t) => (
                      <Fragment key={`header-${t.type_no}`}>
                        <th style={{ textAlign: "right", fontWeight: 400 }}>本期金额</th>
                        <th style={{ textAlign: "right", fontWeight: 400 }}>同比</th>
                      </Fragment>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {groupedData.map((company) => (
                    <tr
                      key={company.company_no}
                      style={{
                        background: company.level === "0" ? "#f0f9ff" : undefined,
                        fontWeight: company.level === "0" ? 600 : 400,
                      }}
                    >
                      <td
                        style={{
                          position: "sticky",
                          left: 0,
                          background: company.level === "0" ? "#f0f9ff" : "#fff",
                          zIndex: 1,
                        }}
                      >
                        {company.company_name}
                        {company.level === "0" && (
                          <span
                            style={{
                              marginLeft: 6,
                              fontSize: 11,
                              color: "#3b82f6",
                              background: "#dbeafe",
                              padding: "1px 6px",
                              borderRadius: 4,
                            }}
                          >
                            集团
                          </span>
                        )}
                      </td>
                      {activeTypes.map((t) => {
                        const metric = company.metrics[t.type_no];
                        return (
                          <Fragment key={`${company.company_no}-${t.type_no}`}>
                            <td style={{ textAlign: "right", fontFamily: "monospace" }}>
                              {formatAmount(metric?.current_amount)}
                            </td>
                            <td
                              style={{
                                textAlign: "right",
                                fontFamily: "monospace",
                                color: getPercentColor(metric?.add_rate),
                              }}
                            >
                              {formatPercent(metric?.add_rate)}
                            </td>
                          </Fragment>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* 指标说明 */}
          <div
            style={{
              marginTop: 16,
              padding: 12,
              background: "#f8fafc",
              borderRadius: 8,
              fontSize: 12,
              color: "#64748b",
            }}
          >
            <strong>指标说明：</strong>
            {activeTypes.map((t, i) => (
              <span key={t.type_no}>
                {t.type_no}={t.type_name}
                {i < activeTypes.length - 1 ? "、" : ""}
              </span>
            ))}
            <span style={{ marginLeft: 16 }}>金额单位：万元</span>
          </div>
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
                          background:
                            log.status === "success"
                              ? "#dcfce7"
                              : log.status === "failed"
                              ? "#fee2e2"
                              : "#fef3c7",
                          color:
                            log.status === "success"
                              ? "#166534"
                              : log.status === "failed"
                              ? "#991b1b"
                              : "#92400e",
                        }}
                      >
                        {log.status || "-"}
                      </span>
                    </td>
                    <td style={{ textAlign: "right" }}>{log.fetched_count ?? 0}</td>
                    <td style={{ textAlign: "right" }}>{log.inserted_count ?? 0}</td>
                    <td style={{ textAlign: "right" }}>{log.updated_count ?? 0}</td>
                    <td
                      style={{
                        maxWidth: 200,
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}
                    >
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
