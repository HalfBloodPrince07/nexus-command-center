"use client";

import { useState, useCallback, useMemo } from "react";
import { Search, Calendar, Trash2, Download, Pin, FileText, X, Filter } from "lucide-react";
import { useChatHistory } from "@/hooks/useChatHistory";
import { useChatStore } from "@/stores/useChatStore";
import { format } from "date-fns";
import { Virtualizer } from "@/components/ui/Virtualizer";
import { debounce } from "lodash";

interface ChatHistorySubtabProps {
  onLoadConversation: (conversationId: string) => void;
}

interface Conversation {
  id: string;
  title: string;
  message_count: number;
  created_at: string;
  updated_at: string;
  is_pinned?: boolean;
}

interface SearchResult {
  conversation_id: string;
  conversation_title: string;
  message_id: string;
  snippet: string;
  score: number;
  timestamp: string;
  role: "user" | "assistant";
}

export default function ChatHistorySubtab({ onLoadConversation }: ChatHistorySubtabProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedConversations, setSelectedConversations] = useState<Set<string>>(new Set());
  const [activeConversation, setActiveConversation] = useState<string | null>(null);
  const [dateFrom, setDateFrom] = useState<string>("");
  const [dateTo, setDateTo] = useState<string>("");
  const [showFilters, setShowFilters] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);

  const { searchResults, isLoading, error, conversations } = useChatHistory({
    query: searchQuery,
    dateFrom: dateFrom ? new Date(dateFrom) : undefined,
    dateTo: dateTo ? new Date(dateTo) : undefined,
  });

  const { switchConversation } = useChatStore();

  const handleSearch = useCallback(
    debounce((query: string) => {
      setSearchQuery(query);
    }, 300),
    []
  );

  const handleLoadConversation = (conversationId: string, messageId?: string) => {
    switchConversation(conversationId);
    onLoadConversation(conversationId);
    setActiveConversation(conversationId);
    
    // Scroll to message if provided
    if (messageId) {
      setTimeout(() => {
        const element = document.querySelector(`[data-message-id="${messageId}"]`);
        element?.scrollIntoView({ behavior: "smooth" });
      }, 300);
    }
  };

  const toggleSelection = (conversationId: string) => {
    const newSelected = new Set(selectedConversations);
    if (newSelected.has(conversationId)) {
      newSelected.delete(conversationId);
    } else {
      newSelected.add(conversationId);
    }
    setSelectedConversations(newSelected);
  };

  const archivedSelected = async () => {
    if (selectedConversations.size === 0) return;
    
    setIsProcessing(true);
    try {
      // For now, we'll unpin the selected conversations as a soft delete
      for (const conversationId of selectedConversations) {
        const response = await fetch(
          `/api/chat/history/conversations/${conversationId}/pin`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({ pin: false }),
          }
        );

        if (!response.ok) {
          throw new Error(`Archive failed: ${response.statusText}`);
        }
      }
      
      console.log(`Archived ${selectedConversations.size} conversation(s)`);
      location.reload();
    } catch (error) {
      console.error("Archive failed:", error);
      alert(`Archive failed: ${error instanceof Error ? error.message : "Unknown error"}`);
    } finally {
      setIsProcessing(false);
      setSelectedConversations(new Set());
    }
  };

  const exportSelected = async () => {
    if (selectedConversations.size === 0) return;
    
    setIsProcessing(true);
    try {
      // Export each selected conversation using backend API
      for (const conversationId of selectedConversations) {
        const response = await fetch(`/api/chat/history/conversations/${conversationId}/export`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({}),
        });

        if (!response.ok) {
          throw new Error(`Export failed: ${response.statusText}`);
        }

        const data = await response.json();
        const downloadResponse = await fetch(data.download_url);
        
        // Download the markdown file
        const blob = await downloadResponse.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = data.filename;
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);
      }
      
      console.log(`Exported ${selectedConversations.size} conversation(s)`);
    } catch (error) {
      console.error("Export failed:", error);
      alert(`Export failed: ${error instanceof Error ? error.message : "Unknown error"}`);
    } finally {
      setIsProcessing(false);
      setSelectedConversations(new Set());
    }
  };

  const hasSelected = selectedConversations.size > 0;

  const groupedResults = useMemo(() => {
    const grouped = new Map<string, SearchResult[]>();
    searchResults?.forEach(result => {
      if (!grouped.has(result.conversation_id)) {
        grouped.set(result.conversation_id, []);
      }
      grouped.get(result.conversation_id)?.push(result);
    });
    return grouped;
  }, [searchResults]);

  return (
    <div className="h-full flex flex-col">
      {/* Search Header */}
      <div className="border-b border-black/[0.06] bg-white/50 px-6 py-4">
        <div className="flex items-center gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-muted w-4 h-4" />
            <input
              type="text"
              placeholder="Search all conversations..."
              onChange={(e) => handleSearch(e.target.value)}
              className="w-full pl-10 pr-4 py-2 rounded-lg border border-black/[0.08] focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 text-sm"
            />
          </div>
          
          <button
            onClick={() => setShowFilters(!showFilters)}
            className="flex items-center gap-2 px-3 py-2 rounded-lg border border-black/[0.08] hover:bg-black/[0.02] text-sm font-medium"
          >
            <Filter className="w-4 h-4" />
            Filters
          </button>
        </div>

        {/* Filters */}
        {showFilters && (
          <div className="mt-3 flex items-center gap-3 animate-in fade-in duration-150">
            <div className="flex items-center gap-2">
              <Calendar className="w-4 h-4 text-ink-muted" />
              <input
                type="date"
                value={dateFrom}
                onChange={(e) => setDateFrom(e.target.value)}
                className="px-2 py-1 text-sm rounded border border-black/[0.08]"
              />
              <span className="text-ink-muted text-sm">to</span>
              <input
                type="date"
                value={dateTo}
                onChange={(e) => setDateTo(e.target.value)}
                className="px-2 py-1 text-sm rounded border border-black/[0.08]"
              />
            </div>
          </div>
        )}
      </div>

      {/* Results Area */}
      <div className="flex-1 min-h-0 flex">
        {/* Conversation List */}
        <div className="w-96 border-r border-black/[0.06] overflow-y-auto">
          {isLoading ? (
            <div className="p-6 text-center text-ink-muted">
              <div className="animate-spin w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full mx-auto mb-2" />
              Searching conversations...
            </div>
          ) : error ? (
            <div className="p-6 text-center text-red-600">
              Failed to search: {error.message}
            </div>
          ) : (
            <Virtualizer
              items={Array.from(groupedResults.entries())}
              renderItem={([conversationId, results]) => {
                const conversation = conversations.find(c => c.id === conversationId);
                if (!conversation) return null;

                return (
                  <div
                    key={conversationId}
                    onClick={() => handleLoadConversation(conversationId)}
                    className={`p-4 border-b border-black/[0.04] hover:bg-black/[0.02] cursor-pointer transition-colors ${
                      activeConversation === conversationId ? "bg-blue-50/50 border-l-4 border-l-blue-500" : ""
                    }`}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <h3 className="font-medium text-sm text-ink">
                          {conversation.title || "Untitled Conversation"}
                        </h3>
                        <p className="text-xs text-ink-muted mt-1">
                          {format(new Date(conversation.updated_at), "MMM d, yyyy · h:mm a")}
                        </p>
                        <p className="text-xs text-ink-muted mt-1">
                          {conversation.message_count} messages
                        </p>
                      </div>
                      
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          toggleSelection(conversationId);
                        }}
                        className="ml-2 p-1 rounded hover:bg-black/[0.05]"
                      >
                        <input
                          type="checkbox"
                          checked={selectedConversations.has(conversationId)}
                          readOnly
                          className="w-4 h-4 rounded border-gray-300"
                        />
                      </button>
                    </div>

                    {/* Search matches preview */}
                    {results.length > 0 && (
                      <div className="mt-2 space-y-1">
                        {results.slice(0, 2).map((result, idx) => (
                          <div
                            key={`${result.message_id}-${idx}`}
                            className="text-xs text-ink-muted bg-black/[0.03] rounded px-2 py-1 truncate"
                            title={result.snippet}
                          >
                            {result.snippet}
                          </div>
                        ))}
                        {results.length > 2 && (
                          <p className="text-xs text-blue-600">
                            +{results.length - 2} more matches
                          </p>
                        )}
                      </div>
                    )}
                  </div>
                );
              }}
              estimateSize={() => 120}
              overscan={5}
            />
          )}
        </div>

        {/* Selected Conversation */}
        {activeConversation && (
          <div className="flex-1 overflow-y-auto p-6">
            <button
              onClick={() => setActiveConversation(null)}
              className="flex items-center gap-2 text-ink-muted hover:text-ink text-sm mb-4"
            >
              <X className="w-4 h-4" />
              Back to results
            </button>

            <div className="max-w-4xl mx-auto">
              <h2 className="text-lg font-semibold text-ink mb-4">
                {conversations.find(c => c.id === activeConversation)?.title || "Conversation"}
              </h2>
              
              {/* Conversation messages would be rendered here */}
              <div className="text-center text-ink-muted py-12">
                <FileText className="w-8 h-8 mx-auto mb-2 text-ink-muted" />
                <p>Conversation history can be loaded here</p>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Action Bar */}
      {hasSelected && (
        <div className="border-t border-black/[0.06] bg-white/50 px-6 py-3">
          <div className="flex items-center justify-between">
            <span className="text-sm text-ink">
              {selectedConversations.size} selected
            </span>
            
            <div className="flex items-center gap-2">
              <button
                onClick={archivedSelected}
                disabled={isProcessing}
                className="flex items-center gap-2 px-3 py-1.5 rounded text-sm bg-ink-muted/10 hover:bg-ink-muted/20 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Trash2 className="w-4 h-4" />
                Archive
              </button>
              
              <button
                onClick={exportSelected}
                disabled={isProcessing}
                className="flex items-center gap-2 px-3 py-1.5 rounded text-sm bg-blue-500 text-white hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Download className="w-4 h-4" />
                Export
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}