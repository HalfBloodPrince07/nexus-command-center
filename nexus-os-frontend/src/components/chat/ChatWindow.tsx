"use client";
import { useCallback, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { useDropzone } from "react-dropzone";
import { SquarePen, Sparkles, X } from "lucide-react";
import { useChatStore } from "@/stores/useChatStore";
import { useAutoScroll } from "@/hooks/useAutoScroll";
import { useAppStore } from "@/stores/useAppStore";
import { reconnectWebSocket } from "@/hooks/useWebSocket";
import { generateId } from "@/lib/utils";
import MessageBubble from "./MessageBubble";
import ChatInput from "./ChatInput";
import AgentActivityPanel from "./AgentActivityPanel";
import { AgentThinkingOrbDynamic } from "../three/AgentThinkingOrb";

interface ChatWindowProps {
  onSendMessage: (content: string, imageB64?: string, imageMime?: string) => void;
  isConnected: boolean;
  activeAgentId?: string; // kept for backward compat; panel now reads from store
}

type PendingImage = {
  url: string;
  b64: string;
  mime: string;
};

const prompts = [
  "Summarize my recent research",
  "Draft a plan for today",
  "What did we discuss last time?",
  "Find patterns in my notes",
];

const ChatWindow = ({ onSendMessage, isConnected, activeAgentId = "Nexus" }: ChatWindowProps) => {
  const { messages, isThinking, streamingMessageId, switchConversation } = useChatStore();
  const { dashboardPanelOpen } = useAppStore();

  const handleNewChat = () => {
    switchConversation(generateId());
    reconnectWebSocket();
  };
  const [pendingImage, setPendingImage] = useState<PendingImage | null>(null);
  const scrollRef = useAutoScroll(messages);

  const handleImageDrop = useCallback((acceptedFiles: File[]) => {
    const imageFile = acceptedFiles[0];
    if (!imageFile) return;

    const reader = new FileReader();
    reader.onload = () => {
      const result = String(reader.result ?? "");
      const base64 = result.includes(",") ? result.split(",")[1] : "";
      setPendingImage({
        url: result,
        b64: base64,
        mime: imageFile.type || "image/jpeg",
      });
    };
    reader.readAsDataURL(imageFile);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    noClick: true,
    accept: { "image/*": [] },
    onDrop: handleImageDrop,
  });

  const isStreaming = streamingMessageId !== null;
  const showOrb = isThinking || isStreaming;

  return (
    <div
      {...getRootProps()}
      className="relative flex h-full flex-1"
    >
      <input {...getInputProps()} />

      <AnimatePresence>
        {isDragActive && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="pointer-events-none absolute inset-0 z-30 flex items-center justify-center bg-blue-500/15 backdrop-blur-sm"
          >
            <div className="rounded-3xl border border-blue-400/30 bg-blue-500/15 px-6 py-4 text-sm font-medium text-blue-100 shadow-lg">
              Drop image here
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="flex flex-1 flex-col">
        <div className="flex items-center justify-between px-8 py-5">
          <div>
            <h1 className="font-display text-xl font-semibold tracking-tight text-ink">
              Conversation
            </h1>
            <p className="mt-0.5 text-xs text-ink-muted">
              Chat with your local intelligence layer
            </p>
          </div>
          <button
            onClick={handleNewChat}
            className="flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-xs font-medium text-ink-muted ring-1 ring-inset ring-black/[0.07] transition-all hover:bg-black/[0.04] hover:text-ink"
            title="Start a new conversation"
          >
            <SquarePen size={13} />
            New Chat
          </button>
        </div>

        <div ref={scrollRef} className="flex-1 overflow-y-auto px-8 pb-4">
          <div className="flex min-h-full flex-col justify-end">
          {messages.length === 0 ? (
            <div className="flex h-full flex-col items-center justify-center text-center">
              <motion.div
                initial={{ opacity: 0, y: 12, scale: 0.9 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
                className="mb-6 flex h-20 w-20 items-center justify-center rounded-3xl bg-gradient-subtle ring-1 ring-inset ring-border-subtle shadow-glass-lg"
              >
                <Sparkles size={36} strokeWidth={1.5} className="text-accent" />
              </motion.div>

              <motion.h2
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
                className="font-display text-3xl font-semibold tracking-tight"
              >
                <span className="text-gradient">Start a conversation</span>
              </motion.h2>

              <motion.p
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, delay: 0.2, ease: [0.16, 1, 0.3, 1] }}
                className="mt-3 max-w-md text-sm text-ink-secondary"
              >
                Ask NEXUS anything - it has access to your agents, memory, and local models.
              </motion.p>

              <motion.div
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, delay: 0.35, ease: [0.16, 1, 0.3, 1] }}
                className="mt-8 flex flex-wrap justify-center gap-2.5"
              >
                {prompts.map((prompt) => (
                  <button
                    key={prompt}
                    onClick={() => isConnected && onSendMessage(prompt)}
                    className="rounded-2xl glass px-4 py-2.5 text-xs font-medium text-ink-secondary transition-all duration-300 hover:-translate-y-0.5 hover:bg-white/90 hover:text-ink hover:shadow-glass"
                  >
                    {prompt}
                  </button>
                ))}
              </motion.div>
            </div>
          ) : (
            <div className="space-y-6">
              {messages.map((msg) => <MessageBubble key={msg.id} message={msg} />)}
            </div>
          )}
          </div>
        </div>

        <AnimatePresence>
          {pendingImage && (
            <ImagePreviewBar
              image={{ url: pendingImage.url, mime: pendingImage.mime }}
              onSend={(question) => {
                onSendMessage(question, pendingImage.b64, pendingImage.mime);
                setPendingImage(null);
              }}
              onClear={() => setPendingImage(null)}
            />
          )}
        </AnimatePresence>

        <div className="flex h-20 items-center justify-center">
          <AnimatePresence>
            {showOrb && (
              <motion.div
                initial={{ opacity: 0, scale: 0.5 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.5 }}
                transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
              >
                <AgentThinkingOrbDynamic status={isThinking ? "thinking" : "streaming"} />
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        <ChatInput sendMessage={onSendMessage} isConnected={isConnected} />
      </div>

      {dashboardPanelOpen && <AgentActivityPanel />}
    </div>
  );
};

function ImagePreviewBar({
  image,
  onSend,
  onClear,
}: {
  image: { url: string; mime: string };
  onSend: (question: string) => void;
  onClear: () => void;
}) {
  const [question, setQuestion] = useState("Describe this image.");

  return (
    <motion.div
      initial={{ height: 0, opacity: 0 }}
      animate={{ height: "auto", opacity: 1 }}
      exit={{ height: 0, opacity: 0 }}
      className="flex items-center gap-3 border-t border-glass-border bg-surface-1/50 px-4 py-3"
    >
      <img
        src={image.url}
        alt="Preview"
        className="h-14 w-14 flex-shrink-0 rounded-lg border border-glass-border object-cover"
      />
      <input
        value={question}
        onChange={(event) => setQuestion(event.target.value)}
        onKeyDown={(event) => event.key === "Enter" && onSend(question)}
        className="flex-1 bg-transparent text-sm text-text-primary outline-none placeholder:text-text-muted"
      />
      <button
        onClick={() => onSend(question)}
        className="rounded-lg bg-accent-primary/20 px-3 py-1.5 text-sm text-accent-primary transition-colors hover:bg-accent-primary/30"
      >
        Send
      </button>
      <button
        onClick={onClear}
        className="p-1.5 text-text-muted transition-colors hover:text-text-primary"
        aria-label="Clear image"
      >
        <X className="h-4 w-4" />
      </button>
    </motion.div>
  );
}

export default ChatWindow;
