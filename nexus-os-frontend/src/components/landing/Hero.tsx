'use client'

import React, { useEffect, useRef, useState } from 'react'
import { motion, useScroll, useTransform, useSpring } from 'framer-motion'
import { ArrowRight, Sparkles } from 'lucide-react'
import { NexusOrb } from '../three/NexusOrb'
import { EASE_OUT_EXPO } from '@/lib/motion'

interface HeroProps {
  onEnter: () => void
}

/* Word-by-word clip-path mask reveal */
function MaskRevealHeadline({
  lines,
  delay = 0,
}: {
  lines: string[]
  delay?: number
}) {
  return (
    <>
      {lines.map((line, lineIdx) => {
        const words = line.split(' ')
        return (
          <span key={lineIdx} className="block">
            {words.map((word, i) => (
              <span
                key={`${lineIdx}-${i}`}
                className="inline-block overflow-hidden align-baseline"
                style={{ paddingBottom: '0.06em' }}
              >
                <motion.span
                  className="inline-block"
                  initial={{ y: '110%' }}
                  animate={{ y: '0%' }}
                  transition={{
                    duration: 1.05,
                    ease: EASE_OUT_EXPO,
                    delay: delay + lineIdx * 0.12 + i * 0.06,
                  }}
                >
                  {word}
                  {i < words.length - 1 ? ' ' : ''}
                </motion.span>
              </span>
            ))}
          </span>
        )
      })}
    </>
  )
}

