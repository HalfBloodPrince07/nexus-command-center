export interface ResearchReport {
  slug: string;
  topic: string;
  report_title?: string;
  created_at: string;
  source_count: number;
  avg_confidence: number;
  status: "pending" | "running" | "complete" | "failed";
  job_id: string;
  word_count: number;
  tags: string[];
  section_count?: number;
  verified_claims?: number;
  hallucinated_claims?: number;
  needs_verification_count?: number;
}

export interface ResearchSource {
  url: string;
  url_hash: string;
  domain: string;
  title: string;
  scraped_at: string;
  char_count: number;
  quality_score: number;
  extraction_status: "success" | "paywall" | "timeout" | "error" | "http_error";
  error: string | null;
  report_slug?: string;
}

export interface ResearchClaim {
  id: string;
  claim_text: string;
  claim_type: "statistic" | "date" | "attribution" | "causal" | "definitional" | "comparative";
  source_section: string;
  context_sentence: string;
  existing_citation: string | null;
  verifiability: "high" | "medium" | "low";
  verification_status: "verified" | "unverified" | "contradicted" | "hallucinated";
  confidence_score: number;
  supporting_urls: string[];
  corrected_text: string | null;
}

export type PipelineAgentId =
  | "Atlas"
  | "Vector"
  | "Fetch"
  | "OutlineArchitect"
  | "SectionDrafter"
  | "SynthesisDirector"
  | "Verity"
  | "Scribe"
  | "Exporter";

export type PipelineStage =
  | "idle"
  | "planning"
  | "searching"
  | "ranking"
  | "scraping"
  | "outlining"
  | "drafting"
  | "synthesizing"
  | "extracting"
  | "extracted"
  | "checking"
  | "annotating"
  | "saving"
  | "indexing"
  | "exporting"
  | "complete"
  | "failed";

export interface PipelineAgentState {
  id: PipelineAgentId;
  label: string;
  stage: PipelineStage;
  detail: string;
  status: "idle" | "active" | "complete" | "error";
  /** Extra metadata agents can surface (e.g. "42 URLs", "3/6 sections") */
  badge?: string;
}

export interface SectionProgress {
  total: number;
  done: number;
  currentTitle: string;
}

export interface ClaimProgress {
  total: number;
  verified: number;
  hallucinated: number;
  unverified: number;
}

export interface OutputPaths {
  md?: string;
  pdf?: string;
  docx?: string;
}

export interface PipelineLogEntry {
  ts: string;        // HH:MM:SS
  agent: string;
  detail: string;
}

export interface ResearchJob {
  job_id: string;
  topic: string;
  slug: string;
  status: "pending" | "running" | "complete" | "failed";
  pipeline: PipelineAgentState[];
  report?: ResearchReport;
  error?: string;
  logs: PipelineLogEntry[];
  sectionProgress: SectionProgress;
  claimProgress: ClaimProgress;
  outputPaths: OutputPaths;
  outlineSections: number;
}
