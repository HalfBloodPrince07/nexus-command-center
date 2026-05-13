'use client'

import React, { useEffect, useRef, useState } from 'react'
import gsap from 'gsap'
import ScrollTrigger from 'gsap/ScrollTrigger'
import { Compass, Search, Brain, Send } from 'lucide-react'
import { EASE_OUT_EXPO } from '@/lib/motion'

/* ─────────────────────────────────────────────────────────────────────────────
   PinnedStorytelling
   The centerpiece. A horizontally-thinking, vertically-pinned section
   that walks through the agent loop in 4 beats.

   GSAP ScrollTrigger pins the section for 4 × 100vh of scroll, scrubbing a
   single timeline that crossfades beats. Left-edge progress dots mirror the
   active beat. On reduced-motion, falls back to a vertical stack.
   ───────────────────────────────────────────────────────────────────────────── */

interface Beat {
  id: string
  index: string
  kicker: string
  title: string
  body: string
  icon: React.ElementType
  Visual: React.FC
}

const BEATS: Beat[] = [
  {
    id: 'route',
    index: '01',
    kicker: 'Route',
    title: 'Nexus reads the request and decides who answers.',
    body:
      'Every message hits the supervisor first. It picks the agents that matter, hands them context, and steps out of the way.',
    icon: Compass,
    Visual: RouteViz,
  },
  {
    id: 'retrieve',
    index: '02',
    kicker: 'Retrieve',
    title: 'Three memory layers report what they know.',
    body:
      'Episodic conversations, semantic documents, procedural patterns. Hybrid search blends them — the right facts arrive together.',
    icon: Search,
    Visual: RetrieveViz,
  },
  {
    id: 'reason',
    index: '03',
    kicker: 'Reason',
    title: 'The model thinks out loud, on your hardware.',
    body:
      'LM Studio runs the inference. Specialist agents reason in parallel. You see the activity panel live — nothing happens off-machine.',
    icon: Brain,
    Visual: ReasonViz,
  },
  {
    id: 'respond',
    index: '04',
    kicker: 'Respond',
    title: 'A clean answer streams back, token by token.',
    body:
      'Citations attached, sources resolvable, history written to memory before the cursor stops blinking.',
    icon: Send,
    Visual: RespondViz,
  },
]

/* ── Visualizations (pure SVG/HTML — no external assets) ──────────────────── */

function RouteViz() {
  return (
    <div className="relative h-full w-full">
      <svg viewBox="0 0 360 240" className="h-full w-full">
        <defs>
          <radialGradient id="routeNexus" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#9B82FF" />
            <stop offset="100%" stopColor="#5E3FE6" />
          </radialGradient>
        </defs>
        {/* Edges */}
        {[
          [180, 120, 60, 60],
          [180, 120, 300, 60],
          [180, 120, 60, 180],
          [180, 120, 300, 180],
        ].map(([x1, y1, x2, y2], i) => (
          <line
            key={i}
            x1={x1} y1={y1} x2={x2} y2={y2}
            stroke="rgba(124,92,255,0.35)"
            strokeWidth="1"
            strokeDasharray="3 3"
          />
        ))}
        {/* Nexus center */}
        <circle cx="180" cy="120" r="22" fill="url(#routeNexus)" />
        <circle cx="180" cy="120" r="34" fill="none" stroke="rgba(124,92,255,0.3)" strokeWidth="1" />
        {/* Specialist nodes */}
        {[
          { x: 60, y: 60, name: 'Aria' },
          { x: 300, y: 60, name: 'Forge' },
          { x: 60, y: 180, name: 'Echo' },
          { x: 300, y: 180, name: 'Iris' },
        ].map((n, i) => (
          <g key={n.name}>
            <circle cx={n.x} cy={n.y} r="12" fill="rgba(124,92,255,0.12)" stroke="rgba(124,92,255,0.6)" />
            <text x={n.x} y={n.y + 30} textAnchor="middle" fontFamily="monospace" fontSize="9" fill="rgba(245,245,247,0.55)">
              {n.name}
            </text>
          </g>
        ))}
        <text x="180" y="125" textAnchor="middle" fontFamily="ui-sans-serif" fontSize="10" fontWeight="600" fill="white">
          NEXUS
        </text>
      </svg>
    </div>
  )
}

