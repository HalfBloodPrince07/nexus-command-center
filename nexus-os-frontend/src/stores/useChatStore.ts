import { create } from 'zustand';
import { immer } from 'zustand/middleware/immer';
import { devtools, persist } from 'zustand/middleware';
import { ChatMessage } from '@/lib/types';
import { generateId } from '@/lib/utils';
import { API_URL } from '@/lib/constants';

type ChatState = {
    messages: ChatMessage[];
    streamingMessageId: string | null;
    isThinking: boolean;
    isConnected: boolean;
    conversationId: string | null;
    inputValue: string;
    historyLoaded: boolean;
};

type ChatActions = {
    addMessage: (message: ChatMessage) => void;
    updateStreamingMessage: (id: string, token: string) => void;
    finalizeStreamingMessage: (id: string) => void;
    createStreamingMessage: (agentId: string) => string;
    setThinking: (value: boolean) => void;
    setConnected: (value: boolean) => void;
    setConversationId: (id: string) => void;
    setInputValue: (value: string) => void;
    clearMessages: () => void;
    loadHistory: (conversationId: string) => Promise<void>;
    switchConversation: (id: string) => void;
};

export const useChatStore = create<ChatState & ChatActions>()(
    devtools(
        persist(
            immer((set, get) => ({
                messages: [],
                streamingMessageId: null,
                isThinking: false,
                isConnected: false,
                conversationId: null,
                inputValue: '',
                historyLoaded: false,

                addMessage: (message) => set((state) => {
                    state.messages.push(message);
                }),

                updateStreamingMessage: (id, token) => set((state) => {
                    const message = state.messages.find(m => m.id === id);
                    if (message && message.isStreaming) {
                        message.content += token;
                    }
                }),

                finalizeStreamingMessage: (id) => set((state) => {
                    const message = state.messages.find(m => m.id === id);
                    if (message) {
                        message.isStreaming = false;
                    }
                    if (state.streamingMessageId === id) {
                        state.streamingMessageId = null;
                    }
                }),

                createStreamingMessage: (agentId) => {
                    const newId = generateId();
                    const newMessage: ChatMessage = {
                        id: newId,
                        role: 'assistant',
                        content: '',
                        timestamp: new Date(),
                        agentId: agentId,
                        isStreaming: true,
                    };
                    set((state) => {
                        state.messages.push(newMessage);
                        state.streamingMessageId = newId;
                    });
                    return newId;
                },

                setThinking: (value) => set({ isThinking: value }),
                setConnected: (value) => set({ isConnected: value }),
                setConversationId: (id) => set({ conversationId: id }),
                setInputValue: (value) => set({ inputValue: value }),
                clearMessages: () => set({ messages: [], historyLoaded: false }),

                switchConversation: (id: string) => set({
                    conversationId: id,
                    messages: [],
                    historyLoaded: false,
                    streamingMessageId: null,
                    isThinking: false,
                }),

                loadHistory: async (conversationId: string) => {
                    if (!conversationId || get().historyLoaded) return;
                    try {
                        const res = await fetch(
                            `${API_URL}/api/chat/history/${encodeURIComponent(conversationId)}?limit=50`
                        );
                        if (!res.ok) return;
                        const data = await res.json();
                        const loaded: ChatMessage[] = (data.messages ?? []).map((m: {
                            role: string;
                            content: string;
                            agent_id?: string;
                            timestamp?: string;
                        }) => ({
                            id: generateId(),
                            role: m.role as 'user' | 'assistant',
                            content: m.content,
                            timestamp: m.timestamp ? new Date(m.timestamp) : new Date(),
                            agentId: m.agent_id ?? 'supervisor',
                            isStreaming: false,
                        }));
                        if (loaded.length > 0) {
                            set({ messages: loaded, historyLoaded: true });
                        } else {
                            set({ historyLoaded: true });
                        }
                    } catch {
                        // silently fail — history is nice-to-have
                    }
                },
            })),
            {
                name: 'nexus-chat-storage',
                partialize: (state) => ({ conversationId: state.conversationId }),
            }
        ),
        { name: 'ChatStore', enabled: process.env.NODE_ENV === 'development' }
    )
);
