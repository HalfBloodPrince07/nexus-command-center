'use client'
import { motion } from 'framer-motion'
import { ChatMessage } from '@/lib/types'
import StatusBadge from '../ui/StatusBadge'
import { cn } from '@/lib/utils'

interface MessageBubbleProps {
  message: ChatMessage
}

const MessageBubble = ({ message }: MessageBubbleProps) => {
  const { id, role, content, timestamp, isStreaming, attachedImageUrl, agentName } = message
  const isUser = role === 'user'

  return (
    <motion.div
      key={id}
      initial={{ opacity: 0, y: 10, x: isUser ? 16 : -16 }}
      animate={{ opacity: 1, y: 0, x: 0 }}
      transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
      className={cn('flex w-full flex-col', isUser ? 'items-end' : 'items-start')}
    >
      {/* Label */}
      <div
        className={cn(
          'mb-1.5 flex items-center gap-2 px-1 text-[11px] font-medium uppercase tracking-wider text-ink-muted',
          isUser ? 'flex-row-reverse' : 'flex-row'
        )}
      >
        <span>{isUser ? 'You' : agentName || 'NEXUS'}</span>
        {!isUser && isStreaming && <StatusBadge status="streaming" size="sm" label="" />}
      </div>

      {/* Bubble */}
      <div
        className={cn(
          'w-auto max-w-[78%] rounded-2xl px-5 py-3.5 transition-shadow duration-300',
          isUser
            ? 'bg-gradient-primary text-white shadow-glow-accent rounded-tr-lg'
            : 'glass-elevated text-ink shadow-glass rounded-tl-lg'
        )}
      >
        {attachedImageUrl && (
          <img
            src={attachedImageUrl}
            alt="Attached image"
            className="mb-2 h-24 w-32 rounded-lg border border-glass-border object-cover"
          />
        )}
        <p className={cn('whitespace-pre-wrap text-[14px] leading-relaxed', isStreaming && 'streaming-cursor')}>
          {content}
        </p>
      </div>

      {/* Timestamp */}
      <div className={cn('mt-1.5 px-1 text-[11px] text-ink-muted', isUser ? 'text-right' : 'text-left')}>
        {new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
      </div>
    </motion.div>
  )
}

export default MessageBubble
