/**
 * Tests for useResearchStore (Zustand store).
 *
 * Each test resets the store state in beforeEach to ensure full isolation.
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { useResearchStore } from '@/stores/useResearchStore'
import type { ResearchReport } from '@/types/research'

// ---------------------------------------------------------------------------
// Minimal ResearchReport fixture
// ---------------------------------------------------------------------------
const makeReport = (overrides: Partial<ResearchReport> = {}): ResearchReport => ({
  slug: 'test-slug',
  topic: 'Test Topic',
  created_at: '2025-01-01T00:00:00Z',
  source_count: 3,
  avg_confidence: 0.75,
  status: 'complete',
  job_id: 'job-1',
  word_count: 800,
  tags: ['test'],
  ...overrides,
})

// ---------------------------------------------------------------------------
// Reset store before every test
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
})

// ---------------------------------------------------------------------------
// startJob
// ---------------------------------------------------------------------------

describe('startJob', () => {
  it('initializes pipeline with 5 idle agents', () => {
    useResearchStore.getState().startJob('AI', 'job-1', 'ai')
    const { activeJob } = useResearchStore.getState()

    expect(activeJob).not.toBeNull()
    expect(activeJob!.pipeline).toHaveLength(5)
    for (const agent of activeJob!.pipeline) {
      expect(agent.status).toBe('idle')
    }
  })

  it('sets topic, job_id, and slug on the active job', () => {
    useResearchStore.getState().startJob('Quantum Computing', 'job-42', 'quantum-computing')
    const { activeJob } = useResearchStore.getState()

    expect(activeJob!.topic).toBe('Quantum Computing')
    expect(activeJob!.job_id).toBe('job-42')
    expect(activeJob!.slug).toBe('quantum-computing')
  })

  it('sets active job status to "running"', () => {
    useResearchStore.getState().startJob('AI', 'job-1', 'ai')
    expect(useResearchStore.getState().activeJob!.status).toBe('running')
  })
})

// ---------------------------------------------------------------------------
// updatePipelineAgent
// ---------------------------------------------------------------------------

describe('updatePipelineAgent', () => {
  it('mutates only the target agent', () => {
    useResearchStore.getState().startJob('AI', 'job-1', 'ai')
    useResearchStore.getState().updatePipelineAgent('Vector', { status: 'active', stage: 'searching' })

    const { pipeline } = useResearchStore.getState().activeJob!

    const vector = pipeline.find((a) => a.id === 'Vector')!
    expect(vector.status).toBe('active')
    expect(vector.stage).toBe('searching')

    // All other agents must remain idle
    const others = pipeline.filter((a) => a.id !== 'Vector')
    for (const agent of others) {
      expect(agent.status).toBe('idle')
    }
  })

  it('does nothing when activeJob is null', () => {
    // Should not throw
    expect(() =>
      useResearchStore.getState().updatePipelineAgent('Vector', { status: 'active' })
    ).not.toThrow()
  })
})

// ---------------------------------------------------------------------------
// completeJob
// ---------------------------------------------------------------------------

describe('completeJob', () => {
  it('sets activeJob status to "complete"', () => {
    useResearchStore.getState().startJob('AI', 'job-1', 'ai')
    useResearchStore.getState().completeJob(makeReport())
    expect(useResearchStore.getState().activeJob!.status).toBe('complete')
  })

  it('adds the report to the reports list', () => {
    useResearchStore.getState().startJob('AI', 'job-1', 'ai')
    useResearchStore.getState().completeJob(makeReport({ slug: 'ai' }))
    expect(useResearchStore.getState().reports).toHaveLength(1)
  })

  it('does not duplicate an already-listed report', () => {
    useResearchStore.getState().startJob('AI', 'job-1', 'ai')
    const report = makeReport({ slug: 'ai' })
    // Pre-seed the reports list with the same slug
    useResearchStore.setState({ reports: [report] })
    useResearchStore.getState().completeJob(report)
    expect(useResearchStore.getState().reports).toHaveLength(1)
  })

  it('marks all pipeline agents complete', () => {
    useResearchStore.getState().startJob('AI', 'job-1', 'ai')
    useResearchStore.getState().completeJob(makeReport())
    const { pipeline } = useResearchStore.getState().activeJob!
    for (const agent of pipeline) {
      expect(agent.status).toBe('complete')
    }
  })
})

// ---------------------------------------------------------------------------
// failJob
// ---------------------------------------------------------------------------

describe('failJob', () => {
  it('sets activeJob status to "failed"', () => {
    useResearchStore.getState().startJob('AI', 'job-1', 'ai')
    useResearchStore.getState().failJob('timeout')
    expect(useResearchStore.getState().activeJob!.status).toBe('failed')
  })

  it('stores the error message', () => {
    useResearchStore.getState().startJob('AI', 'job-1', 'ai')
    useResearchStore.getState().failJob('LLM timeout after 30s')
    expect(useResearchStore.getState().activeJob!.error).toBe('LLM timeout after 30s')
  })
})

// ---------------------------------------------------------------------------
// removeReport
// ---------------------------------------------------------------------------

describe('removeReport', () => {
  it('removes the matching report by slug', () => {
    useResearchStore.setState({
      reports: [makeReport({ slug: 'ai' }), makeReport({ slug: 'ml', topic: 'Machine Learning' })],
    })
    useResearchStore.getState().removeReport('ai')
    const { reports } = useResearchStore.getState()
    expect(reports).toHaveLength(1)
    expect(reports[0].slug).toBe('ml')
  })

  it('results in empty list when only report is removed', () => {
    useResearchStore.setState({ reports: [makeReport({ slug: 'ai' })] })
    useResearchStore.getState().removeReport('ai')
    expect(useResearchStore.getState().reports).toHaveLength(0)
  })

  it('clears viewingSlug and viewingReport when removed slug is currently viewed', () => {
    useResearchStore.setState({
      reports: [makeReport({ slug: 'ai' })],
      viewingSlug: 'ai',
      viewingReport: { content: '# Report', metadata: makeReport({ slug: 'ai' }) },
    })
    useResearchStore.getState().removeReport('ai')
    const state = useResearchStore.getState()
    expect(state.viewingSlug).toBeNull()
    expect(state.viewingReport).toBeNull()
  })
})

// ---------------------------------------------------------------------------
// setReports
// ---------------------------------------------------------------------------

describe('setReports', () => {
  it('replaces the reports list entirely', () => {
    useResearchStore.setState({ reports: [makeReport({ slug: 'old' })] })
    useResearchStore.getState().setReports([makeReport({ slug: 'new', topic: 'New' })])
    const { reports } = useResearchStore.getState()
    expect(reports).toHaveLength(1)
    expect(reports[0].slug).toBe('new')
  })
})
