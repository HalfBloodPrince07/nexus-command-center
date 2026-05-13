'use client'

import React, { useEffect, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import { Brain, Database, Layers, Lock, Network, Zap } from 'lucide-react'
import { EASE_OUT_EXPO, STAGGER } from '@/lib/motion'

/* ─────────────────────────────────────────────────────────────────────────────
   BentoFeatures
   Asymmetric 6-cell bento. Each cell has a deliberate micro-interaction:
   · CELL_AGENTS    — orbit ring rotates faster on hover
   · CELL_MEMORY    — three layers stagger in
   · CELL_PRIVACY   — lock icon snaps closed → glow ring
   · CELL_STREAM    — sparkline redraws
   · CELL_RESEARCH  — pipeline dots cascade
   · CELL_LOCAL     — accent hue shifts toward cursor
   No rainbow palette. Single accent (electric violet). No string-targeted GSAP.
   ───────────────────────────────────────────────────────────────────────────── */

interface CellProps {
  className?: string
  children: React.ReactNode
}

function Cell({ className = '', children }: CellProps) {
  return (
    <div
      className={`stroke-gradient group/cell relative isolate overflow-hidden rounded-3xl bg-surface-glass-elevated p-6 backdrop-blur-xl transition-all duration-500 hover:bg-surface-glass-elevated hover:shadow-glass-lg sm:p-7 ${className}`}
      style={{ minHeight: 240 }}
    >
      {/* Cursor-follow glow */}
      <CursorGlow />
      {children}
    </div>
  )
}

function CursorGlow() {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const parent = ref.current?.parentElement
    if (!parent) return
    const onMove = (e: MouseEvent) => {
      const rect = parent.getBoundingClientRect()
      const x = e.clientX - rect.left
      const y = e.clientY - rect.top
      if (ref.current) {
        ref.current.style.setProperty('--gx', `${x}px`)
        ref.current.style.setProperty('--gy', `${y}px`)
      }
    }
    parent.addEventListener('mousemove', onMove)
    return () => parent.removeEventListener('mousemove', onMove)
  }, [])
  return (
    <div
      ref={ref}
      aria-hidden
      className="pointer-events-none absolute inset-0 -z-10 opacity-0 transition-opacity duration-500 group-hover/cell:opacity-100"
      style={{
        background:
          'radial-gradient(280px circle at var(--gx, 50%) var(--gy, 50%), rgba(124,92,255,0.16), transparent 60%)',
      }}
    />
  )
}

function CellHead({
  icon: Icon,
  label,
  title,
}: {
  icon: React.ElementType
  label: string
  title: string
}) {
  return (
    <>
      <div className="mb-5 inline-flex items-center gap-2.5">
        <span className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-accent-muted text-accent ring-1 ring-inset ring-border-accent">
          <Icon size={16} strokeWidth={1.8} />
        </span>
        <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-ink-tertiary">
          {label}
        </span>
      </div>
      <h3 className="font-display text-xl font-semibold tracking-tight text-ink sm:text-2xl">
        {title}
      </h3>
    </>
  )
}

/* ── Cell viz components ─────────────────────────────────────────────────── */

function OrbitViz() {
  return (
    <div className="pointer-events-none relative mt-6 h-32 w-full">
      <div className="absolute left-1/2 top-1/2 h-2 w-2 -translate-x-1/2 -translate-y-1/2 rounded-full bg-accent shadow-glow-accent" />
      {[0, 1, 2].map((ring) => (
        <div
          key={ring}
          aria-hidden
          className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 rounded-full border border-border-subtle transition-[transform,border-color,opacity] duration-700 ease-out group-hover/cell:[animation-duration:2s] group-hover/cell:border-border-glow"
          style={{
            width: `${50 + ring * 28}px`,
            height: `${50 + ring * 28}px`,
            animation: `spin ${10 + ring * 6}s linear infinite`,
          }}
        >
          <span
            className="absolute h-1.5 w-1.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-accent-light shadow-glow-accent"
            style={{ left: `${50 + ring * 8}%`, top: `${20 - ring * 4}%` }}
          />
        </div>
      ))}
      <style jsx>{`
        @keyframes spin {
          to { transform: translate(-50%, -50%) rotate(360deg); }
        }
      `}</style>
    </div>
  )
}

