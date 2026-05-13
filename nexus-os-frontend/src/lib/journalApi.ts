import { API_URL } from './constants'
import type { JournalEntry, ChartPayload, PatternInsight, Decision, InsightCard, BriefingData } from '@/types/journal'

const json = (r: Response) => r.json()

export async function createJournalEntry(body_md: string, title?: string) {
  const res = await fetch(`${API_URL}/api/journal`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ body_md, title }),
  })
  return json(res)
}

export async function listJournalEntries(limit = 50, offset = 0, start?: string, end?: string) {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) })
  if (start) params.set('start', start)
  if (end) params.set('end', end)
  const res = await fetch(`${API_URL}/api/journal?${params}`)
  return json(res) as Promise<{ entries: JournalEntry[]; count: number }>
}

export async function getJournalEntry(id: string) {
  const res = await fetch(`${API_URL}/api/journal/${id}`)
  return json(res) as Promise<JournalEntry>
}

export async function deleteJournalEntry(id: string) {
  await fetch(`${API_URL}/api/journal/${id}`, { method: 'DELETE' })
}

export async function getMoodTrend(window = 30) {
  const res = await fetch(`${API_URL}/api/journal/mood/trend?window=${window}`)
  return json(res) as Promise<ChartPayload>
}

export async function getMoodCalendar(year: number) {
  const res = await fetch(`${API_URL}/api/journal/mood/calendar?year=${year}`)
  return json(res) as Promise<ChartPayload>
}

export async function getJournalInsights(window = 30) {
  const res = await fetch(`${API_URL}/api/journal/insights?window=${window}`)
  return json(res) as Promise<{ insights: PatternInsight[]; window_days: number }>
}

export async function getRelationshipsGraph() {
  const res = await fetch(`${API_URL}/api/journal/relationships`)
  return json(res) as Promise<ChartPayload>
}

export async function getRelationshipDetail(name: string) {
  const res = await fetch(`${API_URL}/api/journal/relationships/${encodeURIComponent(name)}`)
  return json(res)
}

export async function startDecision(question: string) {
  const res = await fetch(`${API_URL}/api/journal/decisions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
  })
  return json(res)
}

export async function listDecisions() {
  const res = await fetch(`${API_URL}/api/journal/decisions`)
  return json(res) as Promise<{ decisions: Decision[] }>
}

export async function getDecision(id: string) {
  const res = await fetch(`${API_URL}/api/journal/decisions/${id}`)
  return json(res) as Promise<Decision>
}

export async function recordOutcome(id: string, outcome: string) {
  await fetch(`${API_URL}/api/journal/decisions/${id}/outcome`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ outcome }),
  })
}

export async function listInsights(unread = false, limit = 50) {
  const res = await fetch(`${API_URL}/api/insights?unread=${unread}&limit=${limit}`)
  return json(res) as Promise<{ insights: InsightCard[]; count: number }>
}

export async function markInsightRead(id: string) {
  await fetch(`${API_URL}/api/insights/${id}/read`, { method: 'POST' })
}

export async function dismissInsight(id: string) {
  await fetch(`${API_URL}/api/insights/${id}`, { method: 'DELETE' })
}

export async function getTodayBriefing() {
  const res = await fetch(`${API_URL}/api/insights/briefings/today`)
  return json(res) as Promise<{ briefing: BriefingData | null }>
}

export async function listBriefings(limit = 30) {
  const res = await fetch(`${API_URL}/api/insights/briefings?limit=${limit}`)
  return json(res) as Promise<{ briefings: BriefingData[] }>
}

export async function triggerSchedulerJob(job: string) {
  const res = await fetch(`${API_URL}/api/insights/scheduler/trigger/${job}`, { method: 'POST' })
  return json(res)
}
