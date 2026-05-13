'use client'

import { useEffect, useState, useCallback } from 'react'
import { MessageSquare, Search, ArrowRight, Clock, RefreshCw, Plus } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { API_URL } from '@/lib/constants'
import { useChatStore } from '@/stores/useChatStore'
import { useAppStore } from '@/stores/useAppStore'
import { reconnectWebSocket } from '@/hooks/useWebSocket'
import { cn } from '@/lib/utils'
import { generateId } from '@/lib/utils'

type ConversationSummary = {
    conversation_id: string
    title?: string | null
    message_count: number
    created_at: string
    updated_at: string
}

type HistoryMessage = {
    role: 'user' | 'assistant'
    content: string
    agent_id?: string
    timestamp?: string
}

type SearchResult = {
    conversation_id: string
    conversation_title: string
    message_id: string
    snippet: string
    score: number
    timestamp: string
    match_type: string
    role: 'assistant' | 'user'
}

type ChatSearchResponse = {
    results: SearchResult[]
    total: number
    query: string
}

function formatRelativeTime(iso: string): string {
    const diff = Date.now() - new Date(iso).getTime()
    const mins = Math.floor(diff / 60000)
    if (mins < 1) return 'just now'
    if (mins < 60) return `${mins}m ago`
    const hrs = Math.floor(mins / 60)
    if (hrs < 24) return `${hrs}h ago`
    const days = Math.floor(hrs / 24)
    if (days < 7) return `${days}d ago`
    return new Date(iso).toLocaleDateString()
}

function shortId(id: string | undefined | null): string {
    if (!id) return '????????'
    return id.slice(0, 8)
}

