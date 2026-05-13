'use client'

import React, { useEffect, useRef, useState } from 'react'
import { motion, useInView } from 'framer-motion'
import {
  ArrowRight,
  Bot,
  Brain,
  Clock,
  Cpu,
  FileText,
  FlaskConical,
  Globe,
  HardDrive,
  Layers,
  Lock,
  Network,
  Search,
  Shield,
} from 'lucide-react'

import FloatingNav from './FloatingNav'
import TechStackStrip from './TechStackStrip'
import Hero from './Hero'
import PinnedStorytelling from './PinnedStorytelling'
import BentoFeatures from './BentoFeatures'
import { EASE_OUT_EXPO, STAGGER } from '@/lib/motion'

interface LandingPageProps {
  onEnter: () => void
}

/* ── Data ──────────────────────────────────────────────────────────────────── */

const AGENTS = [
  {
    id: 'nexus',
    name: 'Nexus',
    tier: 1,
    role: 'Supervisor',
    description:
      'Reads every message, picks the specialists, and stitches the answer together.',
  },
  {
    id: 'aria',
    name: 'Aria',
    tier: 2,
    role: 'Knowledge Lead',
    description:
      'Owns deep retrieval and semantic understanding across your indexed corpus.',
  },
  {
    id: 'forge',
    name: 'Forge',
    tier: 3,
    role: 'File Processor',
    description:
      'Parses, chunks, and embeds documents into the persistent knowledge layer.',
  },
  {
    id: 'echo',
    name: 'Echo',
    tier: 3,
    role: 'RAG Retriever',
    description: 'Hybrid semantic + keyword search across the document corpus, in real time.',
  },
  {
    id: 'iris',
    name: 'Iris',
    tier: 3,
    role: 'Vision Specialist',
    description: 'Reads images and multi-modal PDFs with full visual understanding.',
  },
] as const

const STATS = [
  { value: 5, suffix: '', prefix: '', label: 'Active Agents', icon: Bot },
  { value: 3, suffix: '', prefix: '', label: 'Memory Layers', icon: Layers },
  { value: 100, suffix: '%', prefix: '', label: 'Local & Private', icon: Lock },
  { value: 2, suffix: 's', prefix: '<', label: 'Avg Response', icon: Clock },
  { value: 50, suffix: 'MB', prefix: '', label: 'Max Upload', icon: HardDrive },
  { value: 19, suffix: '+', prefix: '', label: 'Agent Ecosystem', icon: Network },
] as const

const PIPELINE = [
  { name: 'Atlas', role: 'Lead', icon: FlaskConical },
  { name: 'Vector', role: 'Web Scout', icon: Globe },
  { name: 'Fetch', role: 'Scraper', icon: Search },
  { name: 'Verity', role: 'Fact Checker', icon: Shield },
  { name: 'Scribe', role: 'Writer', icon: FileText },
] as const

/* ── Counter ──────────────────────────────────────────────────────────────── */

