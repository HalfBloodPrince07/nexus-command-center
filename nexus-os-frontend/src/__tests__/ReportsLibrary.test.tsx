/**
 * Tests for ReportsLibrary component.
 *
 * listReports is mocked via vi.mock so no HTTP requests are made.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import type { ResearchReport } from '@/types/research'

// ---------------------------------------------------------------------------
// Mock researchApi before importing component
// ---------------------------------------------------------------------------
vi.mock('@/lib/researchApi', () => ({
  listReports: vi.fn(),
  getReport: vi.fn(),
  deleteReport: vi.fn(),
}))

import { listReports } from '@/lib/researchApi'
import ReportsLibrary from '@/components/research/ReportsLibrary'
import { useResearchStore } from '@/stores/useResearchStore'

// ---------------------------------------------------------------------------
// Reset store and mocks before each test
// ---------------------------------------------------------------------------
beforeEach(() => {
  useResearchStore.setState({
    activeJob: null,
    reports: [],
    sources: [],
    activeSubTab: 'new',
    viewingSlug: null,
    viewingReport: null,
    isLoading: false,
  })
  vi.clearAllMocks()
})

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------
const makeReport = (overrides: Partial<ResearchReport> = {}): ResearchReport => ({
  slug: 'artificial-intelligence',
  topic: 'Artificial Intelligence',
  created_at: '2025-01-01T00:00:00Z',
  source_count: 5,
  avg_confidence: 0.8,
  status: 'complete',
  job_id: 'job-1',
  word_count: 1200,
  tags: ['AI'],
  ...overrides,
})

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('ReportsLibrary', () => {
  it('calls listReports on mount', async () => {
    vi.mocked(listReports).mockResolvedValue([])
    render(<ReportsLibrary />)
    await waitFor(() => {
      expect(listReports).toHaveBeenCalledOnce()
    })
  })

  it('shows empty state when no reports are returned', async () => {
    vi.mocked(listReports).mockResolvedValue([])
    render(<ReportsLibrary />)
    await waitFor(() => {
      expect(screen.getByText('No reports yet')).toBeInTheDocument()
    })
  })

  it('renders a report card with topic name', async () => {
    vi.mocked(listReports).mockResolvedValue([makeReport()])
    render(<ReportsLibrary />)
    await waitFor(() => {
      expect(screen.getByText('Artificial Intelligence')).toBeInTheDocument()
    })
  })

  it('renders the confidence percentage badge', async () => {
    vi.mocked(listReports).mockResolvedValue([makeReport({ avg_confidence: 0.8 })])
    render(<ReportsLibrary />)
    await waitFor(() => {
      // Math.round(0.8 * 100) = 80 → "80% confidence"
      expect(screen.getByText('80% confidence')).toBeInTheDocument()
    })
  })

  it('renders source count', async () => {
    vi.mocked(listReports).mockResolvedValue([makeReport({ source_count: 5 })])
    render(<ReportsLibrary />)
    await waitFor(() => {
      expect(screen.getByText('5 src')).toBeInTheDocument()
    })
  })

  it('renders word count', async () => {
    vi.mocked(listReports).mockResolvedValue([makeReport({ word_count: 1200 })])
    render(<ReportsLibrary />)
    await waitFor(() => {
      expect(screen.getByText('1,200 words')).toBeInTheDocument()
    })
  })

  it('renders a tag chip', async () => {
    vi.mocked(listReports).mockResolvedValue([makeReport({ tags: ['AI'] })])
    render(<ReportsLibrary />)
    await waitFor(() => {
      expect(screen.getByText('AI')).toBeInTheDocument()
    })
  })

  it('does not show empty state when a report is present', async () => {
    vi.mocked(listReports).mockResolvedValue([makeReport()])
    render(<ReportsLibrary />)
    await waitFor(() => {
      expect(screen.queryByText('No reports yet')).not.toBeInTheDocument()
    })
  })

  it('handles listReports rejection gracefully (no crash)', async () => {
    vi.mocked(listReports).mockRejectedValue(new Error('network error'))
    // Should not throw — the component silently fails
    expect(() => render(<ReportsLibrary />)).not.toThrow()
    // After rejection, empty state appears
    await waitFor(() => {
      expect(screen.getByText('No reports yet')).toBeInTheDocument()
    })
  })
})
