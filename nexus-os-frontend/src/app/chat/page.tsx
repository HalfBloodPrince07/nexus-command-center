'use client'
import dynamic from 'next/dynamic'

const AppShell = dynamic(() => import("@/components/layout/AppShell"), { ssr: false })

export default function ChatPage() {
  return <AppShell />
}
