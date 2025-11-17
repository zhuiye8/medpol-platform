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
  log_path?: string | null;
  error_message?: string | null;
}

export interface PipelineRunResult {
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
