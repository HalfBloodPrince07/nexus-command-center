'use client';

import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useAppStore } from '@/stores/useAppStore';
import GlassCard from '@/components/ui/GlassCard';
import { cn } from '@/lib/utils';
import {
  Cpu,
  Wifi,
  WifiOff,
  Loader2,
  CheckCircle2,
  AlertCircle,
  Zap,
  Database,
  RefreshCw
} from 'lucide-react';
import Skeleton from 'react-loading-skeleton';
import 'react-loading-skeleton/dist/skeleton.css';
import toast from 'react-hot-toast';
import type { LMStudioHealth, LMStudioModel, LMStudioModelsResponse, ModelSettings } from '@/lib/settingsApi';

interface RoleAssignment {
  supervisor?: string;
  embedding?: string;
  vision?: string;
  reranker?: string;
}

const ROLES = [
  { key: 'supervisor', label: 'Supervisor', description: 'Main chat agent' },
  { key: 'embedding', label: 'Embedding', description: 'Memory & search' },
  { key: 'vision', label: 'Vision', description: 'Image analysis' },
  { key: 'reranker', label: 'Reranker', description: 'Search relevance' },
];

export default function ModelsSubtab() {
  const [baseUrl, setBaseUrl] = useState('http://localhost:1234/v1');
  const [connectionStatus, setConnectionStatus] = useState<'idle' | 'testing' | 'connected' | 'error'>('idle');
  const [models, setModels] = useState<LMStudioModel[]>([]);
  const [loadingModels, setLoadingModels] = useState(false);
  const [roleAssignments, setRoleAssignments] = useState<RoleAssignment>({});
  const [applying, setApplying] = useState(false);
  
  const { isDarkMode } = useAppStore();

  // Test LM Studio connection
  const testConnection = useCallback(async () => {
    if (!baseUrl) {
      toast.error('Please enter a valid base URL');
      return;
    }

    setConnectionStatus('testing');
    const loadingToast = toast.loading('Testing LM Studio connection...');
    
    try {
      const res = await fetch(`/api/system/lm-studio/health?baseUrl=${encodeURIComponent(baseUrl)}`);
      const data: LMStudioHealth = await res.json();
      
      if (data.status === 'ok') {
        toast.dismiss(loadingToast);
        toast.success('LM Studio connection successful!');
        setConnectionStatus('connected');
        await loadModels();
      } else {
        throw new Error(data.message || 'Connection failed');
      }
    } catch (error) {
      toast.dismiss(loadingToast);
      toast.error(`Failed to connect to LM Studio: ${error instanceof Error ? error.message : 'Unknown error'}`);
      setConnectionStatus('error');
    }
  }, [baseUrl]);

  // Load models from LM Studio
  const loadModels = useCallback(async () => {
    setLoadingModels(true);
    try {
      const res = await fetch(`/api/system/lm-studio/models?baseUrl=${encodeURIComponent(baseUrl)}`);
      const data: LMStudioModelsResponse = await res.json();
      setModels(data.models || []);
      
      // Load current settings for role assignments
      const settingsRes = await fetch('/api/settings/models');
      if (settingsRes.ok) {
        const settings: ModelSettings = await settingsRes.json();
        setRoleAssignments({
          supervisor: settings.supervisor_model,
          embedding: settings.embedding_model,
          vision: settings.vision_model,
          reranker: settings.reranker_model,
        });
      }
    } catch (error) {
      toast.error('Failed to load models from LM Studio');
      setModels([]);
    } finally {
      setLoadingModels(false);
    }
  }, [baseUrl]);

  // Poll for models every 30 seconds when connected
  useEffect(() => {
    if (connectionStatus !== 'connected') return;
    
    const interval = setInterval(() => {
      loadModels();
    }, 30000);

    return () => clearInterval(interval);
  }, [connectionStatus, loadModels]);

  // Apply model settings
  const applySettings = useCallback(async () => {
    setApplying(true);
    try {
      const res = await fetch('/api/settings/models', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          supervisor_model: roleAssignments.supervisor,
          embedding_model: roleAssignments.embedding,
          vision_model: roleAssignments.vision,
          reranker_model: roleAssignments.reranker,
        }),
      });
      
      if (!res.ok) throw new Error('Failed to apply settings');
      
      toast.success('Model settings applied successfully');
      await loadModels(); // Refresh to show updated state
    } catch (error) {
      toast.error('Failed to apply model settings');
    } finally {
      setApplying(false);
    }
  }, [roleAssignments, loadModels]);

  // Handle role assignment change
  const handleRoleChange = useCallback((role: keyof RoleAssignment, modelId: string) => {
    setRoleAssignments(prev => ({ ...prev, [role]: modelId }));
  }, []);

  // Initial load
  useEffect(() => {
    loadModels();
  }, [loadModels]);

  // Trigger embedding reindex
  const triggerReindex = useCallback(async () => {
    const confirmed = confirm(
      'Re-indexing embeddings will process all your files and memory entries. This may take a while and consume significant system resources.\n\nDo you want to continue?'
    );
    
    if (!confirmed) return;
    
    const loadingToast = toast.loading('Starting reindex process...');
    try {
      const res = await fetch('/api/embeddings/reindex', { method: 'POST' });
      if (!res.ok) throw new Error('Failed to trigger reindex');
      toast.dismiss(loadingToast);
      toast.success('Reindexing started. You can continue using Nexus while this runs in the background.');
    } catch (error) {
      toast.dismiss(loadingToast);
      toast.error('Failed to start reindexing');
    }
  }, []);

  return (
    <div className="flex flex-col h-full gap-6 overflow-y-auto">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-ink">Models & AI Configuration</h1>
          <p className="text-sm text-ink-muted mt-0.5">Configure language models and their roles</p>
        </div>
      </div>

      {/* LM Studio Configuration Card */}
      <GlassCard variant="bordered" padding="md">
        <div className="flex items-center gap-2 text-ink-muted text-xs uppercase tracking-widest font-medium mb-4">
          <Cpu className="w-3.5 h-3.5" />
          LM Studio Configuration
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-2">
            <label className="text-sm font-medium text-ink">Base URL</label>
            <div className="flex gap-2">
              <input
                type="text"
                value={baseUrl}
                onChange={(e) => setBaseUrl(e.target.value)}
                className={cn(
                  "flex-1 px-3 py-2 rounded-lg text-sm font-mono",
                  "border border-border-medium bg-surface-primary/60 text-ink",
                  "focus:outline-none focus:ring-2 focus:ring-accent/50 focus:border-accent"
                )}
                placeholder="http://localhost:1234/v1"
              />
              <button
                onClick={testConnection}
                disabled={connectionStatus === 'testing'}
                className={cn(
                  "px-4 py-2 rounded-lg text-sm font-medium flex items-center gap-2",
                  "bg-accent hover:bg-accent-hover text-white",
                  "transition-colors disabled:opacity-50"
                )}
              >
                {connectionStatus === 'testing' ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Testing...
                  </>
                ) : (
                  <>
                    <RefreshCw className="w-4 h-4" />
                    Test Connection
                  </>
                )}
              </button>
            </div>
          </div>

          <div className="flex items-end">
            <AnimatePresence mode="wait">
              {connectionStatus === 'connected' && (
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                  className="flex items-center gap-2 text-emerald-600 dark:text-emerald-400 text-sm bg-emerald-500/10 rounded-lg px-3 py-2 border border-emerald-500/20"
                >
                  <Wifi className="w-4 h-4" />
                  <span>Connected to LM Studio</span>
                </motion.div>
              )}
              {connectionStatus === 'error' && (
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                  className="flex items-center gap-2 text-red-500 text-sm bg-red-500/10 rounded-lg px-3 py-2 border border-red-500/20"
                >
                  <WifiOff className="w-4 h-4" />
                  <span>Connection failed</span>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
      </GlassCard>

      {/* Available Models Card */}
      <GlassCard variant="bordered" padding="md">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2 text-ink-muted text-xs uppercase tracking-widest font-medium">
            <Zap className="w-3.5 h-3.5" />
            Available Models & Role Assignment
          </div>
          {models.length > 0 && (
            <div className="flex items-center gap-2 text-sm text-ink-muted">
              <span>{models.length} model{models.length !== 1 ? 's' : ''} loaded</span>
              <div className="w-2 h-2 bg-emerald-400 rounded-full animate-pulse"></div>
            </div>
          )}
        </div>

        {loadingModels ? (
          <div className="flex items-center gap-2 text-ink-muted text-sm py-4">
            <Loader2 className="w-4 h-4 animate-spin" />
            Loading models from LM Studio...
          </div>
        ) : models.length === 0 ? (
          <div className="text-ink-muted text-sm py-4 text-center">
            No models found. Make sure LM Studio is running and the connection is working.
          </div>
        ) : (
          <div className="space-y-2">
            {models.map((model) => (
              <motion.div
                key={model.id}
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                className="rounded-lg border border-border-subtle bg-surface-primary/40 p-3"
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-mono font-medium text-ink truncate flex-1">{model.name}</span>
                  <span className="text-xs text-ink-muted ml-2 whitespace-nowrap">
                    {model.context_length?.toLocaleString()} ctx
                  </span>
                </div>
                
                {model.quantization && (
                  <div className="mb-3">
                    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-accent/10 text-accent">
                      {model.quantization}
                    </span>
                  </div>
                )}

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-2">
                  {ROLES.map((role) => {
                    const isAssigned = roleAssignments[role.key as keyof RoleAssignment] === model.id;
                    return (
                      <div key={role.key} className="space-y-1">
                        <label className="text-xs text-ink-muted">{role.label}</label>
                        <select
                          value={isAssigned ? model.id : ''}
                          onChange={(e) => handleRoleChange(role.key as keyof RoleAssignment, e.target.value)}
                          className={cn(
                            "w-full px-2 py-1 rounded text-xs",
                            "border border-border-medium bg-surface-primary/60 text-ink",
                            "focus:outline-none focus:ring-1 focus:ring-accent/50 focus:border-accent"
                          )}
                        >
                          <option value="">None</option>
                          <option value={model.id}>{model.name}</option>
                        </select>
                        {isAssigned && (
                          <div className="text-xs text-accent">Active for {role.label}</div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </motion.div>
            ))}
          </div>
        )}

        <div className="mt-4 flex justify-end">
          <button
            onClick={applySettings}
            disabled={applying}
            className={cn(
              "px-4 py-2 rounded-lg text-sm font-medium flex items-center gap-2",
              "bg-accent hover:bg-accent-hover text-white",
              "transition-colors disabled:opacity-50"
            )}
          >
            {applying ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Applying...
              </>
            ) : (
              <>
                <CheckCircle2 className="w-4 h-4" />
                Apply Model Assignments
              </>
            )}
          </button>
        </div>
      </GlassCard>

      {/* Embedding Model Card */}
      <GlassCard variant="bordered" padding="md">
        <div className="flex items-center gap-2 text-ink-muted text-xs uppercase tracking-widest font-medium mb-4">
          <Database className="w-3.5 h-3.5" />
          Embedding Model
        </div>

        <div className="rounded-lg border border-border-subtle bg-surface-primary/40 p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-ink">Currently Using</p>
              <code className="mt-1 inline-block px-2 py-1 rounded text-xs font-mono bg-surface-secondary text-ink-secondary">
                BAAI/bge-m3
              </code>
              <p className="text-xs text-ink-muted mt-2">
                Multi-language embedding model for semantic search and memory
              </p>
            </div>
            <button
              onClick={triggerReindex}
              className={cn(
                "px-3 py-1.5 rounded text-sm font-medium",
                "border border-border-medium text-ink-muted hover:text-ink",
                "bg-surface-secondary/40 hover:bg-surface-primary/60 transition-colors"
              )}
            >
              Re-index All Files
            </button>
          </div>
        </div>

        <p className="text-xs text-ink-muted mt-3">
          Re-indexing processes all files and memory entries. This can be time-consuming for large datasets.
        </p>
      </GlassCard>
    </div>
  );
}