function RetrieveViz() {
  const layers = [
    { label: 'Episodic', store: 'Redis', count: '124 events' },
    { label: 'Semantic', store: 'ChromaDB', count: '12.4k chunks' },
    { label: 'Procedural', store: 'SQLite', count: '38 patterns' },
  ]
  return (
    <div className="flex h-full w-full flex-col justify-center gap-3">
      {layers.map((l, i) => (
        <div
          key={l.label}
          className="stroke-gradient rounded-xl border border-border-subtle bg-surface-glass px-4 py-3"
        >
          <div className="mb-1.5 flex items-center justify-between">
            <span className="font-display text-sm font-semibold text-ink">{l.label}</span>
            <span className="font-mono text-[10px] uppercase tracking-widest text-ink-tertiary">
              {l.store}
            </span>
          </div>
          {/* Match-strength bar */}
          <div className="h-1 overflow-hidden rounded-full bg-border-subtle">
            <div
              className="h-full bg-gradient-primary"
              style={{ width: `${[78, 92, 64][i]}%` }}
            />
          </div>
          <div className="mt-1.5 flex items-center justify-between">
            <span className="font-mono text-[10px] text-ink-tertiary">{l.count}</span>
            <span className="font-mono text-[10px] text-accent">match {[78, 92, 64][i]}%</span>
          </div>
        </div>
      ))}
    </div>
  )
}

function ReasonViz() {
  const lines = [
    { agent: 'Nexus',  msg: 'route:retrieve+reason; ctx=12.4k chunks' },
    { agent: 'Aria',   msg: 'top-3 from semantic, dedup ✓' },
    { agent: 'Echo',   msg: 'episodic match: turn-7 (0.83)' },
    { agent: 'Nexus',  msg: 'compose; tone=concise; cite=true' },
  ]
  return (
    <div className="flex h-full w-full flex-col justify-center gap-1.5 font-mono text-[11px]">
      {lines.map((l, i) => (
        <div
          key={i}
          className="flex items-center gap-2 rounded-md border border-border-subtle bg-surface-glass px-3 py-1.5"
        >
          <span className="text-accent">›</span>
          <span className="font-semibold text-ink">{l.agent}</span>
          <span className="text-ink-tertiary">·</span>
          <span className="truncate text-ink-secondary">{l.msg}</span>
        </div>
      ))}
      <div className="mt-1 flex items-center gap-2 px-2 text-[10px] uppercase tracking-widest text-ink-tertiary">
        <span className="relative flex h-1.5 w-1.5">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent opacity-50" />
          <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-accent" />
        </span>
        thinking · 312 ms
      </div>
    </div>
  )
}

function RespondViz() {
  return (
    <div className="flex h-full w-full flex-col justify-center">
      <div className="stroke-gradient rounded-2xl border border-border-subtle bg-surface-glass p-5">
        <div className="mb-3 flex items-center gap-2">
          <span className="h-1.5 w-1.5 rounded-full bg-accent" />
          <span className="font-mono text-[10px] uppercase tracking-widest text-ink-tertiary">
            Nexus · streaming
          </span>
        </div>
        <p className="text-sm leading-relaxed text-ink">
          Based on your notes from <span className="rounded bg-accent-muted px-1 text-accent">Tuesday&rsquo;s call</span>{' '}
          and the spec excerpt, the bottleneck is the embedding step — not retrieval. Two options:
        </p>
        <ul className="mt-2 space-y-1 text-sm text-ink-secondary">
          <li>· Switch to BAAI/bge-small (3× faster, ~92% recall)</li>
          <li>· Batch ingestion at chunk-time, not query-time</li>
        </ul>
        <div className="mt-3 flex items-center justify-between">
          <span className="font-mono text-[10px] text-ink-tertiary">cited 3 · local-only</span>
          <span className="inline-block h-3 w-1.5 animate-pulse bg-accent" />
        </div>
      </div>
    </div>
  )
}

/* ── Main section ────────────────────────────────────────────────────────── */