function MemoryViz() {
  const layers = [
    { label: 'Episodic', store: 'Redis' },
    { label: 'Semantic', store: 'ChromaDB' },
    { label: 'Procedural', store: 'SQLite' },
  ]
  return (
    <div className="mt-6 space-y-2">
      {layers.map((l, i) => (
        <div
          key={l.label}
          className="flex items-center justify-between rounded-lg border border-border-subtle bg-surface-glass px-3 py-2 transition-all duration-500"
          style={{
            transitionDelay: `${i * 60}ms`,
          }}
        >
          <div className="flex items-center gap-2">
            <span className="h-1.5 w-1.5 rounded-full bg-accent" />
            <span className="text-xs font-medium text-ink-secondary">{l.label}</span>
          </div>
          <span className="font-mono text-[10px] uppercase tracking-widest text-ink-tertiary">
            {l.store}
          </span>
        </div>
      ))}
    </div>
  )
}

function PrivacyViz() {
  return (
    <div className="mt-6 flex items-center gap-3 font-mono text-[11px] text-ink-tertiary">
      <span className="rounded-md border border-border-subtle bg-surface-glass px-2 py-1">
        outbound: 0
      </span>
      <span className="rounded-md border border-border-subtle bg-surface-glass px-2 py-1">
        cloud: none
      </span>
      <span className="rounded-md border border-border-accent bg-accent-muted px-2 py-1 text-accent">
        local: ✓
      </span>
    </div>
  )
}

function StreamViz() {
  // Simple sparkline that "redraws" on hover via CSS animation
  const points = '0,32 16,18 32,24 48,12 64,22 80,8 96,18 112,4 128,14 144,10'
  return (
    <div className="mt-6">
      <svg viewBox="0 0 144 36" className="h-16 w-full">
        <defs>
          <linearGradient id="streamG" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="rgba(124,92,255,0.0)" />
            <stop offset="100%" stopColor="rgba(124,92,255,1)" />
          </linearGradient>
        </defs>
        <polyline
          points={points}
          fill="none"
          stroke="url(#streamG)"
          strokeWidth="1.4"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="origin-left transition-[stroke-dashoffset] duration-1000"
          style={{
            strokeDasharray: 200,
            strokeDashoffset: 200,
            animation: 'draw-line 1.6s ease-out forwards',
          }}
        />
        <style jsx>{`
          @keyframes draw-line {
            to { stroke-dashoffset: 0; }
          }
        `}</style>
      </svg>
      <div className="mt-2 flex items-center justify-between font-mono text-[10px] uppercase tracking-widest text-ink-tertiary">
        <span>tokens / sec</span>
        <span>~ 48</span>
      </div>
    </div>
  )
}

function PipelineViz() {
  const steps = ['Atlas', 'Vector', 'Fetch', 'Verity', 'Scribe']
  return (
    <div className="mt-6 flex items-center gap-1.5">
      {steps.map((s, i) => (
        <React.Fragment key={s}>
          <div className="flex items-center gap-1.5 rounded-full border border-border-subtle bg-surface-glass px-2 py-1 font-mono text-[10px] text-ink-tertiary transition-colors duration-500 group-hover/cell:[--bullet:var(--accent)]">
            <span
              className="h-1 w-1 rounded-full bg-[var(--bullet,var(--text-muted))]"
              style={{ transitionDelay: `${i * 80}ms` }}
            />
            {s}
          </div>
          {i < steps.length - 1 && (
            <span className="text-ink-tertiary">·</span>
          )}
        </React.Fragment>
      ))}
    </div>
  )
}