export default function HistoryTab() {
    const [conversations, setConversations] = useState<ConversationSummary[]>([])
    const [filtered, setFiltered] = useState<ConversationSummary[]>([])
    const [search, setSearch] = useState('')
    const [selectedId, setSelectedId] = useState<string | null>(null)
    const [messages, setMessages] = useState<HistoryMessage[]>([])
    const [loadingList, setLoadingList] = useState(false)
    const [loadingMessages, setLoadingMessages] = useState(false)

    // E2: Bulk actions state
    const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
    const [isSelectable, setIsSelectable] = useState(false)
    const [showBulkActions, setShowBulkActions] = useState(false)

    const currentConversationId = useChatStore(s => s.conversationId)
    const { switchConversation } = useChatStore()
    const { setActiveTab } = useAppStore()

    const loadConversations = useCallback(async () => {
        setLoadingList(true)
        try {
            const res = await fetch(`${API_URL}/api/chat/conversations?limit=100`)
            if (!res.ok) return
            const data = await res.json()
            const valid = (data.conversations ?? []).filter((c: ConversationSummary) => !!c.conversation_id)
            setConversations(valid)
            setFiltered(valid)
        } catch (e) {
            console.error('Failed to load conversations:', e)
        } finally {
            setLoadingList(false)
        }
    }, [])

    useEffect(() => { loadConversations() }, [loadConversations])

    useEffect(() => {
        if (!search.trim()) {
            setFiltered(conversations)
        } else {
            const q = search.toLowerCase()
            setFiltered(conversations.filter(c => c.conversation_id.toLowerCase().includes(q)))
        }
    }, [search, conversations])

    const selectConversation = async (id: string) => {
        setSelectedId(id)
        setLoadingMessages(true)
        try {
            const res = await fetch(`${API_URL}/api/chat/history/${encodeURIComponent(id)}?limit=50`)
            if (!res.ok) return
            const data = await res.json()
            setMessages(data.messages ?? [])
        } catch (e) {
            console.error('Failed to load messages:', e)
        } finally {
            setLoadingMessages(false)
        }
    }

    const continueInChat = (id: string) => {
        switchConversation(id)
        setActiveTab('chat')
        reconnectWebSocket()
    }

    const startNewChat = () => {
        switchConversation(generateId())
        setActiveTab('chat')
        reconnectWebSocket()
    }

    return (
        <div className="flex h-full w-full overflow-hidden">
            {/* Left: conversation list */}
            <div className="flex w-72 flex-shrink-0 flex-col border-r border-black/[0.06] bg-white/40">
                <div className="flex items-center justify-between border-b border-black/[0.06] px-4 py-3">
                    <span className="text-sm font-semibold text-ink">Conversations</span>
                    <div className="flex items-center gap-1">
                        <button
                            onClick={startNewChat}
                            className="flex items-center gap-1 rounded-lg px-2 py-1 text-xs font-medium text-ink-muted transition-colors hover:bg-black/[0.05] hover:text-ink"
                            title="New chat"
                        >
                            <Plus size={13} />
                            New
                        </button>
                        <button
                            onClick={loadConversations}
                            className={cn('rounded-lg p-1.5 text-ink-muted transition-colors hover:bg-black/[0.05] hover:text-ink', loadingList && 'animate-spin')}
                            title="Refresh"
                        >
                            <RefreshCw size={15} />
                        </button>
                    </div>
                </div>

                <div className="px-3 py-2">
                    <div className="flex items-center gap-2 rounded-lg bg-black/[0.04] px-3 py-1.5">
                        <Search size={13} className="text-ink-muted flex-shrink-0" />
                        <input
                            value={search}
                            onChange={e => setSearch(e.target.value)}
                            placeholder="Search conversations..."
                            className="flex-1 bg-transparent text-xs text-ink outline-none placeholder:text-ink-muted"
                        />
                    </div>
                </div>

                <div className="flex-1 overflow-y-auto px-2 pb-2">
                    {loadingList ? (
                        <div className="flex items-center justify-center py-12 text-xs text-ink-muted">Loading...</div>
                    ) : filtered.length === 0 ? (
                        <div className="flex flex-col items-center justify-center gap-2 py-12 text-center">
                            <MessageSquare size={24} className="text-ink-muted opacity-40" />
                            <span className="text-xs text-ink-muted">No conversations yet</span>
                        </div>
                    ) : (
                        <AnimatePresence>
                            {filtered.map(c => {
                                const isActive = c.conversation_id === currentConversationId
                                const isSelected = c.conversation_id === selectedId
                                return (
                                    <motion.button
                                        key={c.conversation_id}
                                        initial={{ opacity: 0, x: -6 }}
                                        animate={{ opacity: 1, x: 0 }}
                                        onClick={() => selectConversation(c.conversation_id)}
                                        className={cn(
                                            'group relative w-full rounded-xl p-3 text-left transition-all mb-1',
                                            isSelected
                                                ? 'bg-gradient-primary text-white shadow-glow-accent'
                                                : 'hover:bg-black/[0.04] text-ink'
                                        )}
                                    >
                                        <div className="flex items-start justify-between gap-2">
                                            <div className="min-w-0">
                                                <div className="flex items-center gap-1.5 min-w-0">
                                                    <span className={cn('text-xs font-medium truncate', isSelected ? 'text-white' : 'text-ink')}>
                                                        {c.title || shortId(c.conversation_id)}
                                                    </span>
                                                    {isActive && (
                                                        <span className="flex-shrink-0 rounded-full bg-emerald-500 px-1.5 py-0.5 text-[9px] font-semibold text-white leading-none">
                                                            active
                                                        </span>
                                                    )}
                                                </div>
                                                <div className={cn('mt-0.5 text-[11px]', isSelected ? 'text-white/70' : 'text-ink-muted')}>
                                                    {c.message_count} message{c.message_count !== 1 ? 's' : ''}
                                                </div>
                                            </div>
                                            <div className={cn('flex items-center gap-1 text-[10px] flex-shrink-0', isSelected ? 'text-white/60' : 'text-ink-muted')}>
                                                <Clock size={10} />
                                                {formatRelativeTime(c.updated_at)}
                                            </div>
                                        </div>
                                    </motion.button>
                                )
                            })}
                        </AnimatePresence>
                    )}
                </div>
            </div>

            {/* Right: message viewer */}
            <div className="flex flex-1 flex-col overflow-hidden">
                {selectedId ? (
                    <>
                        <div className="flex items-center justify-between border-b border-black/[0.06] bg-white/30 px-5 py-3">
                            <div className="min-w-0 mr-4">
                                {(() => {
                                    const sel = conversations.find(c => c.conversation_id === selectedId)
                                    return sel?.title
                                        ? <p className="text-sm font-semibold text-ink truncate">{sel.title}</p>
                                        : <p className="font-mono text-sm font-semibold text-ink">{shortId(selectedId)}</p>
                                })()}
                                <p className="mt-0.5 font-mono text-[10px] text-ink-muted truncate">{selectedId}</p>
                            </div>
                            <button
                                onClick={() => continueInChat(selectedId)}
                                className="flex items-center gap-1.5 rounded-xl bg-gradient-primary px-3.5 py-1.5 text-xs font-semibold text-white shadow-glow-accent transition-opacity hover:opacity-90"
                            >
                                Continue in Chat
                                <ArrowRight size={13} />
                            </button>
                        </div>

                        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
                            {loadingMessages ? (
                                <div className="flex items-center justify-center py-16 text-sm text-ink-muted">Loading messages...</div>
                            ) : messages.length === 0 ? (
                                <div className="flex items-center justify-center py-16 text-sm text-ink-muted">No messages found</div>
                            ) : (
                                messages.map((msg, i) => (
                                    <div
                                        key={i}
                                        className={cn('flex', msg.role === 'user' ? 'justify-end' : 'justify-start')}
                                    >
                                        <div className={cn(
                                            'max-w-[75%] rounded-2xl px-4 py-2.5 text-sm',
                                            msg.role === 'user'
                                                ? 'bg-gradient-primary text-white'
                                                : 'glass text-ink'
                                        )}>
                                            {msg.agent_id && msg.role === 'assistant' && (
                                                <div className="mb-1 text-[10px] font-semibold uppercase tracking-wider opacity-50">
                                                    {msg.agent_id}
                                                </div>
                                            )}
                                            <p className="whitespace-pre-wrap leading-relaxed">{msg.content}</p>
                                            {msg.timestamp && (
                                                <div className={cn('mt-1 text-[10px] opacity-50', msg.role === 'user' ? 'text-right' : '')}>
                                                    {formatRelativeTime(msg.timestamp)}
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                ))
                            )}
                        </div>
                    </>
                ) : (
                    <div className="flex flex-1 flex-col items-center justify-center gap-3 text-center">
                        <MessageSquare size={40} className="text-ink-muted opacity-30" />
                        <div>
                            <p className="text-sm font-medium text-ink">Select a conversation</p>
                            <p className="mt-1 text-xs text-ink-muted">Choose from the list on the left to view messages</p>
                        </div>
                    </div>
                )}
            </div>
        </div>
    )
}
