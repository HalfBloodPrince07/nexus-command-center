/**
 * Tests for PipelineViz component.
 *
 * PipelineViz renders a horizontal pipeline of agent nodes. Each node shows
 * the agent id, label, and a stage badge whose text comes from stageLabels.
 */
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import PipelineViz from '@/components/research/PipelineViz'
import type { PipelineAgentState } from '@/types/research'

// ---------------------------------------------------------------------------
// Shared fixture — mirrors the INITIAL_PIPELINE from useResearchStore
// ---------------------------------------------------------------------------
const INITIAL_PIPELINE: PipelineAgentState[] = [
  { id: 'Atlas',  label: 'Research Lead',   stage: 'idle', detail: '', status: 'idle' },
  { id: 'Vector', label: 'Web Scout',       stage: 'idle', detail: '', status: 'idle' },
  { id: 'Fetch',  label: 'Scraper',         stage: 'idle', detail: '', status: 'idle' },
  { id: 'Verity', label: 'Fact Checker',    stage: 'idle', detail: '', status: 'idle' },
  { id: 'Scribe', label: 'Report Builder',  stage: 'idle', detail: '', status: 'idle' },
]

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('PipelineViz', () => {
  it('renders 5 agent nodes', () => {
    render(<PipelineViz pipeline={INITIAL_PIPELINE} />)

    for (const agent of INITIAL_PIPELINE) {
      expect(screen.getByText(agent.id)).toBeInTheDocument()
    }
  })

  it('renders all agent labels', () => {
    render(<PipelineViz pipeline={INITIAL_PIPELINE} />)
    for (const agent of INITIAL_PIPELINE) {
      expect(screen.getByText(agent.label)).toBeInTheDocument()
    }
  })

  it('active node shows "Searching" stage label', () => {
    const pipeline: PipelineAgentState[] = INITIAL_PIPELINE.map((a) =>
      a.id === 'Vector'
        ? { ...a, status: 'active', stage: 'searching' }
        : { ...a }
    )
    render(<PipelineViz pipeline={pipeline} />)
    // stageLabels maps "searching" → "Searching"
    expect(screen.getByText('Searching')).toBeInTheDocument()
  })

  it('complete node shows "Done" stage label', () => {
    const pipeline: PipelineAgentState[] = INITIAL_PIPELINE.map((a) =>
      a.id === 'Atlas'
        ? { ...a, status: 'complete', stage: 'complete' }
        : { ...a }
    )
    render(<PipelineViz pipeline={pipeline} />)
    // stageLabels maps "complete" → "Done"
    expect(screen.getByText('Done')).toBeInTheDocument()
  })

  it('idle nodes show "Waiting" stage label', () => {
    render(<PipelineViz pipeline={INITIAL_PIPELINE} />)
    // All 5 nodes are idle → 5 "Waiting" badges
    const waitingBadges = screen.getAllByText('Waiting')
    expect(waitingBadges).toHaveLength(5)
  })

  it('renders 4 arrow connectors between 5 nodes', () => {
    const { container } = render(<PipelineViz pipeline={INITIAL_PIPELINE} />)
    // Each arrow is a <svg> element
    const arrows = container.querySelectorAll('svg')
    expect(arrows.length).toBe(4)
  })

  it('does not render detail text when status is idle', () => {
    const pipeline: PipelineAgentState[] = INITIAL_PIPELINE.map((a) =>
      ({ ...a, detail: 'should not appear' })
    )
    render(<PipelineViz pipeline={pipeline} />)
    // Detail is only shown when status === "active"
    expect(screen.queryByText('should not appear')).not.toBeInTheDocument()
  })

  it('renders detail text when agent is active', () => {
    const pipeline: PipelineAgentState[] = INITIAL_PIPELINE.map((a) =>
      a.id === 'Fetch'
        ? { ...a, status: 'active', stage: 'scraping', detail: 'Fetching 5 URLs...' }
        : { ...a }
    )
    render(<PipelineViz pipeline={pipeline} />)
    expect(screen.getByText('Fetching 5 URLs...')).toBeInTheDocument()
  })
})
