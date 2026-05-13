'use client'

import { useEffect, useRef, useState } from 'react'

/**
 * Custom cursor: a small dot trailed by a soft ring that scales up on
 * interactive elements. Disabled on touch (coarse pointers).
 *
 * Touch detection happens client-side; on touch we never set the
 * `data-cursor="custom"` flag, so the native cursor stays.
 */
export default function CustomCursor() {
  const dotRef = useRef<HTMLDivElement>(null)
  const ringRef = useRef<HTMLDivElement>(null)
  const [enabled, setEnabled] = useState(false)
  const [hovering, setHovering] = useState(false)
  const [hidden, setHidden] = useState(true)

  useEffect(() => {
    if (typeof window === 'undefined') return
    const isCoarse = window.matchMedia('(pointer: coarse)').matches
    if (isCoarse) return

    setEnabled(true)
    document.documentElement.setAttribute('data-cursor', 'custom')

    return () => {
      document.documentElement.removeAttribute('data-cursor')
    }
  }, [])

  useEffect(() => {
    if (!enabled) return

    let rafId = 0
    let mouseX = -100
    let mouseY = -100
    let ringX = -100
    let ringY = -100

    const onMove = (e: MouseEvent) => {
      mouseX = e.clientX
      mouseY = e.clientY
      if (hidden) setHidden(false)
    }

    const onEnterInteractive = () => setHovering(true)
    const onLeaveInteractive = () => setHovering(false)
    const onLeaveWindow = () => setHidden(true)
    const onEnterWindow = () => setHidden(false)

    const tick = () => {
      // Dot follows mouse 1:1
      if (dotRef.current) {
        dotRef.current.style.transform = `translate3d(${mouseX}px, ${mouseY}px, 0) translate(-50%, -50%)`
      }
      // Ring lerps for trailing softness
      ringX += (mouseX - ringX) * 0.18
      ringY += (mouseY - ringY) * 0.18
      if (ringRef.current) {
        ringRef.current.style.transform = `translate3d(${ringX}px, ${ringY}px, 0) translate(-50%, -50%)`
      }
      rafId = requestAnimationFrame(tick)
    }

    window.addEventListener('mousemove', onMove)
    document.addEventListener('mouseleave', onLeaveWindow)
    document.addEventListener('mouseenter', onEnterWindow)

    const interactive = 'a, button, [role="button"], input, textarea, select, summary, label[for], [data-cursor-hover]'
    document.querySelectorAll(interactive).forEach((el) => {
      el.addEventListener('mouseenter', onEnterInteractive)
      el.addEventListener('mouseleave', onLeaveInteractive)
    })

    rafId = requestAnimationFrame(tick)

    return () => {
      cancelAnimationFrame(rafId)
      window.removeEventListener('mousemove', onMove)
      document.removeEventListener('mouseleave', onLeaveWindow)
      document.removeEventListener('mouseenter', onEnterWindow)
      document.querySelectorAll(interactive).forEach((el) => {
        el.removeEventListener('mouseenter', onEnterInteractive)
        el.removeEventListener('mouseleave', onLeaveInteractive)
      })
    }
  }, [enabled, hidden])

  if (!enabled) return null

  return (
    <>
      <div
        ref={dotRef}
        aria-hidden
        className="pointer-events-none fixed left-0 top-0 z-[9998] h-1.5 w-1.5 rounded-full bg-accent transition-opacity duration-200"
        style={{ opacity: hidden ? 0 : 1, willChange: 'transform' }}
      />
      <div
        ref={ringRef}
        aria-hidden
        className="pointer-events-none fixed left-0 top-0 z-[9997] rounded-full border border-accent/50 transition-[width,height,opacity,border-color] duration-200 ease-out-expo"
        style={{
          width: hovering ? 44 : 28,
          height: hovering ? 44 : 28,
          opacity: hidden ? 0 : hovering ? 0.9 : 0.55,
          borderColor: hovering ? 'var(--accent)' : 'var(--border-glow)',
          backdropFilter: 'invert(0.05)',
          willChange: 'transform, width, height',
        }}
      />
    </>
  )
}
