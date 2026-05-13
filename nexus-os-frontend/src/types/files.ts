export type FileStatus = "pending" | "processing" | "ready" | "error";
export type PipelineStage = "uploading" | "parsing" | "chunking" | "embedding" | "done" | "error";

export interface FileRecord {
  id: string;
  filename: string;
  original_name: string;
  mime_type: string;
  size_bytes: number;
  status: FileStatus;
  collection: string;
  chunk_count: number;
  uploaded_at: number;
  processed_at: number | null;
  metadata: Record<string, unknown> & { error_message?: string };
}

export interface FileStatusResponse {
  status: FileStatus;
  chunk_count: number;
  error_message?: string | null;
}

export interface UploadProgress {
  fileId: string;
  originalName: string;
  stage: PipelineStage;
  uploadPct: number;
  message: string;
}

export interface SearchResult {
  id: string;
  text: string;
  score: number;
  metadata: {
    file_id: string;
    original_name: string;
    chunk_index: number;
    collection: string;
  };
}

export interface EntityRef {
  name: string;
  type: string;
}

export interface GlobalSearchResult {
  file_id: string;
  original_name: string;
  summary: string;
  score: number;
  entities: EntityRef[];
  source: "vector" | "graph";
}

export interface FolderWatcher {
  id: string;
  path: string;
  collection: string;
  file_count: number;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  timestamp: number;
}
