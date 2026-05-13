export type Mood = {
  score: number
  emotions: string[]
  confidence: number
}

export type JournalEntry = {
  id: string
  created_at: string
  title?: string
  body_md: string
  mood?: Mood
  tags: string[]
}

export type ChartPayload = {
  id: string
  type: 'line' | 'bar' | 'radar' | 'heatmap' | 'graph' | 'calendar'
  title: string
  series?: ChartSeries[]
  nodes?: GraphNode[]
  edges?: GraphEdge[]
  x_label?: string
  y_label?: string
  meta?: Record<string, unknown>
}

export type ChartSeries = {
  name: string
  data: Record<string, unknown>[]
  color?: string
}

export type GraphNode = {
  id: string
  label: string
  size?: number
  color?: string
  category?: string
  metadata?: Record<string, unknown>
}

export type GraphEdge = {
  source: string
  target: string
  label?: string
  weight?: number
  color?: string
}

export type PatternInsight = {
  title: string
  description: string
  confidence: number
  evidence_count: number
}

export type Decision = {
  id: string
  question: string
  status: 'pending' | 'analyzing' | 'complete' | 'recorded_outcome'
  analysis?: DecisionAnalysis
  chosen_option?: string
  outcome?: string
  created_at: string
  completed_at?: string
}

export type DecisionAnalysis = {
  question: string
  options: DecisionOption[]
  recommendation: string
  confidence: number
  caveats: string
}

export type DecisionOption = {
  name: string
  pros: { text: string; weight: number }[]
  cons: { text: string; weight: number }[]
  score: number
  sources: string[]
}

export type InsightCard = {
  id: string
  category: string
  severity: number
  title: string
  body_md: string
  created_at: string
  read_at?: string
}

export type BriefingData = {
  id: string
  body_md: string
  hero_chart?: string
  mood_summary?: string
  created_at: string
}
