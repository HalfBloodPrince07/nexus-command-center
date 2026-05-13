'use client'
import React, { useState } from 'react'
import { motion } from 'framer-motion'
import { Send, Paperclip } from 'lucide-react'
import TextareaAutosize from 'react-textarea-autosize'
import { cn } from '@/lib/utils'

interface ChatInputProps {
  sendMessage: (message: string) => void
  isConnected: boolean
}

const ChatInput = ({ sendMessage, isConnected }: ChatInputProps) => {
  const [message, setMessage] = useState('')
  const [focused, setFocused] = useState(false)

  const handleSend = () => {
    if (message.trim() && isConnected) {
      sendMessage(message.trim())
      setMessage('')
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const canSend = message.trim().length > 0 && isConnected

  return (
    <div className="w-full px-8 pb-6">
      <motion.div
        animate={{
          boxShadow: focused
            ? '0 20px 60px rgba(99, 102, 241, 0.12), 0 0 0 1px rgba(99, 102, 241, 0.15)'
            : '0 8px 32px rgba(0, 0, 0, 0.06), 0 0 0 1px rgba(255, 255, 255, 0.9)',
        }}
        transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
        className="flex items-end gap-2 rounded-3xl glass px-4 py-3"
      >
        {/* Connection dot */}
        <div className="flex h-9 items-center pl-1">
          <span
            className={cn(
              'h-2 w-2 rounded-full transition-all duration-300',
              isConnected
                ? 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]'
                : 'bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.5)]'
            )}
            title={isConnected ? 'Connected' : 'Disconnected'}
          />
        </div>

        {/* Attach */}
        <button
          type="button"
          className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-xl text-ink-muted transition-colors hover:bg-surface-secondary hover:text-ink-secondary"
          aria-label="Attach file"
          disabled
        >
          <Paperclip size={17} strokeWidth={1.8} />
        </button>

        {/* Input */}
        <TextareaAutosize
          value={message}
          onChange={e => setMessage(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          maxRows={6}
          placeholder="Message NEXUS..."
          className="flex-1 resize-none bg-transparent px-1 py-2 text-sm leading-6 text-ink placeholder-ink-muted focus:outline-none"
        />

        {/* Send */}
        <motion.button
          onClick={handleSend}
          disabled={!canSend}
          className={cn(
            'relative flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-xl transition-all duration-300',
            canSend
              ? 'bg-gradient-primary text-white shadow-glow-accent hover:shadow-glow-accent-lg'
              : 'bg-surface-secondary text-ink-muted'
          )}
          whileHover={canSend ? { scale: 1.06 } : {}}
          whileTap={canSend ? { scale: 0.94 } : {}}
          aria-label="Send message"
        >
          <Send size={16} strokeWidth={2} />
        </motion.button>
      </motion.div>

      <p className="mt-2.5 text-center text-[11px] text-ink-muted">
        Press <kbd className="rounded-md bg-surface-secondary px-1.5 py-0.5 text-[10px] font-medium text-ink-secondary ring-1 ring-inset ring-border-subtle">Enter</kbd> to send ·{' '}
        <kbd className="rounded-md bg-surface-secondary px-1.5 py-0.5 text-[10px] font-medium text-ink-secondary ring-1 ring-inset ring-border-subtle">Shift + Enter</kbd> for newline
      </p>
    </div>
  )
}

export default ChatInput
