import { API_URL } from "@/lib/constants";
import type { ResearchReport, ResearchSource } from "@/types/research";

export async function startResearch(topic: string, sessionId: string) {
  const res = await fetch(`${API_URL}/api/research/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ topic, session_id: sessionId }),
  });
  if (!res.ok) throw new Error(`Failed to start research: ${res.statusText}`);
  return res.json() as Promise<{ job_id: string; slug: string; status: string }>;
}

export async function listReports(): Promise<ResearchReport[]> {
  const res = await fetch(`${API_URL}/api/research`);
  if (!res.ok) throw new Error("Failed to fetch reports");
  return res.json();
}

export async function getReport(slug: string): Promise<{ content: string; metadata: ResearchReport }> {
  const res = await fetch(`${API_URL}/api/research/${slug}`);
  if (!res.ok) throw new Error(`Report not found: ${slug}`);
  return res.json();
}

export async function deleteReport(slug: string): Promise<void> {
  const res = await fetch(`${API_URL}/api/research/${slug}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`Failed to delete report: ${slug}`);
}

export async function listAllSources(): Promise<ResearchSource[]> {
  const res = await fetch(`${API_URL}/api/research/sources`);
  if (!res.ok) throw new Error("Failed to fetch sources");
  return res.json();
}

export async function getJobStatus(jobId: string): Promise<{ status: string; error?: string }> {
  const res = await fetch(`${API_URL}/api/research/status/${jobId}`);
  if (!res.ok) throw new Error("Failed to get job status");
  return res.json();
}
