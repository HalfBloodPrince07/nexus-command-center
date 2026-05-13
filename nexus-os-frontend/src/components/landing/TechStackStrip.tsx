'use client'

import { motion } from 'framer-motion'
import { EASE_OUT_EXPO, STAGGER } from '@/lib/motion'

const STACK = [
  { name: 'LM Studio', kind: 'Local LLM runtime' },
  { name: 'ChromaDB', kind: 'Vector store' },
  { name: 'FastAPI', kind: 'Async backend' },
  { name: 'Next.js', kind: 'App Router · TS' },
  { name: 'Redis', kind: 'Episodic cache' },
  { name: 'SQLite', kind: 'Procedural store' },
]

/**
 * "Built on" — quiet, monochrome strip of the actual stack.
 * Stand-in for the conventional "Trusted by" logo bar.
 */
export default function TechStackStrip() {
  return (
    <section className="relative py-14 sm:py-20" aria-label="Built on">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <motion.p
          initial={{ opacity: 0, y: 12 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-60px' }}
          transition={{ duration: 0.6, ease: EASE_OUT_EXPO }}
          className="mb-8 text-center font-mono text-[10px] uppercase tracking-[0.3em] text-ink-tertiary"
        >
          Built on · runs anywhere you can install Python and Node
        </motion.p>

        <div className="grid grid-cols-3 gap-x-6 gap-y-6 sm:grid-cols-6">
          {STACK.map((tech, i) => (
            <motion.div
              key={tech.name}
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-40px' }}
              transition={{
                duration: 0.6,
                delay: i * STAGGER.base,
                ease: EASE_OUT_EXPO,
              }}
              className="group flex flex-col items-center gap-1.5 text-center"
            >
              <span className="font-display text-base font-semibold tracking-tight text-ink-tertiary transition-colors duration-300 group-hover:text-ink">
                {tech.name}
              </span>
              <span className="font-mono text-[9px] uppercase tracking-[0.16em] text-ink-tertiary opacity-0 transition-opacity duration-300 group-hover:opacity-100">
                {tech.kind}
              </span>
            </motion.div>
          ))}
        </div>

        {/* Subtle separator below */}
        <div
          aria-hidden
          className="mx-auto mt-12 h-px max-w-xl bg-gradient-to-r from-transparent via-border-subtle to-transparent"
        />
      </div>
    </section>
  )
}
