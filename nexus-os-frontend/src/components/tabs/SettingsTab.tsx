"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { 
  Cpu, 
  Bot, 
  Bell, 
  Database, 
  Moon, 
  Sun, 
  CheckCircle2, 
  RefreshCw 
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAppStore } from "@/stores/useAppStore";
import GlassCard from "@/components/ui/GlassCard";
import ModelsSubtab from "@/components/settings/ModelsSubtab";
import toast from 'react-hot-toast';

type Subtab = "models" | "agents" | "notifications" | "data-export";

interface SubtabConfig {
  id: Subtab;
  label: string;
  icon: React.ComponentType<any>;
  description: string;
}

const SUBTABS: SubtabConfig[] = [
  {
    id: "models",
    label: "Models",
    icon: Cpu,
    description: "Configure AI models and roles"
  },
  {
    id: "agents", 
    label: "Agents",
    icon: Bot,
    description: "Manage agent personalities and settings"
  },
  {
    id: "notifications",
    label: "Notifications",
    icon: Bell,
    description: "Configure alerts and daily briefings"
  },
  {
    id: "data-export",
    label: "Data & Export",
    icon: Database,
    description: "Backups, exports, and data management"
  }
];

const ComingSoonCard = ({ title }: { title: string }) => (
  <GlassCard variant="bordered" padding="md" className="flex items-center justify-center min-h-[200px]">
    <div className="text-center">
      <div className="text-2xl mb-2">🔨</div>
      <h3 className="text-lg font-semibold text-ink">{title} Settings</h3>
      <p className="text-sm text-ink-muted mt-2">This section is currently under construction</p>
    </div>
  </GlassCard>
);

export default function SettingsTab() {
  const [activeSubtab, setActiveSubtab] = useState<Subtab>("models");
  const { isDarkMode, toggleDarkMode } = useAppStore();

  const renderSubtab = () => {
    switch (activeSubtab) {
      case "models":
        return <ModelsSubtab />;
      case "agents":
        return <ComingSoonCard title="Agent" />;
      case "notifications":
        return <ComingSoonCard title="Notification" />;
      case "data-export":
        return <ComingSoonCard title="Data & Export" />;
      default:
        return <ModelsSubtab />;
    }
  };

  return (
    <div className="flex h-full overflow-hidden">
      {/* Sidebar Navigation */}
      <div className="w-64 lg:w-72 border-r border-border-subtle overflow-y-auto py-7">
        <div className="px-6 pb-4 border-b border-border-subtle">
          <h1 className="text-xl font-semibold text-ink">Settings</h1>
          <p className="text-sm text-ink-muted mt-0.5">Configure your Nexus workspace</p>
        </div>

        <div className="py-4">
          {/* Appearance Section */}
          <div className="px-6 pb-4 border-b border-border-subtle">
            <div className="flex items-center gap-2 text-ink-muted text-xs uppercase tracking-widest font-medium mb-2">
              <Sun className="w-3 h-3" />
              Appearance
            </div>
            <div className="flex items-center justify-between py-2">
              <span className="text-sm text-ink">Dark Mode</span>
              <button
                onClick={toggleDarkMode}
                className={cn(
                  "relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors duration-300",
                  isDarkMode ? "bg-accent" : "bg-border-medium"
                )}
                role="switch"
                aria-checked={isDarkMode}
                aria-label="Toggle dark mode"
              >
                <span
                  className={cn(
                    "pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow-sm transition-transform",
                    isDarkMode ? "translate-x-6" : "translate-x-1"
                  )}
                />
              </button>
            </div>
          </div>

          {/* Subtabs */}
          <div className="pt-4">
            {SUBTABS.map((subtab) => {
              const Icon = subtab.icon;
              const isActive = activeSubtab === subtab.id;
              return (
                <button
                  key={subtab.id}
                  onClick={() => setActiveSubtab(subtab.id)}
                  className={cn(
                    "w-full text-left px-6 py-3 flex items-center gap-3 transition-colors",
                    isActive
                      ? "bg-accent/10 border-r-2 border-accent text-accent"
                      : "hover:bg-surface-secondary/40 text-ink-secondary hover:text-ink"
                  )}
                >
                  <Icon className={cn("w-4 h-4", isActive && "text-accent")} />
                  <div className="flex-1">
                    <div className="text-sm font-medium">{subtab.label}</div>
                    <div className="text-xs text-ink-muted">{subtab.description}</div>
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* Content Area */}
      <div className="flex-1 overflow-y-auto py-6 px-8">
        <AnimatePresence mode="wait">
          <motion.div
            key={activeSubtab}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.2 }}
          >
            {renderSubtab()}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  );
}