import { apiRequest } from "./api";
import type {
  EmbeddingArticle,
  EmbeddingChunk,
  EmbeddingStats,
  FinanceMeta,
  FinanceRecord,
  FinanceStats,
  FinanceSyncLog,
  TaskStatus,
} from "@/types/admin";

type AdminResp<T> = { code: number; message?: string; msg?: string; data: T };

function unwrap<T>(resp: AdminResp<T>): T {
  if (resp.code !== 0) {
    throw new Error(resp.message || resp.msg || "请求失败");
  }
  return resp.data;
}

export async function fetchFinanceStats(): Promise<FinanceStats> {
  const resp = await apiRequest<AdminResp<FinanceStats>>("/v1/admin/finance/stats");
  return unwrap(resp);
}

export async function fetchFinanceMeta(): Promise<FinanceMeta> {
  const resp = await apiRequest<AdminResp<FinanceMeta>>("/v1/admin/finance/meta");
  return unwrap(resp);
}

export async function fetchFinanceRecords(params?: {
  company_no?: string;
  month?: string;
  type_no?: string;
  start_date?: string;
  end_date?: string;
  limit?: number;
}): Promise<FinanceRecord[]> {
  const resp = await apiRequest<AdminResp<FinanceRecord[]>>("/v1/admin/finance/records", {
    query: {
      company_no: params?.company_no,
      month: params?.month,
      type_no: params?.type_no,
      start_date: params?.start_date,
      end_date: params?.end_date,
      limit: params?.limit ?? 500,
    },
  });
  return unwrap(resp);
}

export async function fetchFinanceSyncLogs(limit = 50): Promise<FinanceSyncLog[]> {
  const resp = await apiRequest<AdminResp<FinanceSyncLog[]>>("/v1/admin/finance/sync-logs", {
    query: { limit },
  });
  return unwrap(resp);
}

export async function triggerFinanceSync(month?: string): Promise<{ task_id: string }> {
  const resp = await apiRequest<AdminResp<{ task_id: string }>>("/v1/admin/finance/sync", {
    method: "POST",
    query: month ? { month } : undefined,
  });
  return unwrap(resp);
}

export async function fetchEmbeddingStats(): Promise<EmbeddingStats> {
  const resp = await apiRequest<AdminResp<EmbeddingStats>>("/v1/admin/embeddings/stats");
  return unwrap(resp);
}

export interface EmbeddingArticlesResponse {
  items: EmbeddingArticle[];
  total: number;
}

export async function fetchEmbeddingArticles(
  limit = 50,
  offset = 0
): Promise<EmbeddingArticlesResponse> {
  const resp = await apiRequest<AdminResp<EmbeddingArticlesResponse>>(
    "/v1/admin/embeddings/articles",
    {
      query: { limit, offset },
    }
  );
  return unwrap(resp);
}

export async function fetchEmbeddingArticleDetail(articleId: string): Promise<EmbeddingChunk[]> {
  const resp = await apiRequest<AdminResp<EmbeddingChunk[]>>(`/v1/admin/embeddings/articles/${articleId}`);
  return unwrap(resp);
}