function ScaleViz() {
  return (
    <div className="mt-6 grid grid-cols-6 gap-1.5">
      {Array.from({ length: 18 }).map((_, i) => (
        <span
          key={i}
          className="h-3 rounded-sm bg-border-subtle transition-colors duration-500 group-hover/cell:bg-accent"
          style={{ transitionDelay: `${i * 30}ms` }}
        />
      ))}
    </div>
  )
}

/* ── Layout ──────────────────────────────────────────────────────────────── */

export default function BentoFeatures() {
  return (
    <section id="features" className="relative py-24 sm:py-32">
      <div className="mx-auto max-w-7xl px-4 sm:px-6">
        {/* Eyebrow + headline */}
        <div className="mb-14 max-w-2xl">
          <motion.p
            initial={{ opacity: 0, y: 12 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: '-60px' }}
            transition={{ duration: 0.6, ease: EASE_OUT_EXPO }}
            className="mb-3 font-mono text-[10px] uppercase tracking-[0.3em] text-accent"
          >
            Capabilities
          </motion.p>
          <motion.h2
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: '-60px' }}
            transition={{ duration: 0.7, ease: EASE_OUT_EXPO, delay: 0.05 }}
            className="display-section font-display font-medium text-ink"
          >
            Six pieces.<br />
            <span className="text-gradient">One quiet machine.</span>
          </motion.h2>
        </div>

        {/* Bento grid: 6 cells, 4-col on lg, mixed sizing */}
        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: '-80px' }}
          transition={{ staggerChildren: STAGGER.base }}
          className="grid grid-cols-1 gap-4 sm:gap-5 md:grid-cols-2 lg:grid-cols-4 lg:auto-rows-[260px]"
        >
          <Item span="lg:col-span-2 lg:row-span-2">
            <CellHead icon={Brain} label="01 · Agents" title="Tiered orchestration" />
            <p className="mt-3 max-w-md text-sm leading-relaxed text-ink-secondary">
              A supervisor on top, specialists below. Every request gets routed by intent, not by hand-rolled if-else.
            </p>
            <OrbitViz />
          </Item>

          <Item span="lg:col-span-2">
            <CellHead icon={Database} label="02 · Memory" title="Three layers, one mind" />
            <MemoryViz />
          </Item>

          <Item span="lg:col-span-1">
            <CellHead icon={Lock} label="03 · Privacy" title="Zero outbound" />
            <PrivacyViz />
          </Item>

          <Item span="lg:col-span-1">
            <CellHead icon={Zap} label="04 · Streaming" title="Token-by-token" />
            <StreamViz />
          </Item>

          <Item span="lg:col-span-2">
            <CellHead icon={Layers} label="05 · Research" title="Five-step pipeline" />
            <PipelineViz />
            <p className="mt-4 text-sm leading-relaxed text-ink-secondary">
              A small ensemble of agents that fetches, verifies, and writes — like a research desk on your laptop.
            </p>
          </Item>

          <Item span="lg:col-span-2">
            <CellHead icon={Network} label="06 · Scale" title="Workloads, in parallel" />
            <ScaleViz />
            <p className="mt-4 text-sm leading-relaxed text-ink-secondary">
              Fan out across cores. The page you&rsquo;re reading is the only thing serial about this.
            </p>
          </Item>
        </motion.div>
      </div>
    </section>
  )
}

/* Variants child wrapper — staggered cell entrance */
function Item({ children, span = '' }: { children: React.ReactNode; span?: string }) {
  return (
    <motion.div
      variants={{
        hidden: { opacity: 0, y: 28 },
        visible: { opacity: 1, y: 0, transition: { duration: 0.7, ease: EASE_OUT_EXPO } },
      }}
      className={span}
    >
      <Cell className="h-full">{children}</Cell>
    </motion.div>
  )
}
