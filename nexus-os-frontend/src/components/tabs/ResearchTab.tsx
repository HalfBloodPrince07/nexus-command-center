"use client";

import { AnimatePresence, motion } from "framer-motion";
import { FlaskConical, BookOpen, Database } from "lucide-react";
import { useResearchStore } from "@/stores/useResearchStore";
import NewResearch from "@/components/research/NewResearch";
import ReportsLibrary from "@/components/research/ReportsLibrary";
import SourceManager from "@/components/research/SourceManager";
import ReportViewer from "@/components/research/ReportViewer";
import { cn } from "@/lib/utils";

const subTabs = [
  { id: "new" as const,     label: "New Research", icon: FlaskConical },
  { id: "library" as const, label: "Library",      icon: BookOpen },
  { id: "sources" as const, label: "Sources",      icon: Database },
];

export default function ResearchTab() {
  const { activeSubTab, setActiveSubTab, viewingReport } = useResearchStore();

  if (viewingReport) return <ReportViewer />;

  return (
    <div className="flex h-full flex-col overflow-hidden">
      {/* Sub-tab bar */}
      <div className="flex flex-shrink-0 items-center gap-1 border-b border-border-subtle px-4 pt-3 pb-0">
        {subTabs.map(({ id, label, icon: Icon }) => {
          const active = activeSubTab === id;
          return (
            <button
              key={id}
              onClick={() => setActiveSubTab(id)}
              className={cn(
                "relative flex items-center gap-2 rounded-t-xl px-4 py-2.5 text-sm font-medium transition-all",
                active ? "text-accent" : "text-ink-secondary hover:text-ink"
              )}
            >
              <Icon size={15} strokeWidth={1.8} />
              {label}
              {active && (
                <motion.div
                  layoutId="researchSubTab"
                  className="absolute inset-x-0 bottom-0 h-[2px] rounded-full bg-gradient-primary"
                  transition={{ type: "spring", stiffness: 400, damping: 35 }}
                />
              )}
            </button>
          );
        })}
      </div>

      {/* Content */}
      <div className="min-h-0 flex-1 overflow-hidden">
        <AnimatePresence mode="wait">
          <motion.div
            key={activeSubTab}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
            className="h-full"
          >
            {activeSubTab === "new" && <NewResearch />}
            {activeSubTab === "library" && <ReportsLibrary />}
            {activeSubTab === "sources" && <SourceManager />}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  );
}
