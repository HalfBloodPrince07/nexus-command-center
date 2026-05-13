import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import {
  MemoryStats,
  EpisodicItem,
  SemanticResult,
  ProceduralPattern,
  fetchMemoryStats,
  fetchAllEpisodicMemory,
  fetchEpisodicMemory,
  fetchSemanticMemory,
  searchSemanticMemory,
  fetchProceduralMemory,
  clearEpisodicMemory,
} from '@/lib/memoryApi';
import { fetchConversationStats, ConversationStats } from '@/lib/statsApi';

export type MemoryLayer = 'episodic' | 'semantic' | 'procedural';

type MemoryState = {
  stats: MemoryStats | null;
  episodicItems: EpisodicItem[];
  semanticItems: SemanticResult[];
  semanticResults: SemanticResult[];
  proceduralPatterns: ProceduralPattern[];
  semanticQuery: string;
  selectedLayer: MemoryLayer;
  isLoadingStats: boolean;
  isLoadingLayer: boolean;
  convStats: ConversationStats | null;
};

type MemoryActions = {
  loadStats: () => Promise<void>;
  loadConvStats: () => Promise<void>;
  loadAllEpisodic: () => Promise<void>;
  loadEpisodic: (sessionId: string) => Promise<void>;
  loadSemantic: (limit?: number) => Promise<void>;
  browseSemantic: (limit?: number) => Promise<void>;
  searchSemantic: (q: string) => Promise<void>;
  loadProcedural: (type?: string) => Promise<void>;
  loadGraph: () => Promise<void>;
  loadConflicts: () => Promise<void>;
  setSelectedLayer: (layer: MemoryLayer) => void;
  setSemanticQuery: (q: string) => void;
  clearEpisodic: (sessionId: string) => Promise<void>;
};

export const useMemoryStore = create<MemoryState & MemoryActions>()(
  devtools(
    (set, get) => ({
      stats: null,
      episodicItems: [],
      semanticItems: [],
      semanticResults: [],
      proceduralPatterns: [],
      semanticQuery: '',
      selectedLayer: 'episodic',
      isLoadingStats: false,
      isLoadingLayer: false,
      convStats: null,
      graphData: null,
      conflicts: [],

      loadStats: async () => {
        set({ isLoadingStats: true });
        const stats = await fetchMemoryStats();
        set({ stats, isLoadingStats: false });
      },

      loadConvStats: async () => {
        const convStats = await fetchConversationStats();
        set({ convStats });
      },

      loadAllEpisodic: async () => {
        set({ isLoadingLayer: true });
        const { items } = await fetchAllEpisodicMemory();
        set({ episodicItems: items, isLoadingLayer: false });
      },

      loadEpisodic: async (sessionId) => {
        set({ isLoadingLayer: true });
        const { items } = await fetchEpisodicMemory(sessionId || 'default');
        set({ episodicItems: items, isLoadingLayer: false });
      },

      loadSemantic: async (limit = 50) => {
        set({ isLoadingLayer: true });
        const { items } = await fetchSemanticMemory(limit);
        set({ semanticItems: items, isLoadingLayer: false });
      },

      browseSemantic: async (limit = 50) => {
        set({ semanticQuery: '', isLoadingLayer: true });
        const { items } = await fetchSemanticMemory(limit);
        set({ semanticItems: items, semanticResults: [], isLoadingLayer: false });
      },

      searchSemantic: async (q) => {
        const query = q.trim();
        if (!query) {
          set({ semanticResults: [], semanticQuery: q });
          return;
        }
        set({ isLoadingLayer: true, semanticQuery: q });
        const { results } = await searchSemanticMemory(query);
        set({ semanticResults: results, isLoadingLayer: false });
      },

      loadProcedural: async (type) => {
        set({ isLoadingLayer: true });
        const { patterns } = await fetchProceduralMemory(type);
        set({ proceduralPatterns: patterns, isLoadingLayer: false });
      },

      setSelectedLayer: (layer) => set({ selectedLayer: layer }),
      setSemanticQuery: (q) => set({ semanticQuery: q }),

      clearEpisodic: async (sessionId) => {
        const ok = await clearEpisodicMemory(sessionId || 'default');
        if (ok) {
          set({ episodicItems: [] });
          // refresh stats after clear
          await get().loadStats();
        }
      },
    }),
    { name: 'MemoryStore', enabled: process.env.NODE_ENV === 'development' }
  )
);
