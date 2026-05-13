import { TabId } from './types';

export const WS_URL = "ws://localhost:8000/ws/chat";
export const API_URL = "http://localhost:8000";

export const TABS: { id: TabId; label: string; icon: string; available: boolean }[] = [
    { id: "chat", label: "Chat", icon: "MessageCircle", available: true },
    { id: "dashboard", label: "Dashboard", icon: "LayoutGrid", available: true },
    { id: "research", label: "Research", icon: "FlaskConical", available: true },
    { id: "journal", label: "Journal", icon: "Book", available: true },
    { id: "files", label: "Files", icon: "File", available: true },
    { id: "memory", label: "Memory", icon: "BrainCircuit", available: true },
    { id: "history", label: "History", icon: "History", available: true },
    { id: "insights", label: "Insights", icon: "Sparkles", available: true },
    { id: "settings", label: "Settings", icon: "Settings", available: true },
];
