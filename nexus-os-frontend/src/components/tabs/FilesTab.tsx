"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { AnimatePresence, motion } from "framer-motion";
import { useDropzone } from "react-dropzone";
import {
  Database,
  File as FileIcon,
  FileText,
  FileSpreadsheet,
  FolderOpen,
  FolderSearch,
  Image as ImageIcon,
  LayoutGrid,
  List,
  Loader2,
  MessageSquare,
  Plus,
  RefreshCw,
  Search,
  Send,
  Trash2,
  Upload,
  X,
} from "lucide-react";
import ProcessingPipeline from "@/components/ProcessingPipeline";
import {
  deleteFile,
  getFileStatus,
  listFiles,
  listWatchedFolders,
  reprocessFile,
  searchGlobal,
  stopWatchingFolder,
  streamChatWithFiles,
  uploadFile,
  watchFolder,
} from "@/lib/filesApi";
import { cn } from "@/lib/utils";
import type {
  ChatMessage,
  FileRecord,
  FolderWatcher,
  GlobalSearchResult,
  PipelineStage,
  UploadProgress,
} from "@/types/files";

// ── Constants ─────────────────────────────────────────────────────────────────

type MainTab = "data-management" | "search-chat";
type ViewMode = "grid" | "list";

const MAX_UPLOAD_SIZE = 50 * 1024 * 1024;
const ACCEPT = {
  "application/pdf": [".pdf"],
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
  "text/markdown": [".md"],
  "text/plain": [".txt"],
  "image/png": [".png"],
  "image/jpeg": [".jpg", ".jpeg"],
  "image/webp": [".webp"],
};

const STAGE_MESSAGES: Record<PipelineStage, string> = {
  uploading: "Uploading file...",
  parsing: "Parsing document...",
  chunking: "Summarizing & chunking...",
  embedding: "Embedding chunks...",
  done: "Index ready.",
  error: "Processing failed.",
};

// ── Root component ─────────────────────────────────────────────────────────────

