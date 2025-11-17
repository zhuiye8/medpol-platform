export type ArticleCategory =
  | "frontier"
  | "fda_policy"
  | "ema_policy"
  | "pmda_policy"
  | "project_apply"
  | "domestic_policy";

export interface Article {
  id: string;
  title: string;
  summary?: string | null;
  publish_time: string;
  source_name: string;
  category: ArticleCategory;
  tags: string[];
  source_url: string;
}

export interface ArticleListData {
  items: Article[];
  page: number;
  page_size: number;
  total: number;
}

export interface AIResult {
  id: string;
  task_type: string;
  provider: string;
  model: string;
  output: string;
  created_at: string;
}

export interface ArticleDetail {
  id: string;
  title: string;
  content_html: string;
  translated_content?: string | null;
  translated_content_html?: string | null;
  ai_analysis?: Record<string, unknown> | null;
  summary?: string | null;
  publish_time: string;
  source_name: string;
  original_source_language?: string | null;
  ai_results: AIResult[];
}

export interface LogLine {
  idx: number;
  content: string;
}

export interface LogListData {
  lines: LogLine[];
  total: number;
  truncated: boolean;
}

export interface Envelope<T> {
  code: number;
  msg: string;
  data: T;
}

export interface HealthData {
  status: string;
}

export type ArticlesResponse = Envelope<ArticleListData>;
export type LogResponse = Envelope<LogListData>;
