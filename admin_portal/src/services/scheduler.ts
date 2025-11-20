import type { Envelope } from "@/types/api";
import type {
  CrawlerMeta,
  CrawlerJobItem,
  CrawlerJobRun,
  PipelineRunResult,
  CeleryHealth,
  ResetResult,
} from "@/types/scheduler";
import { apiRequest, RequestOptions } from "./api";

interface JobsResponse extends Envelope<{ items: CrawlerJobItem[] }> {}
interface RunsResponse extends Envelope<{ items: CrawlerJobRun[] }> {}
interface PipelineResponse extends Envelope<PipelineRunResult> {}
interface CeleryResponse extends Envelope<CeleryHealth> {}
interface ResetResponse extends Envelope<ResetResult> {}
interface QuickPipelineResponse extends Envelope<PipelineRunResult> {}

export async function fetchCrawlerMeta(): Promise<CrawlerMeta[]> {
  const resp = await apiRequest<Envelope<CrawlerMeta[]>>("/v1/crawlers/meta");
  return resp.data;
}

export async function fetchJobs(): Promise<CrawlerJobItem[]> {
  const resp = await apiRequest<JobsResponse>("/v1/crawler-jobs");
  return resp.data.items;
}

export async function createJob(payload: Record<string, unknown>): Promise<CrawlerJobItem> {
  const resp = await apiRequest<Envelope<CrawlerJobItem>>("/v1/crawler-jobs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return resp.data;
}

export async function updateJob(jobId: string, payload: Record<string, unknown>): Promise<CrawlerJobItem> {
  const resp = await apiRequest<Envelope<CrawlerJobItem>>(`/v1/crawler-jobs/${jobId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return resp.data;
}

export async function fetchJobRuns(jobId: string): Promise<CrawlerJobRun[]> {
  const resp = await apiRequest<RunsResponse>(`/v1/crawler-jobs/${jobId}/runs`);
  return resp.data.items;
}

export async function triggerJob(jobId: string, payload: Record<string, unknown> = {}): Promise<CrawlerJobRun> {
  const resp = await apiRequest<Envelope<CrawlerJobRun>>(`/v1/crawler-jobs/${jobId}/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return resp.data;
}

export async function deleteJob(jobId: string): Promise<void> {
  await apiRequest<Envelope<{ deleted: boolean }>>(`/v1/crawler-jobs/${jobId}`, {
    method: "DELETE",
  });
}

export async function runPipeline(): Promise<PipelineRunResult> {
  const resp = await apiRequest<PipelineResponse>("/v1/pipeline/run", { method: "POST" });
  return resp.data;
}

export async function runPipelineQuick(): Promise<PipelineRunResult> {
  const resp = await apiRequest<QuickPipelineResponse>("/v1/pipeline/quick-run", { method: "POST" });
  return resp.data;
}

export async function fetchCeleryHealth(): Promise<CeleryHealth> {
  const resp = await apiRequest<CeleryResponse>("/v1/celery/health");
  return resp.data;
}

export async function resetPipelineData(): Promise<ResetResult> {
  const resp = await apiRequest<ResetResponse>("/v1/pipeline/reset", { method: "POST" });
  return resp.data;
}
