import { API_URL } from './constants';

export interface ConversationStats {
  today_messages: number;
  avg_response_ms: number | null;
  weekly_messages: number[];
}

export async function fetchConversationStats(): Promise<ConversationStats> {
  try {
    const res = await fetch(`${API_URL}/api/stats/conversation`);
    if (!res.ok) return { today_messages: 0, avg_response_ms: null, weekly_messages: Array(7).fill(0) };
    return (await res.json()) as ConversationStats;
  } catch {
    return { today_messages: 0, avg_response_ms: null, weekly_messages: Array(7).fill(0) };
  }
}
