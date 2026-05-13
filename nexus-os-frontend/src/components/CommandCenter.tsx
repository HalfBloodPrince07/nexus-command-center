"use client";

import { AnimatePresence, motion } from "framer-motion";
import { LayoutDashboard, BookOpen, Zap } from "lucide-react";
import { useAppStore } from "@/stores/useAppStore";
import { useWebSocket } from "@/hooks/useWebSocket";
import ChatTab from "@/components/ChatTab";
import FilesTab from "@/components/tabs/FilesTab";
import ResearchTab from "@/components/tabs/ResearchTab";
import SettingsTab from "@/components/tabs/SettingsTab";
import MemoryTab from "@/components/tabs/MemoryTab";
import HistoryTab from "@/components/tabs/HistoryTab";
import JournalTab from "@/components/tabs/JournalTab";
import DashboardTab from "@/components/tabs/DashboardTab";
import InsightsTab from "@/components/tabs/InsightsTab";
import ComingSoon from "@/components/ui/ComingSoon";

export default function CommandCenter() {
  const { activeTab, activeAgentId } = useAppStore();
  const { sendMessage, isConnected } = useWebSocket();

  const renderContent = () => {
    switch (activeTab) {
      case "chat":
        return <ChatTab onSendMessage={sendMessage} isConnected={isConnected} activeAgentId={activeAgentId} />;
      case "dashboard":
        return <DashboardTab />;
      case "research":
        return <ResearchTab />;
      case "journal":
        return <JournalTab />;
      case "files":
        return <FilesTab />;
      case "memory":
        return <MemoryTab />;
      case "history":
        return <HistoryTab />;
      case "insights":
        return <InsightsTab />;
      case "settings":
        return <SettingsTab />;
      default:
        return <ChatTab onSendMessage={sendMessage} isConnected={isConnected} activeAgentId={activeAgentId} />;
    }
  };

  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={activeTab}
        initial={{ opacity: 0, y: 8, filter: "blur(6px)" }}
        animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
        exit={{ opacity: 0, y: -8, filter: "blur(6px)" }}
        transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
        className="h-full w-full"
      >
        {renderContent()}
      </motion.div>
    </AnimatePresence>
  );
}
