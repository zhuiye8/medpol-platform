import { useEffect, useState, useCallback } from "react";
import { FileUpload } from "@/components/FileUpload";
import {
  fetchEmployees,
  fetchEmployeeCompanies,
  fetchEmployeeStats,
  fetchEmployeeSheets,
  fetchEmployeePreview,
  importSingleSheet,
  batchImportEmployees,
  fetchEmployeeTaskStatus,
  uploadEmployeeFile,
} from "@/services/adminOps";
import type {
  Employee,
  CompanyStats,
  EmployeePreviewData,
  EmployeeStats,
  BatchImportResponse,
  ImportTaskResult,
  SheetValidation,
} from "@/types/admin";

const TERMINAL_STATES = ["SUCCESS", "FAILURE", "REVOKED"];

type ActiveTab = "data" | "import";
type ImportMode = "single" | "batch";
type ImportStep = 1 | 2 | 3 | 4;  // 1=upload, 2=preview/select, 3=importing, 4=complete

export default function EmployeeImportPage() {
  // Tab state
  const [activeTab, setActiveTab] = useState<ActiveTab>("data");

  // ========== Data Display Tab State ==========
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(50);
  const [loadingData, setLoadingData] = useState(false);
  const [companyFilter, setCompanyFilter] = useState<string>("");
  const [keyword, setKeyword] = useState("");
  const [keywordInput, setKeywordInput] = useState("");
  const [companies, setCompanies] = useState<CompanyStats[]>([]);
  const [stats, setStats] = useState<EmployeeStats | null>(null);

  // ========== Import Tab State ==========
  const [importMode, setImportMode] = useState<ImportMode>("batch");
  const [step, setStep] = useState<ImportStep>(1);
  const [fileId, setFileId] = useState("");
  const [filename, setFilename] = useState("");
  const [sheets, setSheets] = useState<string[]>([]);
  const [selectedSheet, setSelectedSheet] = useState("");
  const [selectedSheets, setSelectedSheets] = useState<string[]>([]);
  const [previewData, setPreviewData] = useState<EmployeePreviewData | null>(null);
  const [manualCompanyName, setManualCompanyName] = useState("");
  const [taskId, setTaskId] = useState("");
  const [taskResult, setTaskResult] = useState<ImportTaskResult | null>(null);
  const [uploading, setUploading] = useState(false);
  const [importing, setImporting] = useState(false);
  const [batchValidations, setBatchValidations] = useState<SheetValidation[]>([]);
  const [error, setError] = useState<string | null>(null);

  // ========== Initialize: Load Data ==========
  useEffect(() => {
    loadEmployeeData();
    loadCompanies();
    loadStats();
  }, [page, companyFilter, keyword]);

  // ========== Data Loading Functions ==========
  const loadEmployeeData = async () => {
    setLoadingData(true);
    setError(null);
    try {
      const data = await fetchEmployees({
        page,
        page_size: pageSize,
        company_name: companyFilter || undefined,
        keyword: keyword || undefined,
      });
      setEmployees(data.items);
      setTotal(data.total);
    } catch (err: any) {
      setError(err.message || "加载员工数据失败");
    } finally {
      setLoadingData(false);
    }
  };

  const loadCompanies = async () => {
    try {
      const data = await fetchEmployeeCompanies();
      setCompanies(data);
    } catch (err: any) {
      console.error("加载公司列表失败:", err);
    }
  };

  const loadStats = async () => {
    try {
      const data = await fetchEmployeeStats();
      setStats(data);
    } catch (err: any) {
      console.error("加载统计失败:", err);
    }
  };

  // ========== Import Flow Functions ==========
  const handleFileSelected = useCallback(async (file: File) => {
    setUploading(true);
    setError(null);
    try {
      const result = await uploadEmployeeFile(file);
      setFileId(result.file_id);
      setFilename(result.filename);

      // Load sheet list
      const sheetNames = await fetchEmployeeSheets(result.file_id);
      setSheets(sheetNames);

      if (importMode === "batch") {
        // Batch mode: skip to sheet selection
        setSelectedSheets(sheetNames.slice(1)); // Default: select all except first (directory sheet)
        setStep(2);
      } else {
        // Single mode: auto-select first sheet and preview
        setSelectedSheet(sheetNames[0]);
        await loadPreview(result.file_id, sheetNames[0]);
        setStep(2);
      }
    } catch (err: any) {
      setError(err.message || "上传失败");
    } finally {
      setUploading(false);
    }
  }, [importMode]);

  const loadPreview = async (fid: string, sheetName: string) => {
    setLoadingData(true);
    setError(null);
    try {
      const data = await fetchEmployeePreview(fid, sheetName);
      setPreviewData(data);

      // If company name cannot be auto-detected, prompt user to input manually
      if (!data.company_name) {
        setError("无法自动识别公司名称，请手动输入");
      }
    } catch (err: any) {
      setError(err.message || "预览失败");
    } finally {
      setLoadingData(false);
    }
  };

  const handleSingleImport = async () => {
    if (!fileId) return;

    const company_name = previewData?.company_name || manualCompanyName;
    if (!company_name) {
      setError("请输入公司名称");
      return;
    }

    setImporting(true);
    setError(null);
    try {
      const result = await importSingleSheet({
        file_id: fileId,
        sheet_name: selectedSheet || undefined,
        company_name,
      });

      setTaskId(result.task_id);
      setStep(3);
      pollTaskStatus(result.task_id);
    } catch (err: any) {
      setError(err.message || "导入失败");
      setImporting(false);
    }
  };

  const handleBatchImport = async () => {
    if (!fileId || selectedSheets.length === 0) {
      setError("请至少选择一个Sheet");
      return;
    }

    setImporting(true);
    setError(null);
    try {
      const firstIndex = sheets.indexOf(selectedSheets[0]);
      const lastIndex = sheets.indexOf(selectedSheets[selectedSheets.length - 1]);

      const result = await batchImportEmployees({
        file_id: fileId,
        start_sheet_index: firstIndex,
        end_sheet_index: lastIndex + 1,
      });

      setTaskId(result.task_id);
      setBatchValidations(result.validation_results);
      setStep(3);
      pollTaskStatus(result.task_id);
    } catch (err: any) {
      setError(err.message || "批量导入失败");
      setImporting(false);
    }
  };

  const pollTaskStatus = (tid: string) => {
    const intervalId = setInterval(async () => {
      try {
        const status = await fetchEmployeeTaskStatus(tid);
        if (TERMINAL_STATES.includes(status.state)) {
          clearInterval(intervalId);
          setTaskResult(status.result);
          setImporting(false);
          setStep(4);

          // Refresh data if successful
          if (status.result.status === "ok") {
            loadEmployeeData();
            loadCompanies();
            loadStats();
          }
        }
      } catch (err) {
        console.error("轮询任务状态失败:", err);
      }
    }, 2000);
  };

  const resetImport = () => {
    setStep(1);
    setFileId("");
    setFilename("");
    setSheets([]);
    setSelectedSheet("");
    setSelectedSheets([]);
    setPreviewData(null);
    setManualCompanyName("");
    setTaskId("");
    setTaskResult(null);
    setBatchValidations([]);
    setError(null);
  };

  const handleSearch = () => {
    setKeyword(keywordInput);
    setPage(1);
  };

  const totalPages = Math.ceil(total / pageSize);

  return (
    <div className="page-container">
      <div className="page-header">
        <h1>员工数据管理</h1>
        <p>管理员工数据和导入Excel文件</p>
      </div>

      {/* Tab Navigation */}
      <div style={{ borderBottom: "1px solid #e2e8f0", marginBottom: 24 }}>
        <div style={{ display: "flex", gap: 32 }}>
          <button
            onClick={() => setActiveTab("data")}
            style={{
              padding: "12px 0",
              background: "none",
              border: "none",
              borderBottom: activeTab === "data" ? "2px solid #0ea5e9" : "2px solid transparent",
              color: activeTab === "data" ? "#0ea5e9" : "#64748b",
              fontSize: 15,
              fontWeight: 500,
              cursor: "pointer",
            }}
          >
            数据展示
          </button>
          <button
            onClick={() => setActiveTab("import")}
            style={{
              padding: "12px 0",
              background: "none",
              border: "none",
              borderBottom: activeTab === "import" ? "2px solid #0ea5e9" : "2px solid transparent",
              color: activeTab === "import" ? "#0ea5e9" : "#64748b",
              fontSize: 15,
              fontWeight: 500,
              cursor: "pointer",
            }}
          >
            导入数据
          </button>
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div style={{
          padding: "12px 16px",
          background: "#fef2f2",
          border: "1px solid #fecaca",
          borderRadius: 6,
          color: "#dc2626",
          marginBottom: 16,
        }}>
          {error}
        </div>
      )}

      {/* ==================== Data Display Tab ==================== */}
      {activeTab === "data" && (
        <div>
          {/* Statistics Cards */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16, marginBottom: 24 }}>
            <div className="panel small">
              <div className="panel__title">总员工数</div>
              <div className="panel__value">{stats?.total || 0}</div>
            </div>
            <div className="panel small">
              <div className="panel__title">公司数量</div>
              <div className="panel__value">{companies.length}</div>
            </div>
            <div className="panel small">
              <div className="panel__title">当前筛选</div>
              <div className="panel__value">{total}</div>
            </div>
            <div className="panel small">
              <div className="panel__title">当前页</div>
              <div className="panel__value">{page} / {totalPages || 1}</div>
            </div>
          </div>

          {/* Filters and Search */}
          <div className="panel" style={{ marginBottom: 16 }}>
            <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
              <select
                value={companyFilter}
                onChange={(e) => {
                  setCompanyFilter(e.target.value);
                  setPage(1);
                }}
                style={{
                  padding: "8px 12px",
                  border: "1px solid #e2e8f0",
                  borderRadius: 6,
                  fontSize: 14,
                  minWidth: 200,
                }}
              >
                <option value="">全部公司</option>
                {companies.map((c) => (
                  <option key={c.name} value={c.name}>
                    {c.name} ({c.count}人)
                  </option>
                ))}
              </select>

              <input
                type="text"
                placeholder="搜索姓名、部门..."
                value={keywordInput}
                onChange={(e) => setKeywordInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleSearch();
                }}
                style={{
                  flex: 1,
                  padding: "8px 12px",
                  border: "1px solid #e2e8f0",
                  borderRadius: 6,
                  fontSize: 14,
                }}
              />

              <button onClick={handleSearch} style={{ padding: "8px 16px" }}>
                搜索
              </button>
            </div>
          </div>

          {/* Employee List */}
          <div className="panel">
            <table className="list-table">
              <thead>
                <tr>
                  <th>姓名</th>
                  <th>公司</th>
                  <th>部门</th>
                  <th>职位</th>
                  <th>入职日期</th>
                </tr>
              </thead>
              <tbody>
                {loadingData ? (
                  <tr>
                    <td colSpan={5} style={{ textAlign: "center", padding: 32, color: "#94a3b8" }}>
                      加载中...
                    </td>
                  </tr>
                ) : employees.length === 0 ? (
                  <tr>
                    <td colSpan={5} style={{ textAlign: "center", padding: 32, color: "#94a3b8" }}>
                      暂无数据
                    </td>
                  </tr>
                ) : (
                  employees.map((emp) => (
                    <tr key={emp.id}>
                      <td>{emp.name}</td>
                      <td style={{ fontSize: 13, color: "#64748b" }}>{emp.company_name}</td>
                      <td>{emp.department || "-"}</td>
                      <td>{emp.position || "-"}</td>
                      <td style={{ fontSize: 13 }}>{emp.hire_date || "-"}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>

            {/* Pagination */}
            <div style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              padding: "12px 16px",
              borderTop: "1px solid #e2e8f0",
            }}>
              <div style={{ fontSize: 14, color: "#64748b" }}>
                共 {total} 条记录，第 {page} / {totalPages || 1} 页
              </div>
              <div style={{ display: "flex", gap: 8 }}>
                <button
                  disabled={page === 1}
                  onClick={() => setPage(page - 1)}
                  className="ghost"
                  style={{ padding: "6px 12px" }}
                >
                  上一页
                </button>
                <button
                  disabled={page >= totalPages}
                  onClick={() => setPage(page + 1)}
                  className="ghost"
                  style={{ padding: "6px 12px" }}
                >
                  下一页
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ==================== Import Data Tab ==================== */}
      {activeTab === "import" && (
        <div className="panel">
          {/* Step 1: Upload */}
          {step === 1 && (
            <div>
              <h3 style={{ marginBottom: 16 }}>上传员工数据文件</h3>

              {/* Import Mode Selection */}
              <div style={{ marginBottom: 24 }}>
                <label style={{ display: "block", fontSize: 14, fontWeight: 500, marginBottom: 12 }}>
                  导入模式
                </label>
                <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                  <label style={{ display: "flex", alignItems: "start", cursor: "pointer" }}>
                    <input
                      type="radio"
                      value="batch"
                      checked={importMode === "batch"}
                      onChange={(e) => setImportMode(e.target.value as ImportMode)}
                      style={{ marginTop: 4, marginRight: 8 }}
                    />
                    <div>
                      <strong>批量导入（推荐）</strong>
                      <p style={{ fontSize: 13, color: "#64748b", margin: "4px 0 0 0" }}>
                        适用于完整花名册，自动从每个Sheet提取公司名称，一次导入多个Sheet
                      </p>
                    </div>
                  </label>
                  <label style={{ display: "flex", alignItems: "start", cursor: "pointer" }}>
                    <input
                      type="radio"
                      value="single"
                      checked={importMode === "single"}
                      onChange={(e) => setImportMode(e.target.value as ImportMode)}
                      style={{ marginTop: 4, marginRight: 8 }}
                    />
                    <div>
                      <strong>单Sheet导入</strong>
                      <p style={{ fontSize: 13, color: "#64748b", margin: "4px 0 0 0" }}>
                        适用于单个Sheet的独立文件
                      </p>
                    </div>
                  </label>
                </div>
              </div>

              {/* File Upload */}
              <FileUpload
                accept=".xlsx,.xls"
                maxSizeMB={10}
                onUpload={handleFileSelected}
                hint="支持 .xlsx 和 .xls 格式，最大 10MB"
                disabled={uploading}
              />
            </div>
          )}

          {/* Step 2: Preview/Select */}
          {step === 2 && importMode === "single" && previewData && (
            <div>
              <h3 style={{ marginBottom: 16 }}>预览数据</h3>

              {/* Company Name Detection */}
              <div style={{ marginBottom: 16, padding: 12, background: previewData.company_name ? "#f0fdf4" : "#fef3c7", borderRadius: 6 }}>
                <div style={{ fontSize: 14, marginBottom: 8 }}>
                  <strong>公司名称:</strong> {previewData.company_name || "无法自动识别"}
                </div>
                {!previewData.company_name && (
                  <input
                    type="text"
                    placeholder="请手动输入公司名称"
                    value={manualCompanyName}
                    onChange={(e) => setManualCompanyName(e.target.value)}
                    style={{
                      width: "100%",
                      padding: "8px 12px",
                      border: "1px solid #e2e8f0",
                      borderRadius: 6,
                      fontSize: 14,
                    }}
                  />
                )}
              </div>

              {/* Preview Stats */}
              <div style={{ display: "flex", gap: 16, marginBottom: 16, fontSize: 14 }}>
                <span>总行数: <strong>{previewData.total_rows}</strong></span>
                <span style={{ color: "#059669" }}>有效: <strong>{previewData.valid_rows}</strong></span>
                <span style={{ color: "#dc2626" }}>有问题: <strong>{previewData.invalid_rows}</strong></span>
              </div>

              {/* Preview Table */}
              {previewData.preview.length > 0 && (
                <div style={{ overflowX: "auto", maxHeight: 400, marginBottom: 16 }}>
                  <table className="list-table">
                    <thead>
                      <tr>
                        <th style={{ width: 50 }}>行号</th>
                        {previewData.columns?.map((col) => (
                          <th key={col.key}>{col.label}</th>
                        ))}
                        <th>问题</th>
                      </tr>
                    </thead>
                    <tbody>
                      {previewData.preview.slice(0, 20).map((row) => (
                        <tr key={row.row_num} style={row.warnings.length > 0 ? { background: "#fef2f2" } : {}}>
                          <td>{row.row_num}</td>
                          {previewData.columns?.map((col) => (
                            <td key={col.key}>{String(row[col.key] ?? "-")}</td>
                          ))}
                          <td style={{ color: "#dc2626", fontSize: 13 }}>
                            {row.warnings.join(", ") || "-"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {/* Actions */}
              <div style={{ display: "flex", justifyContent: "flex-end", gap: 12 }}>
                <button className="ghost" onClick={resetImport}>
                  取消
                </button>
                <button onClick={handleSingleImport} disabled={importing}>
                  开始导入
                </button>
              </div>
            </div>
          )}

          {step === 2 && importMode === "batch" && (
            <div>
              <h3 style={{ marginBottom: 16 }}>选择要导入的Sheet</h3>

              <div style={{ marginBottom: 16 }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 12 }}>
                  <span style={{ fontSize: 14, color: "#64748b" }}>
                    已选择 {selectedSheets.length} 个Sheet
                  </span>
                  <div style={{ display: "flex", gap: 8 }}>
                    <button
                      className="ghost"
                      onClick={() => setSelectedSheets(sheets.slice(1))}
                      style={{ fontSize: 13, padding: "4px 12px" }}
                    >
                      全选
                    </button>
                    <button
                      className="ghost"
                      onClick={() => setSelectedSheets([])}
                      style={{ fontSize: 13, padding: "4px 12px" }}
                    >
                      清空
                    </button>
                  </div>
                </div>

                <div style={{ maxHeight: 400, overflowY: "auto", border: "1px solid #e2e8f0", borderRadius: 6 }}>
                  {sheets.map((sheet, idx) => (
                    <label
                      key={sheet}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        padding: "8px 12px",
                        borderBottom: idx < sheets.length - 1 ? "1px solid #e2e8f0" : "none",
                        cursor: "pointer",
                      }}
                    >
                      <input
                        type="checkbox"
                        checked={selectedSheets.includes(sheet)}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setSelectedSheets([...selectedSheets, sheet]);
                          } else {
                            setSelectedSheets(selectedSheets.filter((s) => s !== sheet));
                          }
                        }}
                        style={{ marginRight: 8 }}
                      />
                      <span style={{ fontSize: 14 }}>{sheet}</span>
                    </label>
                  ))}
                </div>
              </div>

              {/* Actions */}
              <div style={{ display: "flex", justifyContent: "flex-end", gap: 12 }}>
                <button className="ghost" onClick={resetImport}>
                  取消
                </button>
                <button onClick={handleBatchImport} disabled={importing || selectedSheets.length === 0}>
                  开始批量导入
                </button>
              </div>
            </div>
          )}

          {/* Step 3: Importing */}
          {step === 3 && (
            <div style={{ textAlign: "center", padding: "48px 24px" }}>
              <div style={{ fontSize: 36, marginBottom: 16 }}>⏳</div>
              <div style={{ fontSize: 18, color: "#334155", marginBottom: 8 }}>
                {importMode === "batch" ? "批量导入中" : "导入中"}，请稍候...
              </div>
              <div style={{ fontSize: 14, color: "#64748b" }}>
                任务ID: {taskId}
              </div>
            </div>
          )}

          {/* Step 4: Complete */}
          {step === 4 && taskResult && (
            <div>
              <h3 style={{ marginBottom: 16 }}>
                {taskResult.status === "ok" ? "✅ 导入完成" : "❌ 导入失败"}
              </h3>

              {taskResult.status === "ok" ? (
                <div>
                  {importMode === "single" ? (
                    <div style={{ display: "flex", gap: 24, justifyContent: "center", marginBottom: 24 }}>
                      <div style={{ textAlign: "center" }}>
                        <div style={{ fontSize: 32, fontWeight: 600, color: "#0ea5e9" }}>
                          {taskResult.total ?? 0}
                        </div>
                        <div style={{ fontSize: 14, color: "#64748b" }}>总计</div>
                      </div>
                      <div style={{ textAlign: "center" }}>
                        <div style={{ fontSize: 32, fontWeight: 600, color: "#059669" }}>
                          {taskResult.inserted ?? 0}
                        </div>
                        <div style={{ fontSize: 14, color: "#64748b" }}>新增</div>
                      </div>
                      <div style={{ textAlign: "center" }}>
                        <div style={{ fontSize: 32, fontWeight: 600, color: "#f59e0b" }}>
                          {taskResult.updated ?? 0}
                        </div>
                        <div style={{ fontSize: 14, color: "#64748b" }}>更新</div>
                      </div>
                    </div>
                  ) : (
                    <div>
                      <div style={{ display: "flex", gap: 24, justifyContent: "center", marginBottom: 24 }}>
                        <div style={{ textAlign: "center" }}>
                          <div style={{ fontSize: 32, fontWeight: 600, color: "#0ea5e9" }}>
                            {taskResult.total_sheets ?? 0}
                          </div>
                          <div style={{ fontSize: 14, color: "#64748b" }}>Sheet总数</div>
                        </div>
                        <div style={{ textAlign: "center" }}>
                          <div style={{ fontSize: 32, fontWeight: 600, color: "#059669" }}>
                            {taskResult.success_sheets ?? 0}
                          </div>
                          <div style={{ fontSize: 14, color: "#64748b" }}>成功</div>
                        </div>
                        <div style={{ textAlign: "center" }}>
                          <div style={{ fontSize: 32, fontWeight: 600, color: "#dc2626" }}>
                            {taskResult.failed_sheets ?? 0}
                          </div>
                          <div style={{ fontSize: 14, color: "#64748b" }}>失败</div>
                        </div>
                      </div>

                      {/* Detailed Results */}
                      {taskResult.results && Object.keys(taskResult.results).length > 0 && (
                        <div style={{ marginBottom: 24 }}>
                          <h4 style={{ fontSize: 14, marginBottom: 12 }}>详细结果</h4>
                          <div style={{ maxHeight: 300, overflowY: "auto" }}>
                            {Object.entries(taskResult.results).map(([sheet, result]) => (
                              <div key={sheet} style={{ padding: "8px 12px", background: "#f8fafc", marginBottom: 8, borderRadius: 4 }}>
                                <div style={{ fontSize: 14, fontWeight: 500 }}>{result.company_name}</div>
                                <div style={{ fontSize: 13, color: "#64748b" }}>
                                  总计: {result.total}, 新增: {result.inserted}, 更新: {result.updated}
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Errors */}
                      {taskResult.errors && Object.keys(taskResult.errors).length > 0 && (
                        <div style={{ marginBottom: 24 }}>
                          <h4 style={{ fontSize: 14, marginBottom: 12, color: "#dc2626" }}>错误信息</h4>
                          <div style={{ maxHeight: 200, overflowY: "auto" }}>
                            {Object.entries(taskResult.errors).map(([sheet, error]) => (
                              <div key={sheet} style={{ padding: "8px 12px", background: "#fef2f2", marginBottom: 8, borderRadius: 4 }}>
                                <div style={{ fontSize: 13, fontWeight: 500, color: "#dc2626" }}>{sheet}</div>
                                <div style={{ fontSize: 13, color: "#64748b" }}>{error}</div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  <div style={{ textAlign: "center" }}>
                    <button onClick={resetImport}>继续导入</button>
                  </div>
                </div>
              ) : (
                <div style={{ padding: "24px", textAlign: "center" }}>
                  <div style={{ color: "#dc2626", fontSize: 16, marginBottom: 12 }}>
                    {taskResult.error || "未知错误"}
                  </div>
                  <button onClick={resetImport}>重新开始</button>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
