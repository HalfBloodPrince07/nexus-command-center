import { useState, useEffect } from "react";
import { useApi } from "@/hooks/useApi";

export interface SearchResult {
  conversation_id: string;
  conversation_title: string;
  message_id: string;
  snippet: string;
  score: number;
  timestamp: string;
  match_type: "vector" | "keyword";
  role: "user" | "assistant";
}

export interface Conversation {
  id: string;
  title: string;
  message_count: number;
  created_at: string;
  updated_at: string;
  is_pinned?: boolean;
}

interface UseChatHistoryParams {
  query?: string;
  dateFrom?: Date;
  dateTo?: Date;
  conversationId?: string;
  topK?: number;
}

interface UseChatHistoryReturn {
  searchResults: SearchResult[];
  conversations: Conversation[];
  isLoading: boolean;
  error: Error | null;
}

export function useChatHistory(params: UseChatHistoryParams): UseChatHistoryReturn {
  const { post } = useApi();
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let isMounted = true;

    const search = async () => {
      if (!params.query || params.query.trim().length < 3) {
        setSearchResults([]);
        setConversations([]);
        return;
      }

      setIsLoading(true);
      setError(null);

      try {
        const response = await post("/api/chat/history/search", {
          query: params.query,
          topK: params.topK || 20,
          dateFrom: params.dateFrom?.toISOString(),
          dateTo: params.dateTo?.toISOString(),
          conversationId: params.conversationId,
        });

        if (!isMounted) return;

        if (response.ok) {
          const data = await response.json();
          setSearchResults(data.results || []);
          
          // Extract unique conversations from results
          const convMap = new Map<string, Conversation>();
          data.results?.forEach((result: SearchResult) => {
            if (!convMap.has(result.conversation_id)) {
              convMap.set(result.conversation_id, {
                id: result.conversation_id,
                title: result.conversation_title,
                message_count: 0, // Would need separate API call
                created_at: result.timestamp,
                updated_at: result.timestamp,
              });
            }
          });
          setConversations(Array.from(convMap.values()));
        } else {
          throw new Error(`Search failed: ${response.status}`);
        }
      } catch (err) {
        if (!isMounted) return;
        setError(err instanceof Error ? err : new Error("Unknown error"));
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    };

    search();

    return () => {
      isMounted = false;
    };
  }, [post, params.query, params.dateFrom, params.dateTo, params.conversationId, params.topK]);

  return {
    searchResults,
    conversations,
    isLoading,
    error,
  };
}