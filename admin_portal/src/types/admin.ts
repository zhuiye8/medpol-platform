export interface FinanceStats {
  total_records: number;
  latest_sync: string | null;
  date_coverage: {
    min: string | null;
    max: string | null;
  };
}

export interface FinanceRecord {
  id: string;
  keep_date: string;
  company_no: string;
  company_name: string;
  high_company_no: string | null;
  level: string | null;
  type_no: string | null;
  type_name: string | null;
  current_amount: number | null;
  last_year_amount: number | null;
  last_year_total_amount: number | null;
  this_year_total_amount: number | null;
  add_amount: number | null;
  add_rate: number | null;
  year_add_amount: number | null;
  year_add_rate: number | null;
  raw_payload?: Record<string, unknown>;
}

export interface FinanceSyncLog {
  id: string;
  source: string | null;
  mode: string | null;
  status: string | null;
  started_at: string | null;
  finished_at: string | null;
  fetched_count: number | null;
  inserted_count: number | null;
  updated_count: number | null;
  error_message: string | null;
}

export interface FinanceCompany {
  company_no: string;
  company_name: string;
  level: string | null;
}

export interface FinanceType {
  type_no: string;
  type_name: string;
}

export interface FinanceMeta {
  months: string[];
  companies: FinanceCompany[];
  types: FinanceType[];
}

export interface EmbeddingStats {
  total_articles: number;
  embedded_articles: number;
  total_chunks: number;
}

export interface EmbeddingArticle {
  id: string;
  title: string;
  category: string | null;
  publish_time: string | null;
  source_name: string | null;
  embedded: boolean;
  chunk_count: number;
}

export interface EmbeddingChunk {
  chunk_index: number;
  chunk_text: string;
  model_name: string | null;
}

export interface TaskStatus {
  task_id: string;
  state: string;
  result: unknown;
}
