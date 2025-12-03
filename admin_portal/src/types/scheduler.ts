export interface CrawlerMeta {
  name: string;
  label: string;
  description?: string | null;
  category?: string | null;
}

export interface CrawlerJobPayload {
  meta?: Record<string, unknown>;
  limit?: number | null;
  start_time?: string | null;
  end_time?: string | null;
}

export interface CrawlerJobItem {
  id: string;
  name: string;
  crawler_name: string;
  source_id: string;
  job_type: "scheduled" | "one_off";
  schedule_cron?: string | null;
  interval_minutes?: number | null;
  payload: CrawlerJobPayload;
  retry_config: Record<string, unknown>;
  enabled: boolean;
  next_run_at?: string | null;
  last_run_at?: string | null;
  last_status?: string | null;
}

export interface CrawlerJobRun {
  id: string;
  status: string;
  started_at: string;
  finished_at?: string | null;
  executed_crawler: string;
  result_count: number;
  duration_ms?: number | null;
  retry_attempts?: number | null;
  error_type?: string | null;
  pipeline_run_id?: string | null;
  log_path?: string | null;
  error_message?: string | null;
}

export interface PipelineRunResult {
  run_id?: string | null;
  crawled: number;
  outbox_files: number;
  outbox_processed: number;
  outbox_skipped: number;
  ai_summary_pending: number;
  ai_summary_enqueued: number;
  ai_translation_pending: number;
  ai_translation_enqueued: number;
  ai_analysis_pending: number;
  ai_analysis_enqueued: number;
  details: PipelineRunDetail[];
}

export interface CeleryHealth {
  running: boolean;
  detail: string;
}

export interface ResetResult {
  truncated_tables: string[];
  cleared_dirs: string[];
  dedupe_reset: boolean;
  redis_cleared: boolean;
}

export interface PipelineRunDetail {
  id?: string | null;
  crawler_name: string;
  source_id?: string | null;
  status: string;
  result_count: number;
  duration_ms?: number | null;
  attempt_number?: number | null;
  max_attempts?: number | null;
  error_type?: string | null;
  error_message?: string | null;
  log_path?: string | null;
}

export interface PipelineRunItem {
  id: string;
  run_type: string;
  status: string;
  total_crawlers: number;
  successful_crawlers: number;
  failed_crawlers: number;
  total_articles: number;
  started_at: string;
  finished_at?: string | null;
  error_message?: string | null;
  details: PipelineRunDetail[];
}

export interface PipelineRunList {
  items: PipelineRunItem[];
  total: number;
}
