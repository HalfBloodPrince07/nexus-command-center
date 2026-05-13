import { create } from 'zustand';
import { devtools, persist } from 'zustand/middleware';
import { AgentStatus, SystemMetrics, TabId } from '@/lib/types';

type AppState = {
    activeTab: TabId;
    sidebarCollapsed: boolean;
    dashboardPanelOpen: boolean;
    activeAgents: AgentStatus[];
    activeAgentId: string;
    systemOnline: boolean;
    systemMetrics: SystemMetrics | null;
    isDarkMode: boolean;
};

type AppActions = {
    setActiveTab: (tab: TabId) => void;
    toggleSidebar: () => void;
    toggleDashboardPanel: () => void;
    updateAgentStatus: (agentId: string, status: AgentStatus['status']) => void;
    setActiveAgents: (agents: AgentStatus[]) => void;
    setActiveAgentId: (agentId: string) => void;
    setSystemOnline: (value: boolean) => void;
    setSystemMetrics: (metrics: SystemMetrics) => void;
    toggleDarkMode: () => void;
};

export const useAppStore = create<AppState & AppActions>()(
    devtools(
        persist(
            (set) => ({
                activeTab: 'chat',
                sidebarCollapsed: false,
                dashboardPanelOpen: true,
                activeAgents: [
                    {
                        id: "supervisor",
                        name: "Supervisor",
                        tier: 1,
                        status: "idle",
                        description: "Routes messages..."
                    }
                ],
                activeAgentId: "Nexus",
                systemOnline: false,
                systemMetrics: null,
                isDarkMode: false,

                setActiveTab: (tab) => set({ activeTab: tab }),
                toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
                toggleDashboardPanel: () => set((state) => ({ dashboardPanelOpen: !state.dashboardPanelOpen })),
                updateAgentStatus: (agentId, status) => set((state) => ({
                    activeAgents: state.activeAgents.map(agent =>
                        (agent.id === agentId || agent.name === agentId || agent.name.toLowerCase() === agentId.toLowerCase())
                            ? { ...agent, status }
                            : agent
                    )
                })),
                setActiveAgents: (agents) => set({ activeAgents: agents }),
                setActiveAgentId: (activeAgentId) => set({ activeAgentId }),
                setSystemOnline: (value) => set({ systemOnline: value }),
                setSystemMetrics: (metrics) => set({ systemMetrics: metrics }),
                toggleDarkMode: () => set((state) => ({ isDarkMode: !state.isDarkMode })),
            }),
            {
                name: 'nexus-app-storage',
                partialize: (state) => ({ isDarkMode: state.isDarkMode }),
            }
        ),
        { name: 'AppStore', enabled: process.env.NODE_ENV === 'development' }
    )
);
