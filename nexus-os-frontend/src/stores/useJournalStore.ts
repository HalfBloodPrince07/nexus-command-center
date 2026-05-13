import { create } from 'zustand'
import type { JournalEntry, ChartPayload, PatternInsight, Decision } from '@/types/journal'
import * as api from '@/lib/journalApi'

type JournalState = {
  entries: JournalEntry[]
  moodTrend: ChartPayload | null
  moodCalendar: ChartPayload | null
  insights: PatternInsight[]
  relationshipsGraph: ChartPayload | null
  decisions: Decision[]
  loading: boolean
  error: string | null

  loadEntries: (limit?: number, offset?: number) => Promise<void>
  createEntry: (bodyMd: string, title?: string) => Promise<void>
  deleteEntry: (id: string) => Promise<void>
  loadMoodTrend: (window?: number) => Promise<void>
  loadMoodCalendar: (year?: number) => Promise<void>
  loadInsights: (window?: number) => Promise<void>
  loadRelationships: () => Promise<void>
  loadDecisions: () => Promise<void>
  startDecision: (question: string) => Promise<void>
  recordOutcome: (id: string, outcome: string) => Promise<void>
  updateChart: (payload: ChartPayload) => void
}

export const useJournalStore = create<JournalState>((set, get) => ({
  entries: [],
  moodTrend: null,
  moodCalendar: null,
  insights: [],
  relationshipsGraph: null,
  decisions: [],
  loading: false,
  error: null,

  loadEntries: async (limit = 50, offset = 0) => {
    set({ loading: true, error: null })
    try {
      const data = await api.listJournalEntries(limit, offset)
      set({ entries: data.entries })
    } catch (e: any) {
      set({ error: e.message })
    } finally {
      set({ loading: false })
    }
  },

  createEntry: async (bodyMd, title) => {
    set({ loading: true, error: null })
    try {
      await api.createJournalEntry(bodyMd, title)
      await get().loadEntries()
    } catch (e: any) {
      set({ error: e.message })
    } finally {
      set({ loading: false })
    }
  },

  deleteEntry: async (id) => {
    try {
      await api.deleteJournalEntry(id)
      set({ entries: get().entries.filter(e => e.id !== id) })
    } catch (e: any) {
      set({ error: e.message })
    }
  },

  loadMoodTrend: async (window = 30) => {
    try {
      const data = await api.getMoodTrend(window)
      set({ moodTrend: data })
    } catch (e: any) {
      set({ error: e.message })
    }
  },

  loadMoodCalendar: async (year) => {
    try {
      const data = await api.getMoodCalendar(year ?? new Date().getFullYear())
      set({ moodCalendar: data })
    } catch (e: any) {
      set({ error: e.message })
    }
  },

  loadInsights: async (window = 30) => {
    try {
      const data = await api.getJournalInsights(window)
      set({ insights: data.insights })
    } catch (e: any) {
      set({ error: e.message })
    }
  },

  loadRelationships: async () => {
    try {
      const data = await api.getRelationshipsGraph()
      set({ relationshipsGraph: data })
    } catch (e: any) {
      set({ error: e.message })
    }
  },

  loadDecisions: async () => {
    try {
      const data = await api.listDecisions()
      set({ decisions: data.decisions })
    } catch (e: any) {
      set({ error: e.message })
    }
  },

  startDecision: async (question) => {
    try {
      await api.startDecision(question)
      await get().loadDecisions()
    } catch (e: any) {
      set({ error: e.message })
    }
  },

  recordOutcome: async (id, outcome) => {
    try {
      await api.recordOutcome(id, outcome)
      await get().loadDecisions()
    } catch (e: any) {
      set({ error: e.message })
    }
  },

  updateChart: (payload) => {
    if (payload.id.startsWith('mood-trend')) set({ moodTrend: payload })
    else if (payload.id.startsWith('mood-calendar')) set({ moodCalendar: payload })
    else if (payload.id === 'relationship-graph') set({ relationshipsGraph: payload })
  },
}))