export default function PinnedStorytelling() {
  const wrapRef = useRef<HTMLDivElement>(null)
  const stageRef = useRef<HTMLDivElement>(null)
  const [active, setActive] = useState(0)

  useEffect(() => {
    if (typeof window === 'undefined') return
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (reduced) return

    // Desktop only — on mobile the section becomes a vertical stack via CSS
    if (!window.matchMedia('(min-width: 768px)').matches) return

    const wrap = wrapRef.current
    const stage = stageRef.current
    if (!wrap || !stage) return

    gsap.registerPlugin(ScrollTrigger)

    const beats = stage.querySelectorAll<HTMLElement>('[data-beat]')
    const ctx = gsap.context(() => {
      // Initial visibility — first beat shown, others hidden + offset
      beats.forEach((el, i) => {
        gsap.set(el, {
          autoAlpha: i === 0 ? 1 : 0,
          y: i === 0 ? 0 : 40,
        })
      })

      const tl = gsap.timeline({
        scrollTrigger: {
          trigger: wrap,
          start: 'top top',
          end: () => `+=${BEATS.length * 100}vh`,
          pin: stage,
          pinSpacing: true,
          scrub: 0.6,
          anticipatePin: 1,
          onUpdate: (self) => {
            const i = Math.min(
              BEATS.length - 1,
              Math.floor(self.progress * BEATS.length),
            )
            setActive(i)
          },
        },
      })

      // Crossfade between beats along the timeline
      for (let i = 0; i < BEATS.length - 1; i++) {
        tl.to(beats[i], { autoAlpha: 0, y: -30, duration: 1 }, i + 0.4)
          .to(beats[i + 1], { autoAlpha: 1, y: 0, duration: 1 }, i + 0.4)
      }
    }, stage)

    return () => {
      ctx.revert()
      ScrollTrigger.getAll().forEach((t) => t.kill())
    }
  }, [])

  return (
    <section id="memory" ref={wrapRef} className="relative">
      {/* Header */}
      <div className="mx-auto max-w-7xl px-4 py-24 sm:px-6 sm:py-32">
        <p className="mb-3 font-mono text-[10px] uppercase tracking-[0.3em] text-accent">
          The Loop
        </p>
        <h2 className="display-section font-display font-medium text-ink">
          Route. Retrieve. <span className="text-gradient">Reason. Respond.</span>
        </h2>
        <p className="mt-5 max-w-xl text-base leading-relaxed text-ink-secondary sm:text-lg">
          Four beats. One private machine. Scroll to watch a single message travel through the system.
        </p>
      </div>

      {/* Pinned stage (desktop) — vertical stack on mobile */}
      <div
        ref={stageRef}
        className="relative md:h-screen md:overflow-hidden"
        aria-label="Agent loop walkthrough"
      >
        {/* Left progress rail (desktop) */}
        <div className="pointer-events-none absolute left-6 top-1/2 z-10 hidden -translate-y-1/2 flex-col gap-3 md:flex">
          {BEATS.map((b, i) => (
            <div key={b.id} className="flex items-center gap-3">
              <span
                className={`h-2 w-2 rounded-full transition-all duration-500 ${
                  i <= active
                    ? 'scale-125 bg-accent shadow-glow-accent'
                    : 'bg-border-medium'
                }`}
              />
              <span
                className={`font-mono text-[10px] uppercase tracking-[0.18em] transition-colors duration-500 ${
                  i === active ? 'text-ink' : 'text-ink-tertiary'
                }`}
              >
                {b.index} · {b.kicker}
              </span>
            </div>
          ))}
        </div>

        {/* Beats — absolute on desktop (crossfaded by GSAP), stacked on mobile */}
        <div className="relative mx-auto max-w-7xl md:h-full">
          {BEATS.map((beat, i) => {
            const Icon = beat.icon
            const Visual = beat.Visual
            return (
              <article
                key={beat.id}
                data-beat
                className="relative px-4 py-16 sm:px-6 md:absolute md:inset-0 md:flex md:items-center md:py-0 md:pl-32 md:pr-8"
              >
                <div className="grid w-full gap-10 md:grid-cols-2 md:gap-16">
                  {/* Copy */}
                  <div className="flex flex-col justify-center">
                    <div className="mb-5 inline-flex items-center gap-2.5">
                      <span className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-accent-muted text-accent ring-1 ring-inset ring-border-accent">
                        <Icon size={16} strokeWidth={1.8} />
                      </span>
                      <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-ink-tertiary">
                        Beat {beat.index} — {beat.kicker}
                      </span>
                    </div>
                    <h3 className="font-display text-3xl font-medium leading-tight tracking-tight text-ink sm:text-4xl">
                      {beat.title}
                    </h3>
                    <p className="mt-5 max-w-md text-base leading-relaxed text-ink-secondary">
                      {beat.body}
                    </p>
                  </div>

                  {/* Visual */}
                  <div className="stroke-gradient relative h-[260px] overflow-hidden rounded-3xl border border-border-subtle bg-surface-glass-elevated p-6 backdrop-blur-xl sm:h-[340px]">
                    <Visual />
                  </div>
                </div>
              </article>
            )
          })}
        </div>
      </div>
    </section>
  )
}
