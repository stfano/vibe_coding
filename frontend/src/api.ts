export const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export type Envelope<T> = {
  ok: boolean;
  data: T | null;
  error: { code?: string; message?: string; details?: unknown } | null;
  meta: {
    request_id?: string;
    version?: string;
  };
};

export type HealthData = {
  status: string;
  service: string;
  dependencies: Record<string, string>;
};

export type ChatData = {
  session_id: string;
  answer: string;
  safety_notice: string;
  source_status: string;
  citations: Array<{
    title?: string;
    source?: string;
    source_url?: string;
    external_question_id?: string;
    external_answer_id?: string;
    department?: string;
    department_code?: string;
    chunk_index?: number;
  }>;
  safety_flags: string[];
  retrieved_source_ids: number[];
  llm_executed: boolean;
  graph: {
    executed: boolean;
    version?: string;
    path: string[];
    node_summaries?: Array<{
      name: string;
      duration_ms: number;
      summary: string;
    }>;
    retrieved_source_ids?: number[];
    source_status?: string;
    safety_flags?: string[];
    model_name?: string | null;
    prompt_version?: string | null;
    llm_executed?: boolean;
  };
};

export type KnowledgeDocumentSummary = {
  id: number;
  source: string;
  source_display_name: string;
  source_license_status: string;
  source_external_id: string;
  title: string;
  department: string;
  department_code: string;
  status: "needs_review" | "ready" | "disabled";
  source_url: string;
  chunk_count: number;
  updated_at: string;
};

export type KnowledgeDocumentListData = {
  count: number;
  page: number;
  page_size: number;
  results: KnowledgeDocumentSummary[];
};

export type KnowledgeDocumentDetailData = {
  document: KnowledgeDocumentSummary;
  external_qna_record: {
    source_question_id: string;
    source_answer_id: string;
    question_title: string;
    question_body: string;
    answer_body: string;
    answerer_name: string;
    answerer_title: string;
    source_url: string;
    tags: string[];
  } | null;
  chunks: Array<{
    id: number;
    chunk_index: number;
    text_preview: string;
    embedding_model: string;
    embedding_dimensions: number;
    citation_metadata: Record<string, unknown>;
    indexed_at: string | null;
  }>;
};

export type SearchVerificationData = {
  query: string;
  source_status: string;
  safety_flags: string[];
  red_flag_terms?: string[];
  llm_executed: boolean;
  graph_executed: boolean;
  retrieval?: SearchRetrievalMetadata;
  retrieval_metadata?: SearchRetrievalMetadata;
  results: Array<{
    rank: number;
    chunk_id: number;
    document_id: number;
    document_status: string;
    score: number;
    raw_score?: number | null;
    rerank_score?: number | null;
    preview: string;
    citation: {
      title?: string;
      source?: string;
      source_url?: string;
      external_question_id?: string;
      external_answer_id?: string;
      department?: string;
      department_code?: string;
      chunk_index?: number;
    };
  }>;
};

export type SearchRetrievalMetadata = {
  embedding_transport?: string;
  embedding_provider?: string;
  embedding_model?: string;
  embedding_dimensions?: number;
  embedding_fallback_used?: boolean;
  vector_metric?: string;
  rerank_enabled?: boolean;
  rerank_model?: string | null;
};

export type EvaluationRunSummary = {
  id: number;
  dataset: string;
  dataset_version: string;
  status: "running" | "succeeded" | "failed";
  llm_provider: string;
  model_name: string;
  prompt_version: string;
  total_cases: number;
  passed_cases: number;
  failed_cases: number;
  skipped_cases: number;
  error_summary: string;
  created_at: string;
  finished_at: string | null;
};

export type EvaluationRunListData = {
  results: EvaluationRunSummary[];
};

export type EvaluationRunDetailData = {
  run: EvaluationRunSummary;
  results: Array<{
    id: number;
    case_key: string;
    query: string;
    status: "passed" | "failed" | "skipped";
    source_status: string;
    llm_executed: boolean;
    model_name: string;
    prompt_version: string;
    safety_flags: string[];
    citations: Array<{
      title?: string;
      source?: string;
      source_url?: string;
      external_question_id?: string;
      external_answer_id?: string;
      department?: string;
      department_code?: string;
      chunk_index?: number;
    }>;
    retrieved_source_ids: number[];
    graph_path: string[];
    checks: Record<string, boolean>;
    answer_preview: string;
    error_summary: string;
  }>;
};

export async function fetchEnvelope<T>(path: string, init?: RequestInit): Promise<Envelope<T>> {
  const response = await fetch(`${apiBaseUrl}${path}`, init);
  const body = (await response.json()) as Envelope<T>;
  if (!response.ok || !body.ok) {
    throw new Error(body.error?.message ?? `Request failed with ${response.status}`);
  }
  return body;
}