export async function triggerEmbeddingIndex(payload: {
  article_ids?: string[];
  all?: boolean;
  force?: boolean;
}): Promise<{ task_id: string }> {
  const body: Record<string, unknown> = {};
  if (payload.article_ids?.length) {
    body.article_ids = payload.article_ids;
  }
  if (payload.all !== undefined) {
    body.all = payload.all;
  }
  if (payload.force !== undefined) {
    body.force = payload.force;
  }
  const resp = await apiRequest<AdminResp<{ task_id: string }>>("/v1/admin/embeddings/index", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return unwrap(resp);
}

export async function fetchTaskStatus(taskId: string): Promise<TaskStatus> {
  const resp = await apiRequest<AdminResp<TaskStatus>>(`/v1/admin/tasks/${taskId}`);
  return unwrap(resp);
}

// ==================== Employee Data Query APIs ====================

import type {
  BatchImportRequest,
  BatchImportResponse,
  CompanyStats,
  Employee,
  EmployeeListResponse,
  EmployeePreviewData,
  EmployeeStats,
  FileUploadResult,
  ImportTaskResult,
  SingleImportRequest,
} from "@/types/admin";
import { getToken } from "./auth";

const DEFAULT_BASE = "http://localhost:8000";
const API_BASE_URL = (import.meta.env.VITE_API_BASE || DEFAULT_BASE).replace(/\/$/, "");

/**
 * Get employee list (paginated).
 */
export async function fetchEmployees(params: {
  page?: number;
  page_size?: number;
  company_name?: string;
  keyword?: string;
}): Promise<EmployeeListResponse> {
  const resp = await apiRequest<AdminResp<EmployeeListResponse>>("/v1/admin/employees", {
    query: {
      page: params.page,
      page_size: params.page_size,
      company_name: params.company_name,
      keyword: params.keyword,
    },
  });
  return unwrap(resp);
}

/**
 * Get company statistics (extracted from imported employee data).
 */
export async function fetchEmployeeCompanies(): Promise<CompanyStats[]> {
  const resp = await apiRequest<AdminResp<CompanyStats[]>>("/v1/admin/employees/companies");
  return unwrap(resp);
}

/**
 * Get employee statistics.
 */
export async function fetchEmployeeStats(): Promise<EmployeeStats> {
  const resp = await apiRequest<AdminResp<EmployeeStats>>("/v1/admin/employees/stats");
  return unwrap(resp);
}

// ==================== Employee Import APIs ====================

/**
 * Upload Excel file for import.
 */
export async function uploadEmployeeFile(file: File): Promise<FileUploadResult> {
  const formData = new FormData();
  formData.append("file", file);

  const token = getToken();
  const headers: Record<string, string> = {};
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE_URL}/v1/admin/employees/upload`, {
    method: "POST",
    headers,
    body: formData,
  });

  if (!response.ok) {
    throw new Error(`上传失败: ${response.status}`);
  }

  const json = await response.json();
  return unwrap(json);
}

/**
 * Get sheet list from uploaded file.
 */
export async function fetchEmployeeSheets(fileId: string): Promise<string[]> {
  const resp = await apiRequest<AdminResp<string[]>>(
    `/v1/admin/employees/preview/${fileId}/sheets`
  );
  return unwrap(resp);
}

/**
 * Preview employee data from uploaded file.
 * Auto-detects company name, no longer requires company_no parameter.
 */
export async function fetchEmployeePreview(
  fileId: string,
  sheetName?: string,
  limit = 50
): Promise<EmployeePreviewData> {
  const resp = await apiRequest<AdminResp<EmployeePreviewData>>(
    `/v1/admin/employees/preview/${fileId}`,
    {
      query: {
        sheet_name: sheetName,
        limit,
      },
    }
  );
  return unwrap(resp);
}

/**
 * Import single sheet of employee data.
 */
export async function importSingleSheet(
  request: SingleImportRequest
): Promise<{ task_id: string; company_name: string }> {
  const resp = await apiRequest<AdminResp<{ task_id: string; company_name: string }>>(
    "/v1/admin/employees/import",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    }
  );
  return unwrap(resp);
}

/**
 * Batch import multiple sheets (full roster mode).
 */
export async function batchImportEmployees(
  request: BatchImportRequest
): Promise<BatchImportResponse> {
  const resp = await apiRequest<AdminResp<BatchImportResponse>>(
    "/v1/admin/employees/batch-import",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    }
  );
  return unwrap(resp);
}

/**
 * Get employee import task status.
 */
export async function fetchEmployeeTaskStatus(
  taskId: string
): Promise<{ task_id: string; state: string; result: ImportTaskResult }> {
  const resp = await apiRequest<AdminResp<{ task_id: string; state: string; result: ImportTaskResult }>>(
    `/v1/admin/employees/tasks/${taskId}`
  );
  return unwrap(resp);
}
