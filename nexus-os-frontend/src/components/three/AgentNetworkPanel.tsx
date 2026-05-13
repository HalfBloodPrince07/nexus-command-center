"use client";

import { useState } from 'react';
import AgentNetwork from './AgentNetwork';
import { Expand, Shrink, Info } from 'lucide-react';

interface AgentNetworkPanelProps {
  onAgentSelect?: (agent: { id: string; name: string; lastActive: string }) => void;
}

export default function AgentNetworkPanel({ onAgentSelect }: AgentNetworkPanelProps) {
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [selectedAgent, setSelectedAgent] = useState<{ id: string; name: string; lastActive: string } | null>(null);

  const toggleFullscreen = () => {
    setIsFullscreen(!isFullscreen);
    // Could use screenfull.js or next/document to handle actual fullscreen API
  };

  const handleAgentClick = (agent: { id: string; name: string; lastActive: string }) => {
    setSelectedAgent(agent);
    onAgentSelect?.(agent);
  };

  return (
    <div className={isFullscreen ? "fixed inset-0 z-50 bg-white" : "relative h-full"}>
      {/* Header with controls */}
      <div className="flex items-center justify-between border-b border-black/[0.06] bg-white/40 px-4 py-3">
        <h2 className="text-sm font-semibold text-ink">Agent Network</h2>
        <div className="flex items-center gap-2">
          <button
            onClick={toggleFullscreen}
            className="rounded-lg p-2 text-ink-muted transition-colors hover:bg-black/[0.05] hover:text-ink"
            title={isFullscreen ? "Exit fullscreen" : "Fullscreen"}
          >
            {isFullscreen ? <Shrink size={16} /> : <Expand size={16} />}
          </button>
          <button
            className="rounded-lg p-2 text-ink-muted transition-colors hover:bg-black/[0.05] hover:text-ink"
            title="Legend"
          >
            <Info size={16} />
          </button>
        </div>
      </div>

      {/* Legend */}
      <div className="absolute top-16 right-4 z-10 rounded-xl bg-white/80 backdrop-blur p-3 shadow-lg text-xs">
        <h3 className="font-medium mb-2">Legend</h3>
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 bg-blue-500 rounded-full"></div>
            <span>Supervisor</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 bg-amber-500 rounded-full"></div>
            <span>Knowledge</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 bg-rose-500 rounded-full"></div>
            <span>Research</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 bg-purple-500 rounded-full"></div>
            <span>Journal</span>
          </div>
        </div>
      </div>

      {/* Agent Details Panel */}
      {selectedAgent && (
        <div className="absolute top-16 left-4 z-10 rounded-xl bg-white/90 backdrop-blur p-4 shadow-lg w-64">
          <h3 className="font-medium text-sm mb-2">{selectedAgent.name}</h3>
          <div className="text-xs text-ink-muted space-y-1">
            <p>ID: <span className="font-mono">{selectedAgent.id}</span></p>
            <p>Last active: {new Date(selectedAgent.lastActive).toLocaleTimeString()}</p>
          </div>
          <button
            onClick={() => setSelectedAgent(null)}
            className="mt-3 text-xs text-ink-muted hover:text-ink"
          >
            Close
          </button>
        </div>
      )}

      {/* Main Visualization */}
      <div className="flex-1 h-full">
        <AgentNetwork onAgentClick={handleAgentClick} />
      </div>
    </div>
  );
}