'use client'

import React, { useEffect, useRef, useState } from 'react'
import gsap from 'gsap'
import ScrollTrigger from 'gsap/ScrollTrigger'

// ── useRevealOnScroll ────────────────────────────────────────────────────────
// IntersectionObserver-based reveal: opacity 0 → 1 + y: 24 → 0
export function useRevealOnScroll(threshold = 0.15) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!ref.current) return

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add('is-revealed')
          } else {
            entry.target.classList.remove('is-revealed')
          }
        })
      },
      { threshold, rootMargin: '-80px 0px -40% 0px' }
    )

    observer.observe(ref.current)

    return () => observer.disconnect()
  }, [threshold])

  return ref as React.RefObject<HTMLDivElement>
}

// ── useScrollProgress ───────────────────────────────────────────────────────
// Normalized scroll progress (0-1) with smooth lerping
export function useScrollProgress(maxScroll?: number) {
  const [progress, setProgress] = useState(0)

  useEffect(() => {
    const getMax = () =>
      maxScroll ?? (document.documentElement.scrollHeight - window.innerHeight)

    let raf: number

    const update = () => {
      const scrolled = window.scrollY
      const newProgress = Math.min(1, Math.max(0, scrolled / (getMax() || 1)))
      setProgress(newProgress)
      raf = requestAnimationFrame(update)
    }

    update()
    return () => cancelAnimationFrame(raf)
  }, [maxScroll])

  return progress
}

// ── useParallaxYield ───────────────────────────────────────────────────────
// Yields control of an element's transform based on scroll position
export function useParallaxYield(targetRef: React.RefObject<HTMLElement>, intensity = 0.5) {
  const [y, setY] = useState(0)

  useEffect(() => {
    if (!targetRef.current) return

    let raf: number

    const loop = () => {
      const rect = targetRef.current?.getBoundingClientRect()
      if (rect && !isOutsideViewport(rect)) {
        const centerY = window.innerHeight / 2
        const scrollPos = window.scrollY + centerY - rect.top
        setY(scrollPos * intensity)
      }
      raf = requestAnimationFrame(loop)
    }

    loop()
    return () => cancelAnimationFrame(raf)
  }, [targetRef, intensity])

  return y
}

// ── useScrollTextMasking ───────────────────────────────────────────────────
// Reveals text from behind clip-path as you scroll into it
export function useScrollTextMasking(textRef: React.RefObject<HTMLDivElement>, triggerRef: React.RefObject<HTMLElement>) {
  const [maskProgress, setMaskProgress] = useState(0)

  useEffect(() => {
    if (!textRef.current || !triggerRef.current) return

    let raf: number

    const loop = () => {
      const rect = triggerRef.current?.getBoundingClientRect()
      const textRect = textRef.current!.getBoundingClientRect()

      if (rect && textRect && !isOutsideViewport(rect)) {
        const viewportTop = window.scrollY + 100
        const triggerBottom = rect.bottom
        const textTop = textRect.top

        let progress = (viewportTop - textTop) / (triggerBottom - textTop)
        progress = Math.max(0, Math.min(1, progress))

        setMaskProgress(progress)
      } else {
        setMaskProgress(prev => Math.min(prev + 0.05, 1))
      }

      raf = requestAnimationFrame(loop)
    }

    loop()
    return () => cancelAnimationFrame(raf)
  }, [textRef, triggerRef])

  return maskProgress
}

// Helper: Check if rect is outside viewport
function isOutsideViewport(rect: DOMRect): boolean {
  return (rect.top > window.innerHeight + 100 || rect.bottom < -100) && (rect.left > window.innerWidth || rect.right < 0)
}
