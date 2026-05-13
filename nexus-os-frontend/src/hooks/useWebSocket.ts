import { useState, useRef, useEffect, useCallback } from 'react';
import { useChatStore } from '@/stores/useChatStore';
import { useAppStore } from '@/stores/useAppStore';
import { useResearchStore } from '@/stores/useResearchStore';
import { WS_URL, API_URL } from '@/lib/constants';
import { generateId } from '@/lib/utils';
import { ChatMessage, AgentStatus, SystemMetrics } from '@/lib/types';

// Module-level sender ref so non-hook contexts (e.g. NewResearch) can dispatch chat messages.
let _globalSend: ((content: string) => void) | null = null;
export function dispatchChatMessage(content: string): void {
  if (_globalSend) _globalSend(content);
  else console.warn("dispatchChatMessage: WebSocket not connected");
}

// Raw JSON sender — used by research pipeline to send typed messages.
let _globalSendRaw: ((data: object) => void) | null = null;
export function dispatchResearchStart(topic: string, jobId: string, slug: string): void {
  if (_globalSendRaw) _globalSendRaw({ type: "research_start", topic, job_id: jobId, slug });
  else console.warn("dispatchResearchStart: WebSocket not connected");
}

// Module-level reconnect: closes current WS so it auto-reconnects with the
// latest conversationId from useChatStore (used when switching conversations).
let _globalReconnect: (() => void) | null = null;
export function reconnectWebSocket(): void {
  if (_globalReconnect) _globalReconnect();
}

interface UseWebSocketReturn {
  connect: () => void;
  disconnect: () => void;
  sendMessage: (content: string, imageB64?: string, imageMime?: string) => void;
  sendPing: () => void;
  isConnected: boolean;
  isConnecting: boolean;
  error: string | null;
}

