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
