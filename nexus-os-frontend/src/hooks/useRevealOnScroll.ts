'use client'

import { useEffect, useRef, useState } from 'react'
import { useInView } from 'framer-motion'

/**
 * Hook for scroll-triggered reveal animations.
 *
 * Returns a boolean indicating whether the element is currently in view,
 * along with animation progress (0-1) for partial reveals.
 */
export function useRevealOnScroll(
  options?: {
    once?: boolean
    margin?: string
    threshold?: number
  }
) {
  const ref = useRef<HTMLDivElement>(null)
  const [revealed, setRevealed] = useState(false)
  const [progress, setProgress] = useState(0)

  useEffect(() => {
    if (!ref.current) return

    const el = ref.current
    const { once = false, margin = '-100px', threshold = 0.5 } = options || {}

    // Use IntersectionObserver for better performance than useInView
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            setProgress(entry.intersectionRatio)
            if (progress < 1 || !once) {
              setRevealed(true)
            }
          } else if (!once && progress > 0) {
            // Optional: hide on scroll out
            setRevealed(false)
            setProgress(0)
          }
        })
      },
      { rootMargin: margin, threshold }
    )

    observer.observe(el)

    return () => observer.disconnect()
  }, [options?.once, options?.margin, options?.threshold])

  return { ref, revealed, progress }
}