export function useWebSocket(): UseWebSocketReturn {
    const ws = useRef<WebSocket | null>(null);
    const [isConnecting, setIsConnecting] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const reconnectAttempts = useRef(0);
    const heartbeatInterval = useRef<NodeJS.Timeout | null>(null);
    const currentStreamingId = useRef<string | null>(null);

    const {
        isConnected,
        setConnected,
        setConversationId,
        setThinking,
        createStreamingMessage,
        updateStreamingMessage,
        finalizeStreamingMessage,
        addMessage,
        clearMessages,
    } = useChatStore();

    const { setSystemOnline, updateAgentStatus, setActiveAgents, setSystemMetrics, setActiveAgentId } = useAppStore();
    const researchStore = useResearchStore;

    const fetchInitialMetrics = useCallback(() => {
        fetch(`${API_URL}/api/system/metrics`)
            .then(res => res.json())
            .then((data: SystemMetrics) => {
                setSystemMetrics(data);
            })
            .catch(err => console.error("Failed to fetch initial metrics:", err));
    }, [setSystemMetrics]);

    const handleMessage = useCallback((data: string) => {
        try {
            const message = JSON.parse(data);
            switch (message.type) {
                case 'connected': {
                    const connectedId: string = message.conversation_id;
                    setConversationId(connectedId);
                    // Restore chat history if the store is empty (e.g. page refresh)
                    if (useChatStore.getState().messages.length === 0) {
                        useChatStore.getState().loadHistory(connectedId);
                    }
                    // Fetch agent statuses on connect — ALL start idle
                    fetch(`${API_URL}/api/agents/status`).then(res => res.json()).then(payload => {
                        if (payload && Array.isArray(payload.agents)) {
                            setActiveAgents(payload.agents.map((agent: any) => ({
                                id: agent.id,
                                name: agent.name,
                                tier: agent.tier,
                                status: 'idle',   // always start idle; WebSocket events drive state
                                description: agent.role,
                            })) as AgentStatus[]);
                        }
                    }).catch(err => console.error("Failed to fetch agents:", err));
                    // Fetch initial system metrics
                    fetchInitialMetrics();
                    break;
                }
                case 'thinking': {
                    const thinkingAgent = message.agent || message.agent_id || 'Nexus';
                    setThinking(true);
                    // Mark this agent as thinking, reset all others to idle
                    useAppStore.getState().setActiveAgents(
                        useAppStore.getState().activeAgents.map(a =>
                            (a.id === thinkingAgent || a.name === thinkingAgent || a.name.toLowerCase() === thinkingAgent.toLowerCase())
                                ? { ...a, status: 'thinking' }
                                : { ...a, status: 'idle' }
                        )
                    );
                    setActiveAgentId(thinkingAgent);
                    break;
                }
                case 'agent_switch': {
                    const switchTo = message.to || 'Nexus';
                    setActiveAgentId(switchTo);
                    updateAgentStatus(switchTo, 'thinking');
                    if (message.from) updateAgentStatus(message.from, 'idle');
                    // Mark completed agent in research pipeline
                    if (message.from) {
                        researchStore.getState().markAgentComplete(message.from);
                        researchStore.getState().addLog(message.from, 'Complete');
                    }
                    // Mark incoming agent as active
                    researchStore.getState().updatePipelineAgent(switchTo, { status: 'active', stage: 'idle', detail: '' });
                    break;
                }
                case 'stream_token':
                case 'token':
                    if (currentStreamingId.current === null) {
                        const streamingAgent = message.agent_id || message.agent || 'supervisor';
                        currentStreamingId.current = createStreamingMessage(streamingAgent);
                        setThinking(false);
                        // Mark this agent streaming, reset others
                        useAppStore.getState().setActiveAgents(
                            useAppStore.getState().activeAgents.map(a =>
                                (a.id === streamingAgent || a.name === streamingAgent || a.name.toLowerCase() === streamingAgent.toLowerCase())
                                    ? { ...a, status: 'streaming' }
                                    : (a.status === 'thinking' ? a : { ...a, status: 'idle' })
                            )
                        );
                    }
                    updateStreamingMessage(currentStreamingId.current, message.content);
                    break;
                case 'progress': {
                    const rStore = researchStore.getState();
                    if (message.agent) {
                        rStore.updatePipelineAgent(message.agent, {
                            detail: message.detail ?? '',
                            stage: message.stage ?? 'idle',
                            status: 'active',
                        });
                        // Add to activity log (throttle: only notable detail changes)
                        if (message.detail) rStore.addLog(message.agent, message.detail);

                        // Parse section progress from SectionDrafter
                        if (message.agent === 'SectionDrafter' && message.detail) {
                            const m = message.detail.match(/Drafting section (\d+).*?'(.+?)'/);
                            if (m) rStore.setSectionProgress({ currentTitle: m[2] });
                        }
                        // Parse claim progress from Verity
                        if (message.agent === 'Verity' && message.detail) {
                            const m = message.detail.match(/Checking claim (\d+)\/(\d+)/);
                            if (m) {
                                rStore.setClaimProgress({ total: parseInt(m[2], 10) });
                            }
                            // "Extracted N claims"
                            const ext = message.detail.match(/Extracted (\d+) claims/);
                            if (ext) rStore.setClaimProgress({ total: parseInt(ext[1], 10) });
                        }
                    }
                    break;
                }
                case 'section_complete': {
                    const rStore = researchStore.getState();
                    rStore.setSectionProgress({
                        done: (rStore.activeJob?.sectionProgress.done ?? 0) + 1,
                        currentTitle: message.section_title ?? '',
                    });
                    rStore.addLog('SectionDrafter', `Section ${message.section_number}: "${message.section_title}" (${message.word_count ?? 0} words)`);
                    break;
                }
                case 'result': {
                    // Capture metadata from agent result events
                    const rStore = researchStore.getState();
                    if (message.agent === 'OutlineArchitect' && message.data?.sections) {
                        rStore.setOutlineSections(message.data.sections.length);
                        rStore.markAgentComplete('OutlineArchitect', `${message.data.sections.length} sections`);
                    }
                    if (message.agent === 'SectionDrafter' && message.data) {
                        rStore.markAgentComplete('SectionDrafter', `${message.section_count ?? message.data.length} sections`);
                    }
                    if (message.agent === 'SynthesisDirector' && message.data) {
                        const wc = message.data.word_count;
                        rStore.markAgentComplete('SynthesisDirector', wc ? `${wc.toLocaleString()} words` : undefined);
                    }
                    if (message.agent === 'Verity') {
                        rStore.setClaimProgress({
                            verified: message.verified_count ?? 0,
                            hallucinated: message.hallucinated_count ?? 0,
                        });
                        rStore.markAgentComplete('Verity', `${message.verified_count ?? 0} verified`);
                    }
                    if (message.agent === 'Exporter' && message.output_paths) {
                        rStore.setOutputPaths(message.output_paths);
                        rStore.markAgentComplete('Exporter', message.formats_exported?.join(' · ') ?? 'done');
                    }
                    break;
                }
                case 'chunk':
                    // Synthesis / section streaming — track silently, don't flood chat
                    if (message.agent === 'SynthesisDirector' || message.agent === 'SectionDrafter') break;
                    if (currentStreamingId.current === null) {
                        currentStreamingId.current = createStreamingMessage(message.agent || 'Scribe');
                        setThinking(false);
                        updateAgentStatus(message.agent || 'Scribe', 'streaming');
                    }
                    updateStreamingMessage(currentStreamingId.current, message.content ?? '');
                    break;
                case 'stream_end':
                case 'done':
                    if (message.slug) {
                        // Research pipeline completed
                        researchStore.getState().completeJob(message.metadata ?? { slug: message.slug });
                    }
                    if (currentStreamingId.current) {
                        finalizeStreamingMessage(currentStreamingId.current);
                        currentStreamingId.current = null;
                    }
                    setThinking(false);
                    // Reset ALL agents to idle
                    useAppStore.getState().setActiveAgents(
                        useAppStore.getState().activeAgents.map(a => ({ ...a, status: 'idle' }))
                    );
                    setTimeout(() => setActiveAgentId(''), 1200);
                    break;
                case 'system_metrics':
                    setSystemMetrics(message as SystemMetrics);
                    break;
                case 'history_cleared':
                    clearMessages();
                    break;
                case 'pong':
                    break;
                case 'error':
                    if (researchStore.getState().activeJob?.status === 'running') {
                        researchStore.getState().failJob(message.detail ?? message.message ?? 'Unknown error');
                    }
                    // Reset all agent statuses on error
                    useAppStore.getState().setActiveAgents(
                        useAppStore.getState().activeAgents.map(a => ({ ...a, status: 'idle' }))
                    );
                    setThinking(false);
                    if (currentStreamingId.current) {
                        finalizeStreamingMessage(currentStreamingId.current);
                        currentStreamingId.current = null;
                    }
                    console.error("WebSocket error message:", message.message);
                    const errorMsg: ChatMessage = {
                        id: generateId(),
                        role: 'assistant',
                        content: `An error occurred: ${message.message ?? message.detail}`,
                        timestamp: new Date(),
                        agentId: 'system',
                    };
                    addMessage(errorMsg);
                    break;
            }
        } catch (e) {
            console.error("Failed to handle incoming WebSocket message:", e);
        }
    }, [setConversationId, setThinking, createStreamingMessage, updateStreamingMessage, finalizeStreamingMessage, clearMessages, addMessage, updateAgentStatus, setActiveAgents, setSystemMetrics, fetchInitialMetrics]);

    const connect = useCallback(() => {
        if (ws.current || isConnecting) return;

        // Expose reconnect trigger for cross-component use (e.g. switching conversations)
        _globalReconnect = () => {
            reconnectAttempts.current = 0;
            if (ws.current) {
                ws.current.close();
            } else {
                connect();
            }
        };

        setIsConnecting(true);
        setError(null);
        console.log("Attempting to connect to WebSocket...");

        const storedId = useChatStore.getState().conversationId;
        const wsUrl = storedId ? `${WS_URL}?session_id=${encodeURIComponent(storedId)}` : WS_URL;
        const socket = new WebSocket(wsUrl);

        socket.onopen = () => {
            console.log("WebSocket connected.");
            ws.current = socket;
            setIsConnecting(false);
            setConnected(true);
            setSystemOnline(true);
            reconnectAttempts.current = 0;
            _globalSendRaw = (data: object) => {
                if (socket.readyState === WebSocket.OPEN) socket.send(JSON.stringify(data));
            };

            // Start heartbeat
            heartbeatInterval.current = setInterval(() => {
                sendPing();
            }, 30000);
        };

        socket.onmessage = (event) => {
            handleMessage(event.data);
        };

        socket.onclose = () => {
            console.log("WebSocket disconnected.");
            ws.current = null;
            _globalSendRaw = null;
            setIsConnecting(false);
            setConnected(false);
            setSystemOnline(false);
            if (heartbeatInterval.current) {
                clearInterval(heartbeatInterval.current);
            }

            // Reconnect logic
            if (reconnectAttempts.current < 10) {
                const delay = Math.min(30000, (2 ** reconnectAttempts.current) * 1000);
                console.log(`WebSocket closed. Reconnecting in ${delay / 1000}s...`);
                setTimeout(connect, delay);
                reconnectAttempts.current++;
            } else {
                console.error("WebSocket failed to reconnect after 10 attempts.");
                setError("Failed to connect to the server.");
            }
        };

        socket.onerror = (event) => {
            console.error("WebSocket error:", event);
            setError("A connection error occurred.");
            socket.close();
        };

    }, [isConnecting, setConnected, setSystemOnline, handleMessage]);

    const disconnect = () => {
        if (ws.current) {
            reconnectAttempts.current = 10;
            ws.current.close();
            console.log("WebSocket manually disconnected.");
        }
    };

    const sendMessage = (content: string, imageB64?: string, imageMime?: string) => {
        _globalSend = (c: string) => sendMessage(c);
        if (ws.current && ws.current.readyState === WebSocket.OPEN) {
            const message: ChatMessage = {
                id: generateId(),
                role: 'user',
                content,
                timestamp: new Date(),
                attachedImageUrl: imageB64 && imageMime ? `data:${imageMime};base64,${imageB64}` : undefined,
            };
            addMessage(message);
            ws.current.send(
                JSON.stringify(
                    imageB64
                        ? {
                              type: "image_query",
                              content,
                              image_b64: imageB64,
                              image_mime: imageMime || "image/jpeg",
                          }
                        : { type: "message", content }
                )
            );
        } else {
            console.error("Cannot send message: WebSocket is not connected.");
        }
    };

    const sendPing = () => {
        if (ws.current && ws.current.readyState === WebSocket.OPEN) {
            ws.current.send(JSON.stringify({ type: 'ping' }));
        }
    };

    useEffect(() => {
        connect();
        return () => {
            disconnect();
        };
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    return { connect, disconnect, sendMessage, sendPing, isConnected, isConnecting, error };
}
