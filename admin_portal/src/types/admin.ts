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

// ==================== Employee Data Types ====================

// Employee record
export interface Employee {
  id: string;
  company_name: string;
  name: string;
  gender?: string;
  department?: string;
  position?: string;
  employee_level?: string;
  hire_date?: string;
  created_at: string;
}

// Employee list response
export interface EmployeeListResponse {
  total: number;
  page: number;
  page_size: number;
  items: Employee[];
}

// Company statistics
export interface CompanyStats {
  name: string;
  count: number;
}

// Employee statistics
export interface EmployeeStats {
  total: number;
  by_company: Record<string, number>;
}

// ==================== Employee Import Types ====================

// Upload result
export interface FileUploadResult {
  file_id: string;
  filename: string;
  size: number;
}

// Preview data
export interface EmployeePreviewData {
  format_type: 'full_roster' | 'independent' | 'unknown';
  company_name?: string;  // Auto-detected company name
  total_rows: number;
  valid_rows: number;
  invalid_rows: number;
  columns?: EmployeeColumn[];
  preview: EmployeePreviewRow[];
}

export interface EmployeeColumn {
  key: string;
  label: string;
}

export interface EmployeePreviewRow {
  row_num: number;
  warnings: string[];
  [key: string]: unknown;  // Dynamic fields
}

// Single sheet import request
export interface SingleImportRequest {
  file_id: string;
  sheet_name?: string;
  company_name?: string;  // Optional, only when cannot auto-detect
}

// Batch import request
export interface BatchImportRequest {
  file_id: string;
  start_sheet_index?: number;
  end_sheet_index?: number;
  skip_validation?: boolean;
}

// Sheet validation result
export interface SheetValidation {
  sheet_name: string;
  is_valid: boolean;
  error?: string;
  company_name: string;
  total_rows: number;
}

// Batch import response
export interface BatchImportResponse {
  task_id: string;
  total_sheets: number;
  valid_sheets: number;
  validation_results: SheetValidation[];
}

// Import task result
export interface ImportTaskResult {
  status: 'ok' | 'error';
  total?: number;
  inserted?: number;
  updated?: number;
  skipped?: number;
  // Batch import additional fields
  total_sheets?: number;
  success_sheets?: number;
  failed_sheets?: number;
  skipped_sheets?: number;
  results?: Record<string, {
    company_name: string;
    total: number;
    inserted: number;
    updated: number;
  }>;
  errors?: Record<string, string>;
  error?: string;
}
