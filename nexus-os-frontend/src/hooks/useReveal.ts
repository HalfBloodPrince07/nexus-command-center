'use client'

import { useEffect, useRef, useState } from 'react'

interface RevealOptions {
  threshold?: number
  rootMargin?: string
  once?: boolean
}

/**
 * IntersectionObserver-based reveal trigger.
 * Pair with motion variants: opacity 0→1, y 24→0, ease EASE_OUT_EXPO.
 */
export function useReveal<T extends HTMLElement = HTMLDivElement>(
  options: RevealOptions = {},
) {
  const { threshold = 0.15, rootMargin = '-60px', once = true } = options
  const ref = useRef<T>(null)
  const [revealed, setRevealed] = useState(false)

  useEffect(() => {
    const el = ref.current
    if (!el || typeof IntersectionObserver === 'undefined') return

    const obs = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            setRevealed(true)
            if (once) obs.disconnect()
          } else if (!once) {
            setRevealed(false)
          }
        })
      },
      { threshold, rootMargin },
    )

    obs.observe(el)
    return () => obs.disconnect()
  }, [threshold, rootMargin, once])

  return [ref, revealed] as const
}
