export type ChatMessage = {
    id: string;
    role: 'user' | 'assistant';
    content: string;
    timestamp: Date;
    agentId?: string;
    isStreaming?: boolean;
    attachedImageUrl?: string;
    agentName?: string;
};

export type AgentStatus = {
    id: string;
    name: string;
    tier: number;
    status: 'idle' | 'thinking' | 'streaming' | 'error';
    description: string;
};

export type TabId = "chat" | "dashboard" | "research" | "journal" | "files" | "memory" | "history" | "insights" | "settings";

export type SystemMetrics = {
    cpu_percent: number;
    ram_percent: number;
    ram_used_gb: number;
    ram_total_gb: number;
    gpu_percent: number | null;
    gpu_temp_c: number | null;
    gpu_vram_percent: number | null;
    gpu_name: string | null;
};

export type WSMessage = {
    type: string;
    content?: string;
    agentId?: string;
    conversationId?: string;
    timestamp?: number;
};
