import { API_URL } from "@/lib/constants";

export interface ModelsResponse {
  models: string[];
  active: string;
  error?: string;
}

export interface LMStudioHealth {
  status: "ok" | "error";
  message?: string;
}

export interface LMStudioModel {
  id: string;
  name: string;
  context_length: number;
  quantization?: string;
}

export interface LMStudioModelsResponse {
  models: LMStudioModel[];
  loaded: string[];
}

export interface ModelSettings {
  supervisor_model?: string;
  embedding_model?: string;
  vision_model?: string;
  reranker_model?: string;
}

export async function listModels(): Promise<ModelsResponse> {
  const res = await fetch(`${API_URL}/api/settings/models`);
  if (!res.ok) throw new Error(`Failed to fetch models: ${res.status}`);
  return res.json();
}

export async function setActiveModel(model: string): Promise<{ model: string; status: string }> {
  const res = await fetch(`${API_URL}/api/settings/model`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ model }),
  });
  if (!res.ok) throw new Error(`Failed to set model: ${res.status}`);
  return res.json();
}

export async function testLmStudioConnection(baseUrl: string = "http://localhost:1234/v1"): Promise<LMStudioHealth> {
  try {
    const res = await fetch(`${API_URL}/api/system/lm-studio/health?baseUrl=${encodeURIComponent(baseUrl)}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  } catch (error) {
    return {
      status: "error",
      message: error instanceof Error ? error.message : "Connection failed"
    };
  }
}

export async function getLmStudioModels(baseUrl: string = "http://localhost:1234/v1"): Promise<LMStudioModelsResponse> {
  const res = await fetch(`${API_URL}/api/system/lm-studio/models?baseUrl=${encodeURIComponent(baseUrl)}`);
  if (!res.ok) throw new Error(`Failed to fetch LM Studio models: ${res.status}`);
  return res.json();
}

export async function getModelSettings(): Promise<ModelSettings> {
  const res = await fetch(`${API_URL}/api/settings/models`);
  if (!res.ok) throw new Error(`Failed to fetch model settings: ${res.status}`);
  return res.json();
}

export async function updateModelSettings(settings: ModelSettings): Promise<{ status: string; message?: string }> {
  const res = await fetch(`${API_URL}/api/settings/models`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(settings),
  });
  if (!res.ok) throw new Error(`Failed to update model settings: ${res.status}`);
  return res.json();
}

export async function triggerReindex(): Promise<{ status: string; message?: string }> {
  const res = await fetch(`${API_URL}/api/embeddings/reindex`, {
    method: "POST",
  });
  if (!res.ok) throw new Error(`Failed to trigger reindex: ${res.status}`);
  return res.json();
}
