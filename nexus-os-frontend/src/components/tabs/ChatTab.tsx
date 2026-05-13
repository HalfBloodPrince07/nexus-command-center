"use client";

import ChatWindow from "@/components/chat/ChatWindow";

interface ChatTabProps {
  onSendMessage: (content: string, imageB64?: string, imageMime?: string) => void;
  isConnected: boolean;
  activeAgentId: string;
}

export default function ChatTab({ onSendMessage, isConnected, activeAgentId }: ChatTabProps) {
  return <ChatWindow onSendMessage={onSendMessage} isConnected={isConnected} activeAgentId={activeAgentId} />;
}
