import { API_URL } from './constants';

export interface MemoryStats {
  episodic: { total: number; available: boolean };
  semantic: { total: number; available: boolean };
  procedural: { total: number; by_type: Record<string, number> };
}

export interface EpisodicItem {
  type: string;
  content: string;
  metadata: Record<string, unknown>;
  timestamp: number;
  session_id?: string;
}

export interface SemanticResult {
  id: string;
  text: string;
  score: number;
  metadata: {
    source: string;
    category: string;
    session_id: string;
    stored_at: string;
  };
}

export interface ProceduralPattern {
  id: string;
  pattern_type: string;
  trigger: string;
  action: string;
  confidence: number;
  use_count: number;
  created_at: string;
}

const EMPTY_STATS: MemoryStats = {
  episodic: { total: 0, available: false },
  semantic: { total: 0, available: false },
  procedural: { total: 0, by_type: {} },
};

export async function fetchMemoryStats(): Promise<MemoryStats> {
  try {
    const res = await fetch(`${API_URL}/api/memory/stats`);
    if (!res.ok) return EMPTY_STATS;
    return (await res.json()) as MemoryStats;
  } catch {
    return EMPTY_STATS;
  }
}

export async function fetchAllEpisodicMemory(
  limit = 50
): Promise<{ items: EpisodicItem[]; count: number }> {
  try {
    const res = await fetch(`${API_URL}/api/memory/episodic?limit=${limit}`);
    if (!res.ok) return { items: [], count: 0 };
    const data = await res.json();
    return { items: data.items ?? [], count: data.count ?? 0 };
  } catch {
    return { items: [], count: 0 };
  }
}

export async function fetchEpisodicMemory(
  sessionId: string,
  limit = 20
): Promise<{ items: EpisodicItem[]; count: number }> {
  try {
    const res = await fetch(
      `${API_URL}/api/memory/episodic/${encodeURIComponent(sessionId)}?limit=${limit}`
    );
    if (!res.ok) return { items: [], count: 0 };
    const data = await res.json();
    return { items: data.items ?? [], count: data.count ?? 0 };
  } catch {
    return { items: [], count: 0 };
  }
}

export async function searchSemanticMemory(
  q: string,
  n = 5
): Promise<{ results: SemanticResult[]; count: number }> {
  try {
    const res = await fetch(
      `${API_URL}/api/memory/semantic/search?q=${encodeURIComponent(q)}&n=${n}`
    );
    if (!res.ok) return { results: [], count: 0 };
    const data = await res.json();
    return { results: data.results ?? [], count: data.count ?? 0 };
  } catch {
    return { results: [], count: 0 };
  }
}

export async function fetchSemanticMemory(
  limit = 50,
  category?: string
): Promise<{ items: SemanticResult[]; count: number }> {
  try {
    const url = new URL(`${API_URL}/api/memory/semantic`);
    url.searchParams.set('limit', String(limit));
    if (category) url.searchParams.set('category', category);
    const res = await fetch(url.toString());
    if (!res.ok) return { items: [], count: 0 };
    const data = await res.json();
    return { items: data.items ?? [], count: data.count ?? 0 };
  } catch {
    return { items: [], count: 0 };
  }
}

export async function fetchProceduralMemory(
  patternType?: string
): Promise<{ patterns: ProceduralPattern[]; count: number }> {
  try {
    const url = patternType
      ? `${API_URL}/api/memory/procedural?pattern_type=${encodeURIComponent(patternType)}`
      : `${API_URL}/api/memory/procedural`;
    const res = await fetch(url);
    if (!res.ok) return { patterns: [], count: 0 };
    const data = await res.json();
    return { patterns: data.patterns ?? [], count: data.count ?? 0 };
  } catch {
    return { patterns: [], count: 0 };
  }
}

export async function clearEpisodicMemory(sessionId: string): Promise<boolean> {
  try {
    const res = await fetch(
      `${API_URL}/api/memory/episodic/${encodeURIComponent(sessionId)}`,
      { method: 'DELETE' }
    );
    if (!res.ok) return false;
    const data = await res.json();
    return Boolean(data.ok);
  } catch {
    return false;
  }
}

// Utility: human-friendly relative timestamp
export function formatRelativeTime(timestamp: number): string {
  // Accept either seconds or milliseconds
  const ms = timestamp > 1e12 ? timestamp : timestamp * 1000;
  const diff = Date.now() - ms;
  if (diff < 0) return 'just now';
  const sec = Math.floor(diff / 1000);
  if (sec < 10) return 'just now';
  if (sec < 60) return `${sec}s ago`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const days = Math.floor(hr / 24);
  if (days < 7) return `${days}d ago`;
  const weeks = Math.floor(days / 7);
  if (weeks < 5) return `${weeks}w ago`;
  const months = Math.floor(days / 30);
  if (months < 12) return `${months}mo ago`;
  const years = Math.floor(days / 365);
  return `${years}y ago`;
}
