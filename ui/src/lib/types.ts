export type FileStatus = "queued" | "processing" | "processed" | "failed";

export interface IssuerFile {
  id: string;
  name: string;
  folder: string;
  size: number;
  ext: string;
  format: string;
  status: FileStatus;
  doc_type: string;
  doc_label: string;
  category: string;
  confidence: number;
  doc_type_locked: boolean;
  pages?: number | null;
  blocks?: number;
  chars?: number;
  facts?: number;
  ocr_pages?: number;
  needs_ocr_pages?: number;
  warnings?: string[];
  error?: string | null;
  uploaded_at: string;
  processed_at?: string;
}

export interface Block {
  page: number | null;
  loc: string;
  kind: "text" | "ocr" | "needs_ocr" | "table" | "row";
  text: string;
}

export type FactType =
  | "amount" | "percent" | "date" | "count" | "person" | "entity" | "place" | "identifier" | "short_text";

export interface Fact {
  id: string;
  type: FactType;
  label: string;
  value: string;
  unit: string;
  period: string;
  loc: string;
  page: number | null;
  snippet: string;
  file_id: string | null;
  file_name: string;
  doc_type: string | null;
  doc_label: string;
  origin: "rules" | "model" | "user";
  reviewed: boolean;
  edited?: boolean;
  note?: string;
  superseded?: boolean;
  used_in?: string[];
}

export interface Offer {
  company_name?: string;
  board?: "bse_sme" | "nse_emerge";
  registered_office?: string;
  company_secretary?: string;
  issue_type?: "fresh" | "ofs" | "fresh_ofs";
  fresh_issue_shares?: string;
  ofs_shares?: string;
  face_value?: string;
  pre_issue_shares?: string;
  post_issue_shares?: string;
  selling_shareholder?: string;
  lead_manager?: string;
  registrar?: string;
  market_maker?: string;
  statutory_auditor?: string;
  legal_counsel?: string;
  board_resolution_date?: string;
  shareholder_resolution_date?: string;
  [k: string]: string | undefined;
}

export interface ProjectStats {
  files: number;
  processed: number;
  failed: number;
  pending: number;
  facts: number;
  reviewed_facts: number;
  sections: number;
  drafted: number;
  pages: number;
}

export interface Project {
  id: string;
  name: string;
  created_at: string;
  updated_at: string;
  offer: Offer;
  offer_sources?: Record<string, Source | null>;
  stats: ProjectStats;
  files?: IssuerFile[];
}

export type Writer = "inserted" | "code" | "template" | "slm_core" | "slm_ext";

export interface SectionDef {
  key: string;
  title: string;
  part: string;
  writer: Writer;
  needs: string[];
  checklist: string[];
  query: string;
  subheads: string[];
}

export interface Source {
  file_id?: string;
  file_name: string;
  loc: string;
  snippet?: string;
}

export interface SignOff {
  status: "reviewed" | "unreviewed";
  by?: string;
  at?: string;
  note?: string;
}

export interface DraftVersion {
  n: number;
  created_at: string | null;
  engine: string | null;
  edited: boolean;
  model_name?: string | null;
  words: number;
  placeholders: number | null;
  ungrounded: number;
  review: "reviewed" | "unreviewed" | string;
  selected: boolean;
}

export interface SectionRow extends SectionDef {
  version?: number | null;
  versions?: number;
  status: "drafted" | "not_started";
  engine: string | null;
  updated_at: string | null;
  edited: boolean;
  placeholders: number | null;
  ungrounded: number | null;
  checklist_coverage: number | null;
  grounding: number | null;
  weak: number | null;
  narrative_pending: number | null;
  review: SignOff;
}

export interface BriefItem {
  fact_id: string;
  label: string;
  value: string;
  period: string;
  file_name: string;
  loc: string;
}

export interface DraftBlock {
  type: "heading" | "paragraph" | "table" | "note" | "brief";
  text: string;
  rows?: string[][];
  facts: string[];
  caption?: string;
  sources?: Source[];
  items?: BriefItem[];
  sub?: string;
  missing?: boolean;
  flag?: string;
  template?: boolean;
}

export interface Verification {
  grounded: number;
  ungrounded: { figure: string; context: string }[];
  weak: { figure: string; context: string }[];
  grounding: number | null;
  placeholders: number;
  checklist: { item: string; covered: boolean; status: "covered" | "unconfirmed" | "missing" }[];
  checklist_coverage: number | null;
  drhp_stage: string[];
  narrative_pending: number;
  missing_inputs: { item: string; where: string }[];
}

export interface Draft {
  version?: number;
  blocks: DraftBlock[];
  writer: Writer;
  engine: string;
  routed: string[];
  latency_s?: number;
  usage?: Record<string, number>;
  verification: Verification;
  updated_at: string;
  edited: boolean;
  model_name?: string | null;
  review?: SignOff;
  covered?: string[];
  missing?: { item: string; where: string }[];
  narrative_pending?: string[];
}

export interface Job {
  id: string;
  project_id: string;
  kind: "process" | "draft";
  label: string;
  status: "running" | "done" | "done_with_errors" | "failed" | "cancelled";
  done: number;
  total: number;
  message: string;
  started_at: number;
  finished_at: number | null;
  errors: { file?: string; section?: string; error: string }[];
  current?: string | null;
  keys?: string[];
}

export interface Issue {
  id: string;
  severity: "high" | "medium" | "low";
  kind: "missing_input" | "ungrounded" | "weak" | "narrative" | "checklist" | "inconsistency" | "drhp_stage" | "ocr" | "ingest" | "disclosure";
  title: string;
  detail: string;
  section?: string;
  file_id?: string;
  fact_ids?: string[];
}

export interface Review {
  issues: Issue[];
  summary: {
    sections_total: number;
    sections_drafted: number;
    sections_signed_off: number;
    high: number;
    medium: number;
    low: number;
    placeholders: number;
    narrative_pending: number;
    by_kind: Record<string, number>;
  };
}

export interface Settings {
  use_model: boolean;
  model_url: string;
  model_name: string;
  api_key: string;
  api_key_set?: boolean;
  temperature: number;
  max_tokens: number;
  ocr_enabled: boolean;
  ocr_page_limit: number;
  ocr_backend?: string;
  ocr_model_url?: string;
  ocr_model_name?: string;
  ocr_api_key?: string;
}

export interface Health {
  status: string;
  ocr_available: boolean;
  use_model: boolean;
  model: { reachable: boolean | null; models?: string[]; latency_ms?: number | null; serverless?: boolean; workers_running?: number; error?: string | null };
  model_name: string;
  model_url: string;
}

export interface Meta {
  doc_types: { value: string; label: string; category: string }[];
  categories: string[];
  parts: string[];
  writers: Record<Writer, string>;
  sections: SectionDef[];
  formats: string[];
}

export interface SectionData {
  section: SectionDef;
  draft: Draft | null;
  versions: DraftVersion[];
}
