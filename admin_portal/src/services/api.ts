import type {
  ArticlesResponse,
  LogResponse,
  HealthData,
  Envelope,
  ArticleCategory,
  ArticleDetail,
} from "@/types/api";

const DEFAULT_BASE = "http://localhost:8000";
const API_BASE_URL = (import.meta.env.VITE_API_BASE || DEFAULT_BASE).replace(/\/$/, "");

export type RequestOptions = RequestInit & { query?: Record<string, string | number | undefined> };

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const url = new URL(path, API_BASE_URL);
  if (options.query) {
    Object.entries(options.query).forEach(([key, value]) => {
      if (value === undefined || value === null || value === "") {
        return;
      }
      url.searchParams.set(key, String(value));
    });
  }

  const response = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
    },
    ...options,
  });
  if (!response.ok) {
    throw new Error(`请求失败：${response.status}`);
  }
  return (await response.json()) as T;
}

export async function fetchArticles(params?: {
  page?: number;
  pageSize?: number;
  category?: ArticleCategory;
  status?: string;
  q?: string;
}): Promise<ArticlesResponse> {
  return apiRequest<ArticlesResponse>("/v1/articles/", {
    query: {
      page: params?.page ?? 1,
      page_size: params?.pageSize ?? 20,
      category: params?.category,
      status: params?.status,
      q: params?.q,
    },
  });
}

export async function fetchLogs(limit = 200): Promise<LogResponse> {
  return apiRequest<LogResponse>("/v1/admin/logs", {
    query: { limit },
  });
}

export async function fetchHealth(): Promise<Envelope<HealthData>> {
  return apiRequest<Envelope<HealthData>>("/healthz");
}

export async function fetchArticleDetail(articleId: string): Promise<ArticleDetail> {
  const resp = await apiRequest<Envelope<ArticleDetail>>(`/v1/articles/${articleId}`);
  return resp.data;
}