export default function Hero({ onEnter }: HeroProps) {
  const sectionRef = useRef<HTMLElement>(null)
  const [cursor, setCursor] = useState({ x: 0, y: 0 })

  // Track normalized cursor [-1, 1] relative to viewport center, for orb reactivity
  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      const x = (e.clientX / window.innerWidth) * 2 - 1
      const y = (e.clientY / window.innerHeight) * 2 - 1
      setCursor({ x, y })
    }
    window.addEventListener('mousemove', onMove, { passive: true })
    return () => window.removeEventListener('mousemove', onMove)
  }, [])

  const { scrollY } = useScroll()
  const smooth = useSpring(scrollY, { stiffness: 100, damping: 30, restDelta: 0.001 })

  // Hero parallax: text fades + lifts as you scroll
  const textY = useTransform(smooth, [0, 600], [0, -80])
  const textOpacity = useTransform(smooth, [0, 350, 600], [1, 0.6, 0])
  const orbScale = useTransform(smooth, [0, 600], [1, 1.18])
  const orbY = useTransform(smooth, [0, 600], [0, -40])
  const cueOpacity = useTransform(smooth, [0, 120], [1, 0])

  // For NexusOrb scrollProgress prop (0..1 over the first viewport)
  const [scrollProg, setScrollProg] = useState(0)
  useEffect(() => {
    const unsub = smooth.on('change', (v) => {
      const vh = typeof window !== 'undefined' ? window.innerHeight : 800
      setScrollProg(Math.min(1, v / vh))
    })
    return () => unsub()
  }, [smooth])

  return (
    <section
      ref={sectionRef}
      id="top"
      className="relative isolate flex min-h-[100svh] items-center overflow-hidden px-4 sm:px-8"
    >
      {/* ── Ambient backdrop: mesh gradient + slow aurora + vignette ─── */}
      <div className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute inset-0 bg-gradient-mesh" />
        <div
          className="absolute -inset-[10%] animate-aurora opacity-60"
          style={{
            background:
              'conic-gradient(from 0deg at 50% 50%, rgba(124,92,255,0.10), transparent 30%, rgba(155,130,255,0.08) 60%, transparent 90%, rgba(124,92,255,0.10))',
            filter: 'blur(60px)',
          }}
        />
        {/* Vignette */}
        <div
          className="absolute inset-0"
          style={{
            background:
              'radial-gradient(ellipse at center, transparent 50%, rgba(10,10,11,0.35) 100%)',
          }}
        />
      </div>

      {/* ── Layout: type left, orb right (stacks on mobile) ─── */}
      <div className="relative mx-auto flex w-full max-w-7xl flex-col items-center gap-12 lg:flex-row lg:items-center lg:gap-8">
        {/* ─── Left: type column ─── */}
        <motion.div
          style={{ y: textY, opacity: textOpacity }}
          className="relative z-10 flex w-full flex-col items-center text-center lg:flex-1 lg:items-start lg:text-left"
        >
          {/* Eyebrow */}
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, ease: EASE_OUT_EXPO }}
            className="mb-6 inline-flex items-center gap-2 rounded-full border border-border-subtle bg-surface-glass px-3.5 py-1.5 backdrop-blur-md"
          >
            <Sparkles size={12} className="text-accent" />
            <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-ink-secondary">
              Local-first · Multi-agent
            </span>
          </motion.div>

          {/* Headline */}
          <h1 className="display-hero font-display font-medium text-ink">
            <MaskRevealHeadline lines={['Local-first', 'multi-agent']} delay={0.05} />
            <span className="block">
              <span className="inline-block overflow-hidden align-baseline" style={{ paddingBottom: '0.06em' }}>
                <motion.span
                  className="inline-block text-gradient"
                  initial={{ y: '110%' }}
                  animate={{ y: '0%' }}
                  transition={{ duration: 1.05, ease: EASE_OUT_EXPO, delay: 0.45 }}
                >
                  intelligence.
                </motion.span>
              </span>
            </span>
          </h1>

          {/* Deck */}
          <motion.p
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.9, delay: 0.65, ease: EASE_OUT_EXPO }}
            className="mt-7 max-w-xl text-balance text-base leading-relaxed text-ink-secondary sm:text-lg"
          >
            A private command center for AI agents that think, retrieve, and remember —
            running entirely on your machine. No cloud. No telemetry. No tradeoffs.
          </motion.p>

          {/* CTAs */}
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.85, ease: EASE_OUT_EXPO }}
            className="mt-9 flex flex-col items-center gap-3 sm:flex-row lg:items-start"
          >
            <button
              onClick={onEnter}
              className="group relative inline-flex items-center gap-2.5 overflow-hidden rounded-full bg-gradient-primary px-7 py-3.5 text-sm font-semibold text-white shadow-glow-accent transition-shadow duration-300 hover:shadow-glow-accent-lg"
              data-cursor-hover
            >
              <span className="relative z-10">Launch NEXUS</span>
              <ArrowRight
                size={15}
                className="relative z-10 transition-transform duration-300 group-hover:translate-x-1"
              />
              <span className="pointer-events-none absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-white/30 to-transparent transition-transform duration-700 group-hover:translate-x-full" />
            </button>

            <a
              href="#agents"
              className="group inline-flex items-center gap-2 rounded-full border border-border-subtle bg-surface-glass px-6 py-3.5 text-sm font-medium text-ink-secondary backdrop-blur-md transition-colors duration-300 hover:border-border-glow hover:text-ink"
              data-cursor-hover
            >
              How it works
              <span className="text-ink-tertiary transition-transform duration-300 group-hover:translate-x-0.5">
                ↓
              </span>
            </a>
          </motion.div>

          {/* Trust line */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 1, delay: 1.05 }}
            className="mt-7 flex items-center gap-2 font-mono text-[11px] uppercase tracking-[0.16em] text-ink-tertiary"
          >
            <span className="relative flex h-1.5 w-1.5">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent opacity-50" />
              <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-accent" />
            </span>
            5 agents · 3 memory layers · 0 cloud calls
          </motion.div>
        </motion.div>

        {/* ─── Right: 3D orb ─── */}
        <motion.div
          initial={{ opacity: 0, scale: 0.86 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 1.4, delay: 0.2, ease: EASE_OUT_EXPO }}
          style={{ scale: orbScale, y: orbY }}
          className="relative h-[340px] w-[340px] sm:h-[420px] sm:w-[420px] lg:h-[560px] lg:w-[560px]"
        >
          <NexusOrb
            scrollProgress={scrollProg}
            cursor={cursor}
            className="h-full w-full"
          />
          {/* Soft halo behind canvas (CSS, not 3D — extra cheap) */}
          <div
            aria-hidden
            className="pointer-events-none absolute inset-0 -z-10 rounded-full"
            style={{
              background:
                'radial-gradient(circle at center, rgba(124,92,255,0.18), transparent 60%)',
              filter: 'blur(40px)',
            }}
          />
        </motion.div>
      </div>

      {/* ─── Scroll cue ─── */}
      <motion.div
        style={{ opacity: cueOpacity }}
        className="pointer-events-none absolute bottom-8 left-1/2 flex -translate-x-1/2 flex-col items-center gap-2"
      >
        <span className="font-mono text-[10px] uppercase tracking-[0.3em] text-ink-tertiary">
          Scroll
        </span>
        <motion.span
          animate={{ y: [0, 8, 0] }}
          transition={{ duration: 1.6, repeat: Infinity, ease: 'easeInOut' }}
          className="block h-8 w-px bg-gradient-to-b from-ink-tertiary to-transparent"
        />
      </motion.div>
    </section>
  )
}
