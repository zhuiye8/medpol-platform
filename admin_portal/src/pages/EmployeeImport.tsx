import { useEffect, useState, useCallback } from "react";
import { FileUpload } from "@/components/FileUpload";
import {
  fetchEmployeeCompanies,
  fetchEmployeeStats,
  fetchEmployeeSheets,
  fetchEmployeePreview,
  triggerEmployeeImport,
  fetchEmployeeTaskStatus,
  uploadEmployeeFile,
} from "@/services/adminOps";
import type {
  CompanyOption,
  EmployeePreviewData,
  EmployeePreviewRow,
  EmployeeStats,
} from "@/types/admin";

const TERMINAL_STATES = ["SUCCESS", "FAILURE", "REVOKED"];

type ImportStep = "upload" | "preview" | "importing" | "result";

export default function EmployeeImportPage() {
  // Step state
  const [step, setStep] = useState<ImportStep>("upload");

  // File state
  const [fileId, setFileId] = useState<string | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);

  // Company and sheet selection
  const [companies, setCompanies] = useState<CompanyOption[]>([]);
  const [companyNo, setCompanyNo] = useState<string>("");
  const [sheets, setSheets] = useState<string[]>([]);
  const [selectedSheet, setSelectedSheet] = useState<string>("");

  // Preview data
  const [preview, setPreview] = useState<EmployeePreviewData | null>(null);

  // Task state
  const [taskId, setTaskId] = useState<string | null>(null);
  const [taskState, setTaskState] = useState<string | null>(null);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);

  // Stats and UI state
  const [stats, setStats] = useState<EmployeeStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load companies and stats on mount
  useEffect(() => {
    async function loadInitial() {
      try {
        const [companiesData, statsData] = await Promise.all([
          fetchEmployeeCompanies(),
          fetchEmployeeStats(),
        ]);
        setCompanies(companiesData);
        setStats(statsData);
        if (companiesData.length > 0 && !companyNo) {
          setCompanyNo(companiesData[0].value);
        }
      } catch (err) {
        setError((err as Error).message || "加载失败");
      }
    }
    loadInitial();
  }, []);

  // Handle file upload
  const handleFileUpload = useCallback(async (file: File) => {
    setError(null);
    try {
      const res = await uploadEmployeeFile(file);
      setFileId(res.file_id);
      setFileName(res.filename);

      // Load sheets
      const sheetsData = await fetchEmployeeSheets(res.file_id);
      setSheets(sheetsData);
      if (sheetsData.length > 0) {
        setSelectedSheet(sheetsData[0]);
      }
    } catch (err) {
      setError((err as Error).message || "上传失败");
    }
  }, []);

  // Load preview when file, company, or sheet changes
  const loadPreview = useCallback(async () => {
    if (!fileId || !companyNo) return;
    setLoading(true);
    setError(null);
    try {
      const data = await fetchEmployeePreview(fileId, companyNo, selectedSheet || undefined);
      setPreview(data);
      setStep("preview");
    } catch (err) {
      setError((err as Error).message || "预览失败");
    } finally {
      setLoading(false);
    }
  }, [fileId, companyNo, selectedSheet]);

  // Auto-load preview when file is uploaded and company is selected
  useEffect(() => {
    if (fileId && companyNo && step === "upload") {
      loadPreview();
    }
  }, [fileId, companyNo, step, loadPreview]);

  // Handle import
  const handleImport = useCallback(async () => {
    if (!fileId || !companyNo) return;
    setError(null);
    try {
      const res = await triggerEmployeeImport({
        file_id: fileId,
        company_no: companyNo,
        sheet_name: selectedSheet || undefined,
      });
      setTaskId(res.task_id);
      setStep("importing");
    } catch (err) {
      setError((err as Error).message || "导入失败");
    }
  }, [fileId, companyNo, selectedSheet]);

  // Poll task status
  useEffect(() => {
    if (!taskId) return;
    setTaskState("PENDING");

    const timer = setInterval(async () => {
      try {
        const res = await fetchEmployeeTaskStatus(taskId);
        setTaskState(res.state);
        if (TERMINAL_STATES.includes(res.state)) {
          clearInterval(timer);
          setResult(res.result);
          setStep("result");
          // Refresh stats
          fetchEmployeeStats().then(setStats).catch(() => {});
        }
      } catch (err) {
        setTaskState("FAILED");
        setError((err as Error).message || "任务状态获取失败");
        clearInterval(timer);
        setStep("result");
      }
    }, 2000);

    return () => clearInterval(timer);
  }, [taskId]);

  // Reset to start
  const handleReset = useCallback(() => {
    setStep("upload");
    setFileId(null);
    setFileName(null);
    setSheets([]);
    setSelectedSheet("");
    setPreview(null);
    setTaskId(null);
    setTaskState(null);
    setResult(null);
    setError(null);
  }, []);

  return (
    <div>
      <div className="page-header">
        <h1>员工数据导入</h1>
        <p style={{ color: "#475569", margin: 0 }}>
          从 Excel 文件导入员工信息到数据库
        </p>
      </div>

      {/* Stats cards */}
      <div className="toolbar">
        <div style={{ display: "flex", gap: 12 }}>
          <div className="panel small">
            <div className="panel__title">员工总数</div>
            <div className="panel__value">{stats?.total ?? "--"}</div>
          </div>
          {stats?.by_company && Object.entries(stats.by_company).slice(0, 4).map(([name, count]) => (
            <div key={name} className="panel small">
              <div className="panel__title">{name}</div>
              <div className="panel__value">{count}</div>
            </div>
          ))}
          <div className="panel small">
            <div className="panel__title">任务状态</div>
            <div className="panel__value">{taskState || "未触发"}</div>
          </div>
        </div>
      </div>

      {error && <div className="error-banner">错误：{error}</div>}

      {/* Step 1: Upload */}
      {step === "upload" && (
        <div className="panel" style={{ marginTop: 12 }}>
          <div className="panel__title">Step 1: 上传文件</div>
          <div style={{ marginTop: 16, display: "flex", gap: 16, marginBottom: 16 }}>
            <div style={{ flex: 1 }}>
              <label style={{ display: "block", marginBottom: 6, fontSize: 14, color: "#475569" }}>
                公司编号 *
              </label>
              <select
                value={companyNo}
                onChange={(e) => setCompanyNo(e.target.value)}
                style={{
                  width: "100%",
                  padding: "8px 12px",
                  borderRadius: 6,
                  border: "1px solid #e2e8f0",
                  fontSize: 14,
                }}
              >
                {companies.map((c) => (
                  <option key={c.value} value={c.value}>
                    {c.label} ({c.value})
                  </option>
                ))}
              </select>
            </div>
          </div>
          <FileUpload
            accept=".xlsx,.xls"
            maxSizeMB={10}
            onUpload={handleFileUpload}
            hint="支持 .xlsx, .xls 格式，最大 10MB"
          />
          {fileName && (
            <div style={{ marginTop: 12, color: "#059669", fontSize: 14 }}>
              已上传: {fileName}
            </div>
          )}
        </div>
      )}

      {/* Step 2: Preview */}
      {step === "preview" && preview && (
        <div className="panel" style={{ marginTop: 12 }}>
          <div className="panel__title" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span>Step 2: 预览数据</span>
            <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
              {sheets.length > 1 && (
                <select
                  value={selectedSheet}
                  onChange={(e) => {
                    setSelectedSheet(e.target.value);
                    // Reload preview with new sheet
                    if (fileId && companyNo) {
                      fetchEmployeePreview(fileId, companyNo, e.target.value)
                        .then(setPreview)
                        .catch((err) => setError((err as Error).message));
                    }
                  }}
                  style={{
                    padding: "4px 8px",
                    borderRadius: 4,
                    border: "1px solid #e2e8f0",
                    fontSize: 13,
                  }}
                >
                  {sheets.map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </select>
              )}
              <button className="ghost" onClick={loadPreview} disabled={loading}>
                刷新预览
              </button>
            </div>
          </div>

          {/* Preview stats */}
          <div style={{ display: "flex", gap: 16, margin: "12px 0", fontSize: 14 }}>
            <span>总行数: <strong>{preview.total_rows}</strong></span>
            <span style={{ color: "#059669" }}>有效: <strong>{preview.valid_rows}</strong></span>
            <span style={{ color: "#dc2626" }}>有问题: <strong>{preview.invalid_rows}</strong></span>
          </div>

          {/* Preview table */}
          {preview.preview.length === 0 ? (
            <div className="empty-state">暂无数据</div>
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table className="list-table">
                <thead>
                  <tr>
                    <th style={{ width: 50, position: "sticky", left: 0, background: "#f8fafc", zIndex: 1 }}>行号</th>
                    {preview.columns.map((col) => (
                      <th key={col.key}>{col.label}</th>
                    ))}
                    <th style={{ position: "sticky", right: 0, background: "#f8fafc", zIndex: 1 }}>问题</th>
                  </tr>
                </thead>
                <tbody>
                  {preview.preview.map((row: EmployeePreviewRow) => (
                    <tr key={row.row_num} style={row.warnings.length > 0 ? { background: "#fef2f2" } : {}}>
                      <td style={{ position: "sticky", left: 0, background: row.warnings.length > 0 ? "#fef2f2" : "#fff", zIndex: 1 }}>
                        {row.row_num}
                      </td>
                      {preview.columns.map((col) => (
                        <td key={col.key}>{String(row[col.key] ?? "-")}</td>
                      ))}
                      <td style={{ color: "#dc2626", position: "sticky", right: 0, background: row.warnings.length > 0 ? "#fef2f2" : "#fff", zIndex: 1 }}>
                        {row.warnings.join(", ") || "-"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Actions */}
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 12, marginTop: 16 }}>
            <button className="ghost" onClick={handleReset}>
              取消
            </button>
            <button onClick={handleImport} disabled={preview.valid_rows === 0}>
              开始导入 ({preview.total_rows} 条)
            </button>
          </div>
        </div>
      )}

      {/* Step 3: Importing */}
      {step === "importing" && (
        <div className="panel" style={{ marginTop: 12, textAlign: "center", padding: "48px 24px" }}>
          <div style={{ fontSize: 36, marginBottom: 16 }}>...</div>
          <div style={{ fontSize: 18, color: "#334155", marginBottom: 8 }}>
            正在导入...
          </div>
          <div style={{ fontSize: 14, color: "#64748b" }}>
            任务状态: {taskState || "PENDING"}
          </div>
        </div>
      )}

      {/* Step 4: Result */}
      {step === "result" && (
        <div className="panel" style={{ marginTop: 12 }}>
          <div className="panel__title">导入结果</div>
          {result?.status === "ok" ? (
            <div style={{ padding: "24px 0" }}>
              <div style={{ display: "flex", gap: 24, justifyContent: "center", marginBottom: 24 }}>
                <div style={{ textAlign: "center" }}>
                  <div style={{ fontSize: 32, fontWeight: 600, color: "#0ea5e9" }}>
                    {(result as Record<string, number>).total ?? 0}
                  </div>
                  <div style={{ fontSize: 14, color: "#64748b" }}>总计</div>
                </div>
                <div style={{ textAlign: "center" }}>
                  <div style={{ fontSize: 32, fontWeight: 600, color: "#059669" }}>
                    {(result as Record<string, number>).inserted ?? 0}
                  </div>
                  <div style={{ fontSize: 14, color: "#64748b" }}>新增</div>
                </div>
                <div style={{ textAlign: "center" }}>
                  <div style={{ fontSize: 32, fontWeight: 600, color: "#f59e0b" }}>
                    {(result as Record<string, number>).updated ?? 0}
                  </div>
                  <div style={{ fontSize: 14, color: "#64748b" }}>更新</div>
                </div>
                <div style={{ textAlign: "center" }}>
                  <div style={{ fontSize: 32, fontWeight: 600, color: "#94a3b8" }}>
                    {(result as Record<string, number>).skipped ?? 0}
                  </div>
                  <div style={{ fontSize: 14, color: "#64748b" }}>跳过</div>
                </div>
              </div>
              <div style={{ textAlign: "center" }}>
                <button onClick={handleReset}>继续导入</button>
              </div>
            </div>
          ) : (
            <div style={{ padding: "24px", textAlign: "center" }}>
              <div style={{ color: "#dc2626", fontSize: 16, marginBottom: 12 }}>
                导入失败
              </div>
              <div style={{ color: "#64748b", fontSize: 14, marginBottom: 24 }}>
                {(result as Record<string, string>)?.error || "未知错误"}
              </div>
              <button onClick={handleReset}>重新开始</button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