export default function FilesTab() {
  const [activeTab, setActiveTab] = useState<MainTab>("data-management");
  const [files, setFiles] = useState<FileRecord[]>([]);
  const [uploadQueue, setUploadQueue] = useState<UploadProgress[]>([]);
  const [watchers, setWatchers] = useState<FolderWatcher[]>([]);

  const refreshFiles = useCallback(() => {
    listFiles().then(setFiles).catch(() => {});
  }, []);

  const refreshWatchers = useCallback(() => {
    listWatchedFolders().then(setWatchers).catch(() => {});
  }, []);

  useEffect(() => {
    refreshFiles();
    refreshWatchers();

    const id = window.setInterval(() => {
      refreshFiles();
      refreshWatchers();
    }, 5000);
    return () => window.clearInterval(id);
  }, [refreshFiles, refreshWatchers]);

  const pollingRef = useRef<Record<string, boolean>>({});
  useEffect(() => () => { pollingRef.current = {}; }, []);

  const updateQueueItem = useCallback(
    (fileId: string, patch: Partial<UploadProgress>) =>
      setUploadQueue((cur) => cur.map((item) => item.fileId === fileId ? { ...item, ...patch } : item)),
    []
  );
  const removeQueueItem = useCallback(
    (fileId: string) => setUploadQueue((cur) => cur.filter((item) => item.fileId !== fileId)),
    []
  );

  const wait = useCallback((ms: number) => new Promise<void>((r) => window.setTimeout(r, ms)), []);

  const pollStatus = useCallback(async (fileId: string) => {
    pollingRef.current[fileId] = true;
    let stage: PipelineStage = "parsing";
    const stageSeq: PipelineStage[] = ["parsing", "chunking", "embedding"];
    let stageIdx = 0;

    while (pollingRef.current[fileId]) {
      try {
        const status = await getFileStatus(fileId);
        if (!pollingRef.current[fileId]) return;

        if (status.status === "ready") {
          updateQueueItem(fileId, { stage: "done", uploadPct: 100, message: `Indexed ${status.chunk_count ?? 0} chunks.` });
          await wait(1200);
          removeQueueItem(fileId);
          break;
        }
        if (status.status === "error") {
          updateQueueItem(fileId, { stage: "error", message: "Processing failed." });
          await wait(1500);
          removeQueueItem(fileId);
          break;
        }

        stageIdx = Math.min(stageIdx + 1, stageSeq.length - 1);
        stage = stageSeq[stageIdx];
        updateQueueItem(fileId, { stage, message: STAGE_MESSAGES[stage] });
      } catch {
        updateQueueItem(fileId, { stage: "error", message: "Unable to read file status." });
        await wait(1500);
        removeQueueItem(fileId);
        break;
      }
      await wait(2000);
    }
    delete pollingRef.current[fileId];
  }, [removeQueueItem, updateQueueItem, wait]);

  const processUpload = useCallback(async (file: File, tempId: string) => {
    try {
      const response = await uploadFile(file, "files", (pct) =>
        updateQueueItem(tempId, { uploadPct: pct, message: `Uploading... ${pct}%` })
      );
      updateQueueItem(tempId, { fileId: response.file_id, stage: "parsing", uploadPct: 100, message: STAGE_MESSAGES.parsing });
      await pollStatus(response.file_id);
    } catch {
      updateQueueItem(tempId, { stage: "error", message: "Upload failed." });
      await wait(1500);
      removeQueueItem(tempId);
    }
  }, [pollStatus, removeQueueItem, updateQueueItem, wait]);

  const handleUpload = useCallback((acceptedFiles: File[]) => {
    acceptedFiles.forEach((file) => {
      const tempId = `upload_${Date.now()}_${Math.random().toString(36).slice(2)}`;
      setUploadQueue((cur) => [
        ...cur,
        { fileId: tempId, originalName: file.name, stage: "uploading", uploadPct: 0, message: STAGE_MESSAGES.uploading },
      ]);
      void processUpload(file, tempId);
    });
  }, [processUpload]);

  const handleDelete = useCallback(async (fileId: string): Promise<void> => {
    try {
      await deleteFile(fileId);
    } catch (err) {
      // Re-throw with context so the FileCard can display it
      throw err instanceof Error ? err : new Error(String(err));
    }
    // Refresh even if there were warnings — the record is gone
    try { refreshFiles(); } catch { /* ignore */ }
    removeQueueItem(fileId);
  }, [refreshFiles, removeQueueItem]);

  const handleReprocess = useCallback(async (fileId: string) => {
    await reprocessFile(fileId);
    await refreshFiles();
  }, [refreshFiles]);

  const handleWatchFolder = useCallback(async (path: string) => {
    await watchFolder(path, "files");
    await refreshWatchers();
  }, [refreshWatchers]);

  const handleStopWatcher = useCallback(async (id: string) => {
    await stopWatchingFolder(id);
    setWatchers((cur) => cur.filter((w) => w.id !== id));
  }, []);

  return (
    <div className="h-full min-h-0 flex flex-col">
      {/* Main tabs */}
      <div className="flex border-b border-glass-border shrink-0">
        <MainTabButton
          active={activeTab === "data-management"}
          onClick={() => setActiveTab("data-management")}
          icon={<Database className="h-4 w-4" />}
          label="Data Management"
        />
        <MainTabButton
          active={activeTab === "search-chat"}
          onClick={() => setActiveTab("search-chat")}
          icon={<MessageSquare className="h-4 w-4" />}
          label="Search & Chat"
        />
      </div>

      <div className="min-h-0 flex-1 overflow-hidden">
        <AnimatePresence mode="wait">
          {activeTab === "data-management" ? (
            <motion.div
              key="data-management"
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -8 }}
              transition={{ duration: 0.2 }}
              className="h-full"
            >
              <DataManagementTab
                files={files}
                uploadQueue={uploadQueue}
                watchers={watchers}
                onFilesDropped={handleUpload}
                onDelete={handleDelete}
                onReprocess={handleReprocess}
                onWatchFolder={handleWatchFolder}
                onStopWatcher={handleStopWatcher}
              />
            </motion.div>
          ) : (
            <motion.div
              key="search-chat"
              initial={{ opacity: 0, x: 8 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 8 }}
              transition={{ duration: 0.2 }}
              className="h-full"
            >
              <SearchChatTab files={files} />
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

// ── Tab 1: Data Management ────────────────────────────────────────────────────

function DataManagementTab({
  files,
  uploadQueue,
  watchers,
  onFilesDropped,
  onDelete,
  onReprocess,
  onWatchFolder,
  onStopWatcher,
}: {
  files: FileRecord[];
  uploadQueue: UploadProgress[];
  watchers: FolderWatcher[];
  onFilesDropped: (files: File[]) => void;
  onDelete: (fileId: string) => Promise<void>;
  onReprocess: (fileId: string) => Promise<void>;
  onWatchFolder: (path: string) => Promise<void>;
  onStopWatcher: (id: string) => Promise<void>;
}) {
  const [viewMode, setViewMode] = useState<ViewMode>("grid");

  return (
    <div className="h-full flex flex-col gap-0 overflow-hidden">
      <div className="flex flex-col lg:flex-row gap-4 p-6 pb-0 shrink-0">
        {/* Upload dropzone */}
        <UploadZone onFilesDropped={onFilesDropped} queue={uploadQueue} className="flex-1" />
        {/* Folder watcher panel */}
        <FolderWatchPanel watchers={watchers} onWatch={onWatchFolder} onStop={onStopWatcher} />
      </div>

      {/* File browser */}
      <div className="flex-1 min-h-0 overflow-hidden p-6 pt-4 flex flex-col">
        <div className="flex items-center justify-between mb-4 shrink-0">
          <div>
            <h3 className="text-base font-semibold text-text-primary">
              Active Files
              <span className="ml-2 text-xs font-normal text-text-muted">({files.length})</span>
            </h3>
          </div>
          <div className="inline-flex rounded-2xl border border-glass-border bg-surface-1/70 p-1">
            <ToggleButton active={viewMode === "grid"} onClick={() => setViewMode("grid")} icon={<LayoutGrid className="h-4 w-4" />} />
            <ToggleButton active={viewMode === "list"} onClick={() => setViewMode("list")} icon={<List className="h-4 w-4" />} />
          </div>
        </div>

        <div className="flex-1 min-h-0 overflow-y-auto pr-1 pb-4">
          {files.length === 0 ? (
            <EmptyState
              icon={<FolderOpen className="h-10 w-10 text-text-muted" />}
              title="No files uploaded yet"
              description="Drag and drop documents above or watch a folder to start building your knowledge base."
            />
          ) : (
            <div className={viewMode === "grid" ? "grid gap-4 md:grid-cols-2 xl:grid-cols-3" : "space-y-3"}>
              {files.map((file) => (
                <FileCard
                  key={file.id}
                  file={file}
                  viewMode={viewMode}
                  onDelete={onDelete}
                  onReprocess={onReprocess}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function UploadZone({
  onFilesDropped,
  queue,
  className,
}: {
  onFilesDropped: (files: File[]) => void;
  queue: UploadProgress[];
  className?: string;
}) {
  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop: onFilesDropped,
    accept: ACCEPT,
    maxSize: MAX_UPLOAD_SIZE,
    noClick: false,
  });

  return (
    <div className={cn("flex flex-col gap-3", className)}>
      <div
        {...getRootProps()}
        className={cn(
          "cursor-pointer rounded-2xl border border-dashed border-glass-border bg-surface-1/70 p-6 text-center transition-colors",
          isDragActive && "border-accent-primary/40 bg-accent-primary/10"
        )}
      >
        <input {...getInputProps()} />
        <div className="flex flex-col items-center justify-center min-h-[120px]">
          <Upload className={cn("mb-2 h-8 w-8", isDragActive ? "text-accent-primary" : "text-text-muted")} />
          <p className="text-sm font-medium text-text-primary">
            {isDragActive ? "Drop to upload" : "Drag & drop files"}
          </p>
          <p className="mt-1 text-xs text-text-muted">PDF, DOCX, XLSX, TXT, MD, PNG, JPG, WEBP · max 50 MB</p>
        </div>
      </div>

      <AnimatePresence initial={false}>
        {queue.map((item) => (
          <motion.div
            key={item.fileId}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.18 }}
          >
            <ProcessingPipeline stage={item.stage} originalName={item.originalName} uploadPct={item.uploadPct} />
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}

function FolderWatchPanel({
  watchers,
  onWatch,
  onStop,
}: {
  watchers: FolderWatcher[];
  onWatch: (path: string) => Promise<void>;
  onStop: (id: string) => Promise<void>;
}) {
  const [path, setPath] = useState("");
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState("");

  const handleAdd = async () => {
    const trimmed = path.trim();
    if (!trimmed) return;
    setAdding(true);
    setError("");
    try {
      await onWatch(trimmed);
      setPath("");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to watch folder");
    } finally {
      setAdding(false);
    }
  };

  return (
    <div className="w-full lg:w-72 shrink-0 flex flex-col gap-3 rounded-2xl border border-glass-border bg-surface-1/70 p-4">
      <div className="flex items-center gap-2">
        <FolderSearch className="h-4 w-4 text-accent-primary" />
        <span className="text-sm font-semibold text-text-primary">Folder Watch</span>
      </div>
      <p className="text-xs text-text-muted">
        Enter a local folder path. New files will be auto-ingested every 30 s.
      </p>

      <div className="flex items-center gap-2">
        <input
          value={path}
          onChange={(e) => setPath(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && void handleAdd()}
          placeholder="C:\Users\... or /home/..."
          className="min-w-0 flex-1 rounded-xl border border-glass-border bg-surface-2 px-3 py-1.5 text-xs text-text-primary outline-none placeholder:text-text-muted focus:border-accent-primary/40"
        />
        <button
          onClick={() => void handleAdd()}
          disabled={adding || !path.trim()}
          className="inline-flex items-center gap-1 rounded-xl bg-accent-primary/20 px-3 py-1.5 text-xs font-medium text-accent-primary hover:bg-accent-primary/30 disabled:opacity-50"
        >
          {adding ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Plus className="h-3.5 w-3.5" />}
          Watch
        </button>
      </div>

      {error && <p className="text-xs text-red-400">{error}</p>}

      {watchers.length > 0 && (
        <div className="space-y-2 mt-1">
          {watchers.map((w) => (
            <div
              key={w.id}
              className="flex items-center gap-2 rounded-xl border border-glass-border bg-surface-2 px-3 py-2"
            >
              <div className="min-w-0 flex-1">
                <p className="truncate text-xs font-medium text-text-primary" title={w.path}>{w.path}</p>
                <p className="text-[11px] text-text-muted">{w.file_count} files seen</p>
              </div>
              <button
                onClick={() => void onStop(w.id)}
                className="shrink-0 rounded-lg p-1 text-text-muted hover:text-status-error"
                title="Stop watching"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Tab 2: Search & Chat ──────────────────────────────────────────────────────

function SearchChatTab({ files }: { files: FileRecord[] }) {
  const [query, setQuery] = useState("");
  const [searching, setSearching] = useState(false);
  const [searchResults, setSearchResults] = useState<GlobalSearchResult[]>([]);
  const [showAllSearch, setShowAllSearch] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const abortRef = useRef<(() => void) | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const chatInputRef = useRef<HTMLInputElement>(null);

  // Debounced auto-search: fires 300 ms after the user stops typing
  useEffect(() => {
    const q = query.trim();
    if (!q) {
      setSearchResults([]);
      setShowAllSearch(false);
      return;
    }
    const timer = setTimeout(async () => {
      setSearching(true);
      try {
        const data = await searchGlobal(q, "files", 10);
        setSearchResults(data.results);
        setShowAllSearch(false);
      } catch (e) {
        console.error(e);
      } finally {
        setSearching(false);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [query]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const prevSelectedSize = useRef(0);
  useEffect(() => {
    if (selectedIds.size > 0 && prevSelectedSize.current === 0) {
      chatInputRef.current?.focus();
    }
    prevSelectedSize.current = selectedIds.size;
  }, [selectedIds.size]);

  const toggleSelect = (fileId: string) =>
    setSelectedIds((cur) => {
      const next = new Set(cur);
      next.has(fileId) ? next.delete(fileId) : next.add(fileId);
      return next;
    });

  const isSearchMode = query.trim().length > 0;
  const displayedSearchResults = showAllSearch ? searchResults : searchResults.slice(0, 5);
  const readyFiles = useMemo(() => files.filter((f) => f.status === "ready"), [files]);

  const selectAll = () => {
    if (isSearchMode) {
      setSelectedIds(new Set(searchResults.map((r) => r.file_id)));
    } else {
      setSelectedIds(new Set(readyFiles.map((f) => f.id)));
    }
  };
  const clearSelection = () => setSelectedIds(new Set());

  // Resolve names for the context bar from both file list and search results
  const selectedFileLabels = useMemo(
    () =>
      Array.from(selectedIds).map((id) => {
        const f = files.find((x) => x.id === id);
        if (f) return { id, name: f.original_name };
        const r = searchResults.find((x) => x.file_id === id);
        return { id, name: r?.original_name ?? id };
      }),
    [selectedIds, files, searchResults]
  );

  const handleChat = () => {
    const q = chatInput.trim();
    if (!q || streaming || selectedIds.size === 0) return;

    const userMsg: ChatMessage = { role: "user", content: q, timestamp: Date.now() };
    setMessages((cur) => [...cur, userMsg]);
    setChatInput("");
    setStreaming(true);

    const placeholder: ChatMessage = { role: "assistant", content: "", timestamp: Date.now() };
    setMessages((cur) => [...cur, placeholder]);

    let accumulated = "";
    abortRef.current = streamChatWithFiles(
      q,
      Array.from(selectedIds),
      "files",
      (token) => {
        accumulated += token;
        setMessages((cur) => {
          const updated = [...cur];
          updated[updated.length - 1] = { role: "assistant", content: accumulated, timestamp: Date.now() };
          return updated;
        });
      },
      () => setStreaming(false),
      (err) => {
        setMessages((cur) => {
          const updated = [...cur];
          updated[updated.length - 1] = { role: "assistant", content: `Error: ${err}`, timestamp: Date.now() };
          return updated;
        });
        setStreaming(false);
      }
    );
  };

  const stopStream = () => {
    abortRef.current?.();
    setStreaming(false);
  };

  const hasFiles = files.length > 0;
  const listCount = isSearchMode ? displayedSearchResults.length : files.length;

  return (
    <div className="h-full flex overflow-hidden">
      {/* ── Left panel: file browser + search ── */}
      <div className="w-72 shrink-0 flex flex-col border-r border-glass-border/50 overflow-hidden">
        {/* Search bar */}
        <div className="p-4 shrink-0 border-b border-glass-border/50">
          <div className="flex items-center gap-1.5 rounded-2xl border border-glass-border bg-surface-1/70 px-3 py-2 focus-within:border-accent-primary/40 transition-colors">
            {searching
              ? <Loader2 className="h-3.5 w-3.5 shrink-0 text-accent-primary animate-spin" />
              : <Search className="h-3.5 w-3.5 shrink-0 text-text-muted" />
            }
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={hasFiles ? "Search files…" : "Upload files first"}
              disabled={!hasFiles}
              className="min-w-0 flex-1 bg-transparent text-xs text-text-primary outline-none placeholder:text-text-muted disabled:opacity-50"
            />
            {query && (
              <button
                onClick={() => setQuery("")}
                className="shrink-0 text-text-muted hover:text-text-primary transition-colors"
              >
                <X className="h-3 w-3" />
              </button>
            )}
          </div>
        </div>

        {/* File list */}
        <div className="flex-1 min-h-0 overflow-y-auto">
          {!hasFiles ? (
            <div className="flex flex-col items-center justify-center h-full text-center p-6 gap-2">
              <FolderSearch className="h-8 w-8 text-text-muted/40" />
              <p className="text-xs text-text-muted">
                Upload documents in Data Management to get started
              </p>
            </div>
          ) : (
            <div className="p-3 flex flex-col gap-0">
              {/* header row */}
              <div className="flex items-center justify-between mb-2 px-1">
                <p className="text-[11px] text-text-muted">
                  {isSearchMode
                    ? (searching ? "Searching…" : `${searchResults.length} result${searchResults.length !== 1 ? "s" : ""}`)
                    : `${files.length} file${files.length !== 1 ? "s" : ""}`}
                </p>
                {(listCount > 0 || selectedIds.size > 0) && (
                  <div className="flex gap-2">
                    <button onClick={selectAll} className="text-[11px] text-accent-primary hover:underline">All</button>
                    <button onClick={clearSelection} className="text-[11px] text-text-muted hover:underline">None</button>
                  </div>
                )}
              </div>

              {isSearchMode ? (
                searching ? (
                  <div className="flex items-center justify-center py-6">
                    <Loader2 className="h-4 w-4 animate-spin text-text-muted" />
                  </div>
                ) : searchResults.length === 0 ? (
                  <p className="py-6 text-center text-xs text-text-muted">No files found</p>
                ) : (
                  <>
                    {displayedSearchResults.map((result) => (
                      <SearchResultCard
                        key={result.file_id}
                        result={result}
                        selected={selectedIds.has(result.file_id)}
                        onToggle={() => toggleSelect(result.file_id)}
                      />
                    ))}
                    {!showAllSearch && searchResults.length > 5 && (
                      <button
                        onClick={() => setShowAllSearch(true)}
                        className="mt-1 w-full rounded-xl border border-dashed border-glass-border py-2 text-xs text-text-muted hover:text-text-primary hover:border-glass-border/70 transition-colors"
                      >
                        Show {searchResults.length - 5} more
                      </button>
                    )}
                  </>
                )
              ) : (
                files.map((file) => (
                  <BrowseFileCard
                    key={file.id}
                    file={file}
                    selected={selectedIds.has(file.id)}
                    onToggle={() => toggleSelect(file.id)}
                  />
                ))
              )}
            </div>
          )}
        </div>
      </div>

      {/* ── Right panel: chat ── */}
      <div className="flex-1 min-w-0 flex flex-col overflow-hidden">
        {/* Selected files context bar */}
        <div className={cn(
          "shrink-0 border-b border-glass-border/50 transition-all duration-200",
          selectedIds.size > 0 ? "px-4 py-2.5" : "px-4 py-0 h-0 overflow-hidden border-b-0"
        )}>
          {selectedIds.size > 0 && (
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-[11px] font-semibold text-text-muted shrink-0">Context:</span>
              {selectedFileLabels.map((item) => (
                <span
                  key={item.id}
                  className="inline-flex items-center gap-1 rounded-full bg-accent-primary/15 border border-accent-primary/25 px-2 py-0.5 text-[11px] text-accent-primary"
                >
                  <span className="max-w-[120px] truncate">{item.name}</span>
                  <button
                    onClick={() => toggleSelect(item.id)}
                    className="shrink-0 text-accent-primary/60 hover:text-accent-primary"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </span>
              ))}
            </div>
          )}
        </div>

        {/* Messages */}
        <div className="flex-1 min-h-0 overflow-y-auto p-4 space-y-3">
          {messages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center gap-3">
              <div className={cn(
                "rounded-2xl border p-6 max-w-xs transition-colors",
                selectedIds.size > 0
                  ? "border-accent-primary/20 bg-accent-primary/5"
                  : "border-dashed border-glass-border bg-surface-1/40"
              )}>
                <MessageSquare className={cn(
                  "h-8 w-8 mb-3 mx-auto",
                  selectedIds.size > 0 ? "text-accent-primary/60" : "text-text-muted"
                )} />
                <p className="text-sm font-medium text-text-primary mb-1">
                  {selectedIds.size > 0 ? "Ready to chat" : "Select files to start"}
                </p>
                <p className="text-xs text-text-muted leading-relaxed">
                  {selectedIds.size > 0
                    ? `${selectedIds.size} file${selectedIds.size !== 1 ? "s" : ""} loaded into context. Ask anything about them.`
                    : hasFiles
                    ? "Pick files from the list on the left, then ask anything about them."
                    : "Upload documents first, then select them here to chat."}
                </p>
              </div>
            </div>
          ) : (
            messages.map((msg, i) => <ChatBubble key={i} message={msg} />)
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="shrink-0 p-4 pt-0">
          <div className={cn(
            "flex items-center gap-2 rounded-2xl border bg-surface-1/70 px-3 py-2 transition-colors",
            selectedIds.size > 0
              ? "border-accent-primary/30 ring-1 ring-accent-primary/10"
              : "border-glass-border"
          )}>
            <input
              ref={chatInputRef}
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleChat();
                }
              }}
              placeholder={
                selectedIds.size === 0
                  ? "← Select files on the left first…"
                  : "Ask a question about the selected files…"
              }
              disabled={selectedIds.size === 0 || streaming}
              className="flex-1 bg-transparent text-sm text-text-primary outline-none placeholder:text-text-muted disabled:opacity-50"
            />
            {streaming ? (
              <button
                onClick={stopStream}
                className="shrink-0 inline-flex items-center gap-1 rounded-xl border border-red-500/30 bg-red-500/10 px-2.5 py-1.5 text-[11px] font-medium text-red-400 hover:bg-red-500/20"
              >
                <X className="h-3.5 w-3.5" />
                Stop
              </button>
            ) : (
              <button
                onClick={handleChat}
                disabled={selectedIds.size === 0 || !chatInput.trim()}
                className="shrink-0 rounded-xl bg-accent-primary/20 p-2 text-accent-primary hover:bg-accent-primary/30 disabled:opacity-40"
              >
                <Send className="h-4 w-4" />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Sub-components ─────────────────────────────────────────────────────────────

function SearchResultCard({
  result,
  selected,
  onToggle,
}: {
  result: GlobalSearchResult;
  selected: boolean;
  onToggle: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const scorePct = Math.round(Math.min(1, Math.max(0, result.score)) * 100);

  return (
    <motion.div layout>
      <button
        type="button"
        onClick={onToggle}
        className={cn(
          "w-full text-left rounded-xl border px-3 py-2.5 mb-1 transition-all duration-150",
          selected
            ? "border-accent-primary/50 bg-accent-primary/10 ring-1 ring-accent-primary/15"
            : "border-transparent hover:border-glass-border hover:bg-surface-1/70"
        )}
      >
        <div className="flex items-center gap-2.5">
          {/* Checkbox */}
          <div className={cn(
            "h-4 w-4 shrink-0 rounded border-2 flex items-center justify-center transition-colors",
            selected
              ? "border-accent-primary bg-accent-primary"
              : "border-glass-border bg-transparent"
          )}>
            {selected && (
              <svg className="h-2.5 w-2.5 text-white" viewBox="0 0 10 10" fill="none">
                <path d="M2 5l2.5 2.5L8 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            )}
          </div>

          {/* File info */}
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-1.5">
              <span className="truncate text-xs font-medium text-text-primary" title={result.original_name}>
                {result.original_name || result.file_id}
              </span>
              <span className={cn(
                "shrink-0 rounded-full px-1.5 py-px text-[10px] font-medium leading-none",
                result.source === "graph"
                  ? "bg-violet-500/15 text-violet-400"
                  : "bg-emerald-500/15 text-emerald-400"
              )}>
                {result.source === "graph" ? "KG" : `${scorePct}%`}
              </span>
            </div>
          </div>
        </div>

        {/* Summary peek */}
        {result.summary && (
          <div className="mt-1.5 pl-6">
            <p className={cn("text-[11px] text-text-muted leading-[1.4]", !expanded && "line-clamp-2")}>
              {result.summary}
            </p>
            {result.summary.length > 100 && (
              <button
                type="button"
                onClick={(e) => { e.stopPropagation(); setExpanded(!expanded); }}
                className="mt-0.5 text-[10px] text-accent-primary/70 hover:text-accent-primary"
              >
                {expanded ? "Less" : "More"}
              </button>
            )}
          </div>
        )}

        {/* Entity tags */}
        {result.entities.length > 0 && (
          <div className="mt-1.5 pl-6 flex flex-wrap gap-1">
            {result.entities.slice(0, 3).map((e) => (
              <span key={e.name} className="rounded-full bg-surface-2 px-1.5 py-px text-[10px] text-text-muted">
                {e.name}
              </span>
            ))}
            {result.entities.length > 3 && (
              <span className="text-[10px] text-text-muted">+{result.entities.length - 3}</span>
            )}
          </div>
        )}
      </button>
    </motion.div>
  );
}

function BrowseFileCard({
  file,
  selected,
  onToggle,
}: {
  file: FileRecord;
  selected: boolean;
  onToggle: () => void;
}) {
  const canSelect = file.status === "ready";
  return (
    <button
      type="button"
      onClick={canSelect ? onToggle : undefined}
      disabled={!canSelect}
      className={cn(
        "w-full text-left rounded-xl border px-3 py-2.5 mb-1 transition-all duration-150",
        selected
          ? "border-accent-primary/50 bg-accent-primary/10 ring-1 ring-accent-primary/15"
          : canSelect
          ? "border-transparent hover:border-glass-border hover:bg-surface-1/70"
          : "border-transparent opacity-50 cursor-not-allowed"
      )}
    >
      <div className="flex items-center gap-2.5">
        <div className={cn(
          "h-4 w-4 shrink-0 rounded border-2 flex items-center justify-center transition-colors",
          selected ? "border-accent-primary bg-accent-primary" : "border-glass-border bg-transparent"
        )}>
          {selected && (
            <svg className="h-2.5 w-2.5 text-white" viewBox="0 0 10 10" fill="none">
              <path d="M2 5l2.5 2.5L8 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          )}
        </div>
        <div className="min-w-0 flex-1">
          <span className="block truncate text-xs font-medium text-text-primary" title={file.original_name}>
            {file.original_name}
          </span>
          <span className="text-[10px] text-text-muted">
            {formatBytes(file.size_bytes)}{file.chunk_count > 0 ? ` · ${file.chunk_count} chunks` : ""}
          </span>
        </div>
        {file.status !== "ready" && <StatusPill status={file.status} />}
      </div>
    </button>
  );
}

function ChatBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  return (
    <div className={cn("flex", isUser ? "justify-end" : "justify-start")}>
      <div className={cn(
        "max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed",
        isUser
          ? "bg-accent-primary/20 text-text-primary rounded-tr-sm"
          : "bg-surface-2 text-text-primary rounded-tl-sm"
      )}>
        {message.content || <span className="animate-pulse text-text-muted">▋</span>}
      </div>
    </div>
  );
}

function FileCard({
  file,
  viewMode,
  onDelete,
  onReprocess,
}: {
  file: FileRecord;
  viewMode: ViewMode;
  onDelete: (fileId: string) => Promise<void>;
  onReprocess: (fileId: string) => Promise<void>;
}) {
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [reprocessing, setReprocessing] = useState(false);
  const fileIcon = getFileIcon(file.mime_type);
  const FileTypeIcon = fileIcon.icon;
  const processingErrorMsg = typeof file.metadata?.error_message === "string" ? file.metadata.error_message : null;

  const handleDelete = async (e: { stopPropagation: () => void }) => {
    e.stopPropagation();
    setDeleting(true);
    setDeleteError(null);
    try {
      await onDelete(file.id);
      // Card will unmount as file list refreshes — no need to reset deleting
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : "Delete failed — check backend logs");
      setDeleting(false);
    }
  };

  const handleReprocess = async (e: React.MouseEvent) => {
    e.stopPropagation();
    setReprocessing(true);
    try {
      await onReprocess(file.id);
    } finally {
      setReprocessing(false);
    }
  };

  return (
    <motion.article
      layout
      whileHover={{ y: -1 }}
      className={cn(
        "rounded-2xl border border-glass-border bg-surface-1/70 p-4 shadow-sm",
        deleteError && "border-red-500/30",
        viewMode === "list" && "flex items-center gap-4"
      )}
    >
      <div className={cn("flex items-start gap-3", viewMode === "list" && "flex-1")}>
        <div className={cn("flex h-10 w-10 shrink-0 items-center justify-center rounded-xl", fileIcon.wrapper)}>
          <FileTypeIcon className={cn("h-4.5 w-4.5", fileIcon.iconClass)} />
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <h4 className="truncate text-sm font-semibold text-text-primary">{file.original_name}</h4>
              <p className="text-xs text-text-muted">{formatBytes(file.size_bytes)}</p>
            </div>
            <StatusPill status={file.status} />
          </div>

          <div className="mt-2 flex flex-wrap gap-1.5 text-[11px] text-text-muted">
            <span className="rounded-full bg-surface-2 px-2 py-0.5">{file.chunk_count} chunks</span>
            <span className="rounded-full bg-surface-2 px-2 py-0.5">{file.collection}</span>
          </div>

          {file.status === "error" && processingErrorMsg && !deleteError && (
            <p className="mt-1.5 text-[11px] text-red-400/70 leading-snug line-clamp-2">{processingErrorMsg}</p>
          )}
          {deleteError && (
            <p className="mt-1.5 text-[11px] text-red-400 leading-snug line-clamp-3" title={deleteError}>
              Delete failed: {deleteError}
            </p>
          )}
        </div>
      </div>

      <div className={cn("mt-3 flex items-center justify-end gap-2", viewMode === "list" && "mt-0")}>
        {file.status === "error" && (
          <motion.button
            whileTap={{ scale: 0.95 }}
            onClick={(e) => void handleReprocess(e)}
            disabled={reprocessing}
            className="inline-flex items-center gap-1.5 rounded-xl border border-violet-500/30 bg-violet-500/10 px-3 py-1.5 text-xs font-medium text-violet-300 hover:bg-violet-500/20 disabled:opacity-50"
          >
            <RefreshCw className={cn("h-3.5 w-3.5", reprocessing && "animate-spin")} />
            {reprocessing ? "Retrying…" : "Retry"}
          </motion.button>
        )}
        <motion.button
          whileTap={{ scale: 0.95 }}
          onClick={(e) => void handleDelete(e)}
          disabled={deleting}
          className="inline-flex items-center gap-1.5 rounded-xl border border-glass-border bg-surface-2 px-3 py-1.5 text-xs font-medium text-text-muted hover:text-status-error disabled:opacity-50"
        >
          {deleting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
          {deleting ? "Deleting…" : "Delete"}
        </motion.button>
      </div>
    </motion.article>
  );
}

// ── Shared utility components ──────────────────────────────────────────────────

function MainTabButton({
  active,
  onClick,
  icon,
  label,
}: {
  active: boolean;
  onClick: () => void;
  icon: ReactNode;
  label: string;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-2 border-b-2 px-5 py-3 text-sm font-medium transition-colors",
        active
          ? "border-accent-primary text-text-primary"
          : "border-transparent text-text-muted hover:text-text-primary"
      )}
    >
      {icon}
      {label}
    </button>
  );
}

function ToggleButton({ active, onClick, icon }: { active: boolean; onClick: () => void; icon: ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "rounded-xl p-2 transition-colors",
        active ? "bg-accent-primary/20 text-accent-primary" : "text-text-muted hover:text-text-primary"
      )}
    >
      {icon}
    </button>
  );
}

function StatusPill({ status }: { status: FileRecord["status"] }) {
  const map = {
    pending: "bg-amber-500/10 text-amber-600 ring-amber-500/20",
    processing: "bg-accent-primary/10 text-accent-primary ring-accent-primary/25 animate-pulse",
    ready: "bg-emerald-500/10 text-emerald-600 ring-emerald-500/20",
    error: "bg-red-500/10 text-red-600 ring-red-500/20",
  } as const;
  return (
    <span className={cn("rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset", map[status])}>
      {status}
    </span>
  );
}

function EmptyState({ icon, title, description }: { icon: ReactNode; title: string; description: string }) {
  return (
    <div className="flex h-full min-h-[160px] flex-col items-center justify-center rounded-2xl border border-dashed border-glass-border bg-surface-1/60 p-8 text-center">
      {icon}
      <h4 className="mt-3 text-base font-semibold text-text-primary">{title}</h4>
      <p className="mt-1 max-w-md text-sm text-text-muted">{description}</p>
    </div>
  );
}

function getFileIcon(mimeType: string) {
  if (mimeType === "application/pdf")
    return { icon: FileText, wrapper: "bg-red-500/10", iconClass: "text-red-500" };
  if (mimeType.includes("wordprocessingml"))
    return { icon: FileText, wrapper: "bg-blue-500/10", iconClass: "text-blue-500" };
  if (mimeType.includes("spreadsheet"))
    return { icon: FileSpreadsheet, wrapper: "bg-emerald-500/10", iconClass: "text-emerald-500" };
  if (mimeType.startsWith("image/"))
    return { icon: ImageIcon, wrapper: "bg-violet-500/10", iconClass: "text-violet-500" };
  return { icon: FileIcon, wrapper: "bg-surface-2", iconClass: "text-text-muted" };
}

function formatBytes(bytes: number) {
  if (!Number.isFinite(bytes) || bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB"];
  let value = bytes / 1024;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) { value /= 1024; unit++; }
  return `${value.toFixed(value >= 10 ? 0 : 1)} ${units[unit]}`;
}
