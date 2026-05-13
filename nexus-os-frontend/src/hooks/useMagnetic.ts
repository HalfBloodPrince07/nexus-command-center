'use client'

import { useEffect, useRef, useState } from 'react'

interface MagneticState {
  x: number
  y: number
}

/**
 * Pulls an element toward the cursor on hover.
 * `strength` is the divisor — lower = stronger pull (8 default ≈ 6–10px shift).
 * No-ops on coarse pointers (touch).
 */
export function useMagnetic<T extends HTMLElement = HTMLButtonElement>(
  strength = 8,
) {
  const ref = useRef<T>(null)
  const [offset, setOffset] = useState<MagneticState>({ x: 0, y: 0 })

  useEffect(() => {
    const el = ref.current
    if (!el) return
    if (
      typeof window !== 'undefined' &&
      window.matchMedia('(pointer: coarse)').matches
    ) {
      return
    }

    const onMove = (e: MouseEvent) => {
      const rect = el.getBoundingClientRect()
      const dx = e.clientX - (rect.left + rect.width / 2)
      const dy = e.clientY - (rect.top + rect.height / 2)
      setOffset({ x: dx / strength, y: dy / strength })
    }
    const onLeave = () => setOffset({ x: 0, y: 0 })

    el.addEventListener('mousemove', onMove)
    el.addEventListener('mouseleave', onLeave)
    return () => {
      el.removeEventListener('mousemove', onMove)
      el.removeEventListener('mouseleave', onLeave)
    }
  }, [strength])

  return [ref, offset] as const
}