function Counter({
  value,
  prefix = '',
  suffix = '',
  trigger,
}: {
  value: number
  prefix?: string
  suffix?: string
  trigger: boolean
}) {
  const [display, setDisplay] = useState(0)

  useEffect(() => {
    if (!trigger) return
    const duration = 1400
    const start = performance.now()
    let raf = 0
    const tick = (now: number) => {
      const t = Math.min((now - start) / duration, 1)
      const eased = 1 - Math.pow(1 - t, 3)
      setDisplay(Math.round(eased * value))
      if (t < 1) raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [trigger, value])

  return (
    <>
      {prefix}
      {display}
      {suffix}
    </>
  )
}

/* ── Section header ───────────────────────────────────────────────────────── */

function SectionHeader({
  eyebrow,
  title,
  highlight,
  subtitle,
}: {
  eyebrow: string
  title: string
  highlight?: string
  subtitle?: string
}) {
  return (
    <div className="mb-14 max-w-2xl">
      <motion.p
        initial={{ opacity: 0, y: 10 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: '-60px' }}
        transition={{ duration: 0.5, ease: EASE_OUT_EXPO }}
        className="mb-3 font-mono text-[10px] uppercase tracking-[0.3em] text-accent"
      >
        {eyebrow}
      </motion.p>
      <motion.h2
        initial={{ opacity: 0, y: 16 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: '-60px' }}
        transition={{ duration: 0.7, delay: 0.05, ease: EASE_OUT_EXPO }}
        className="display-section font-display font-medium text-ink"
      >
        {title}{' '}
        {highlight && <span className="text-gradient">{highlight}</span>}
      </motion.h2>
      {subtitle && (
        <motion.p
          initial={{ opacity: 0, y: 12 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-60px' }}
          transition={{ duration: 0.7, delay: 0.12, ease: EASE_OUT_EXPO }}
          className="mt-5 max-w-xl text-base leading-relaxed text-ink-secondary sm:text-lg"
        >
          {subtitle}
        </motion.p>
      )}
    </div>
  )
}

/* ── Page ─────────────────────────────────────────────────────────────────── */

const LandingPage = ({ onEnter }: LandingPageProps) => {
  const statsRef = useRef<HTMLElement>(null)
  const statsInView = useInView(statsRef, { once: true, margin: '-80px' })

  return (
    <div className="relative min-h-screen">
      <FloatingNav onEnter={onEnter} />

      <Hero onEnter={onEnter} />

      <div className="relative z-20">
        <TechStackStrip />

        <PinnedStorytelling />

        <BentoFeatures />

        {/* ── STATS ──────────────────────────────────────────────────────── */}
        <section ref={statsRef} className="py-20 sm:py-28">
          <div className="mx-auto max-w-6xl px-4 sm:px-6">
            <div className="stroke-gradient rounded-3xl border border-border-subtle bg-surface-glass-elevated p-6 backdrop-blur-xl sm:p-10">
              <div className="grid grid-cols-2 gap-y-8 sm:grid-cols-3 lg:grid-cols-6">
                {STATS.map((stat, i) => {
                  const Icon = stat.icon
                  return (
                    <motion.div
                      key={stat.label}
                      initial={{ opacity: 0, y: 18 }}
                      animate={statsInView ? { opacity: 1, y: 0 } : {}}
                      transition={{
                        duration: 0.6,
                        delay: i * STAGGER.base,
                        ease: EASE_OUT_EXPO,
                      }}
                      className="flex flex-col items-center text-center"
                    >
                      <div className="mb-3 inline-flex h-9 w-9 items-center justify-center rounded-xl bg-accent-muted text-accent ring-1 ring-inset ring-border-accent">
                        <Icon size={15} strokeWidth={1.8} />
                      </div>
                      <p className="font-display text-3xl font-medium tabular-nums tracking-tight text-ink sm:text-4xl">
                        <Counter
                          value={stat.value}
                          prefix={stat.prefix}
                          suffix={stat.suffix}
                          trigger={statsInView}
                        />
                      </p>
                      <p className="mt-1 font-mono text-[10px] uppercase tracking-[0.18em] text-ink-tertiary">
                        {stat.label}
                      </p>
                    </motion.div>
                  )
                })}
              </div>
            </div>
          </div>
        </section>

        {/* ── AGENTS ────────────────────────────────────────────────────── */}
        <section id="agents" className="py-20 sm:py-28">
          <div className="mx-auto max-w-7xl px-4 sm:px-6">
            <SectionHeader
              eyebrow="The Roster"
              title="Five agents."
              highlight="One supervisor."
              subtitle="A small, opinionated team. Tier-one reads intent. Tier-three does the work. Nothing is general-purpose for the sake of being general-purpose."
            />

            {/* Featured: Nexus */}
            <motion.div
              initial={{ opacity: 0, y: 28 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-60px' }}
              transition={{ duration: 0.7, ease: EASE_OUT_EXPO }}
              className="mb-5"
            >
              <div className="stroke-gradient relative overflow-hidden rounded-3xl border border-border-subtle bg-surface-glass-elevated p-8 backdrop-blur-xl transition-shadow duration-500 hover:shadow-glow-accent sm:p-10">
                <div className="absolute inset-0 -z-10 bg-gradient-subtle opacity-60" />
                <div className="flex flex-col gap-7 sm:flex-row sm:items-center">
                  <div className="relative shrink-0">
                    <div className="flex h-20 w-20 items-center justify-center rounded-2xl bg-gradient-primary shadow-glow-accent sm:h-24 sm:w-24">
                      <span className="font-display text-3xl font-semibold text-white sm:text-4xl">
                        N
                      </span>
                    </div>
                    <span className="absolute -right-1 -top-1 h-3 w-3 rounded-full bg-accent shadow-glow-accent" />
                  </div>
                  <div className="flex-1">
                    <div className="mb-2.5 flex flex-wrap items-center gap-2">
                      <h3 className="font-display text-2xl font-medium tracking-tight text-ink">
                        Nexus
                      </h3>
                      <span className="rounded-full border border-border-accent bg-accent-muted px-2.5 py-0.5 font-mono text-[10px] uppercase tracking-[0.16em] text-accent">
                        Tier 1 · Supervisor
                      </span>
                    </div>
                    <p className="max-w-2xl text-base leading-relaxed text-ink-secondary">
                      Routes traffic. Holds context. Decides who answers. The only agent
                      that talks to all of the others.
                    </p>
                  </div>
                  <div className="flex shrink-0 flex-col gap-2 sm:items-end">
                    {['Routes all traffic', 'Holds context', 'Always listening'].map(
                      (tag) => (
                        <span
                          key={tag}
                          className="inline-flex items-center gap-2 rounded-full border border-border-subtle bg-surface-glass px-3 py-1 font-mono text-[10px] uppercase tracking-[0.14em] text-ink-tertiary"
                        >
                          <span className="h-1 w-1 rounded-full bg-accent" />
                          {tag}
                        </span>
                      ),
                    )}
                  </div>
                </div>
              </div>
            </motion.div>

            {/* T2 + T3 grid */}
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {AGENTS.slice(1).map((agent, i) => (
                <motion.div
                  key={agent.id}
                  initial={{ opacity: 0, y: 24 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true, margin: '-50px' }}
                  transition={{
                    duration: 0.6,
                    delay: i * STAGGER.base,
                    ease: EASE_OUT_EXPO,
                  }}
                >
                  <div className="stroke-gradient group relative h-full overflow-hidden rounded-2xl border border-border-subtle bg-surface-glass-elevated p-6 backdrop-blur-xl transition-all duration-500 hover:-translate-y-0.5 hover:border-border-accent">
                    <div className="mb-4 flex items-center gap-3">
                      <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-accent-muted text-accent ring-1 ring-inset ring-border-accent transition-transform duration-500 group-hover:scale-105">
                        <span className="font-display text-base font-semibold">
                          {agent.name[0]}
                        </span>
                      </div>
                      <div>
                        <div className="flex items-center gap-1.5">
                          <span className="font-display text-base font-semibold text-ink">
                            {agent.name}
                          </span>
                          <span className="rounded-full border border-border-subtle bg-surface-glass px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-widest text-ink-tertiary">
                            T{agent.tier}
                          </span>
                        </div>
                        <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink-tertiary">
                          {agent.role}
                        </p>
                      </div>
                    </div>
                    <p className="text-sm leading-relaxed text-ink-secondary">
                      {agent.description}
                    </p>
                    <div className="mt-5 flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-[0.14em] text-ink-tertiary">
                      <span className="relative flex h-1.5 w-1.5">
                        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent opacity-40" />
                        <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-accent" />
                      </span>
                      Idle · Ready
                    </div>
                  </div>
                </motion.div>
              ))}
            </div>
          </div>
        </section>

        {/* ── RESEARCH PIPELINE ──────────────────────────────────────────── */}
        <section id="research" className="py-20 sm:py-28">
          <div className="mx-auto max-w-6xl px-4 sm:px-6">
            <SectionHeader
              eyebrow="Research Pipeline"
              title="Five steps."
              highlight="One verified report."
              subtitle="A second team — outside the main loop — that fans out, checks the receipts, and writes it up."
            />

            <div className="relative">
              {/* Connecting line — desktop only */}
              <div
                aria-hidden
                className="absolute left-0 right-0 top-[42px] hidden h-px bg-gradient-to-r from-transparent via-border-accent to-transparent lg:block"
              />

              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
                {PIPELINE.map((step, i) => {
                  const Icon = step.icon
                  return (
                    <motion.div
                      key={step.name}
                      initial={{ opacity: 0, y: 22 }}
                      whileInView={{ opacity: 1, y: 0 }}
                      viewport={{ once: true, margin: '-40px' }}
                      transition={{
                        duration: 0.55,
                        delay: i * STAGGER.base,
                        ease: EASE_OUT_EXPO,
                      }}
                      className="relative"
                    >
                      <div className="stroke-gradient group rounded-2xl border border-border-subtle bg-surface-glass-elevated p-5 text-center backdrop-blur-xl transition-all duration-500 hover:-translate-y-1 hover:border-border-accent">
                        <span className="absolute -top-2.5 left-1/2 inline-flex h-5 w-5 -translate-x-1/2 items-center justify-center rounded-full border border-border-subtle bg-surface-primary font-mono text-[9px] font-semibold text-ink-tertiary">
                          {String(i + 1).padStart(2, '0')}
                        </span>
                        <div className="mx-auto mb-3 flex h-11 w-11 items-center justify-center rounded-xl bg-accent-muted text-accent ring-1 ring-inset ring-border-accent">
                          <Icon size={18} strokeWidth={1.8} />
                        </div>
                        <p className="font-display text-base font-semibold text-ink">
                          {step.name}
                        </p>
                        <p className="mt-0.5 font-mono text-[10px] uppercase tracking-[0.14em] text-ink-tertiary">
                          {step.role}
                        </p>
                      </div>
                    </motion.div>
                  )
                })}
              </div>
            </div>

            <motion.div
              initial={{ opacity: 0, y: 14 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.6, delay: 0.2, ease: EASE_OUT_EXPO }}
              className="mt-10 flex justify-center"
            >
              <div className="inline-flex items-center gap-3 rounded-full border border-border-subtle bg-surface-glass px-5 py-2.5 font-mono text-[11px] uppercase tracking-[0.18em] text-ink-tertiary backdrop-blur-md">
                <span className="h-1.5 w-1.5 rounded-full bg-accent" />
                Cited · Structured · Local-only
              </div>
            </motion.div>
          </div>
        </section>

        {/* ── FINAL CTA ─────────────────────────────────────────────────── */}
        <section className="px-4 pb-32 pt-16 sm:px-6 sm:pb-40 sm:pt-24">
          <div className="mx-auto max-w-3xl">
            <motion.div
              initial={{ opacity: 0, y: 24 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-80px' }}
              transition={{ duration: 0.8, ease: EASE_OUT_EXPO }}
              className="stroke-gradient relative overflow-hidden rounded-[2.5rem] border border-border-subtle bg-surface-glass-elevated p-10 text-center backdrop-blur-xl sm:p-16"
            >
              {/* Ambient halo */}
              <div
                aria-hidden
                className="pointer-events-none absolute -top-32 left-1/2 h-72 w-72 -translate-x-1/2 rounded-full bg-accent/30 blur-[100px]"
              />
              <div className="absolute inset-0 -z-10 bg-gradient-mesh opacity-60" />

              <div className="relative z-10">
                <div className="mx-auto mb-6 flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-primary shadow-glow-accent">
                  <Cpu size={22} className="text-white" strokeWidth={1.8} />
                </div>
                <h2 className="display-section font-display font-medium text-ink">
                  Ready when you are.
                </h2>
                <p className="mx-auto mt-5 max-w-md text-base leading-relaxed text-ink-secondary">
                  Five agents. Three memory layers. Zero outbound calls. Open the
                  command center and write your first message.
                </p>

                {/* Mini avatars */}
                <div className="mt-8 flex items-center justify-center">
                  {AGENTS.map((a, i) => (
                    <div
                      key={a.id}
                      style={{
                        zIndex: AGENTS.length - i,
                        marginLeft: i === 0 ? 0 : '-8px',
                      }}
                      className="flex h-9 w-9 items-center justify-center rounded-full bg-gradient-primary font-display text-xs font-semibold text-white ring-2 ring-surface-primary"
                    >
                      {a.name[0]}
                    </div>
                  ))}
                  <span className="ml-3 font-mono text-[11px] uppercase tracking-[0.16em] text-ink-tertiary">
                    5 agents · standing by
                  </span>
                </div>

                <button
                  onClick={onEnter}
                  className="group relative mt-9 inline-flex items-center gap-3 overflow-hidden rounded-full bg-gradient-primary px-9 py-4 text-sm font-semibold text-white shadow-glow-accent transition-shadow duration-300 hover:shadow-glow-accent-lg"
                  data-cursor-hover
                >
                  <span className="relative z-10">Launch Command Center</span>
                  <ArrowRight
                    size={16}
                    className="relative z-10 transition-transform duration-300 group-hover:translate-x-1"
                  />
                  <span className="pointer-events-none absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-white/30 to-transparent transition-transform duration-700 group-hover:translate-x-full" />
                </button>
              </div>
            </motion.div>
          </div>
        </section>
      </div>
    </div>
  )
}

export default LandingPage
