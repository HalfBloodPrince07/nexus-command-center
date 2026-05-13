'use client'

import { useEffect, useRef } from 'react'

export function useAutoScroll(dependency: React.DependencyList) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (ref.current) {
      ref.current.scrollTo({ top: ref.current.scrollHeight, behavior: 'smooth' })
    }
  }, [dependency])
  return ref
}
