import type { FileRecord, FolderWatcher, GlobalSearchResult, SearchResult } from "@/types/files";

const API_BASE = "http://localhost:8000";

export async function uploadFile(
  file: File,
  collection = "files",
  onProgress?: (pct: number) => void
): Promise<{ file_id: string; status: string; original_name: string }> {
  return new Promise((resolve, reject) => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("collection", collection);

    const xhr = new XMLHttpRequest();
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress?.(Math.round((e.loaded / e.total) * 100));
    };
    xhr.onload = () =>
      xhr.status === 200
        ? resolve(JSON.parse(xhr.responseText))
        : reject(new Error(`Upload failed: ${xhr.status}`));
    xhr.onerror = () => reject(new Error("Network error"));
    xhr.open("POST", `${API_BASE}/api/files/upload`);
    xhr.send(formData);
  });
}

export async function listFiles(collection?: string): Promise<FileRecord[]> {
  const url = collection
    ? `${API_BASE}/api/files/?collection=${collection}`
    : `${API_BASE}/api/files/`;
  const res = await fetch(url);
  const data = await res.json();
  return data.data ?? [];
}

export async function getFileStatus(fileId: string): Promise<Pick<FileRecord, "status" | "chunk_count">> {
  const res = await fetch(`${API_BASE}/api/files/${fileId}/status`);
  return res.json();
}

export async function deleteFile(fileId: string): Promise<void> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/api/files/${fileId}`, { method: "DELETE" });
  } catch (networkErr) {
    throw new Error(
      `Cannot reach the backend at ${API_BASE}. Is it running? (${networkErr instanceof Error ? networkErr.message : networkErr})`
    );
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body?.detail ?? `Delete failed: HTTP ${res.status}`);
  }
}

export async function searchFiles(
  query: string,
  collection = "files",
  n = 5
): Promise<{ chunks: SearchResult[]; query: string }> {
  const res = await fetch(
    `${API_BASE}/api/files/search?q=${encodeURIComponent(query)}&collection=${collection}&n=${n}`
  );
  return res.json();
}

export async function searchGlobal(
  query: string,
  collection = "files",
  n = 10
): Promise<{ results: GlobalSearchResult[]; query: string }> {
  const res = await fetch(
    `${API_BASE}/api/files/search-global?q=${encodeURIComponent(query)}&collection=${collection}&n=${n}`
  );
  if (!res.ok) throw new Error(`Global search failed: ${res.status}`);
  return res.json();
}

export async function reprocessFile(fileId: string): Promise<{ file_id: string; status: string }> {
  const res = await fetch(`${API_BASE}/api/files/${fileId}/reprocess`, { method: "POST" });
  if (!res.ok) throw new Error(`Reprocess failed: ${res.status}`);
  return res.json();
}

export async function watchFolder(
  path: string,
  collection = "files"
): Promise<{ watcher_id: string; path: string; status: string }> {
  const res = await fetch(`${API_BASE}/api/files/watch-folder`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path, collection }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? "Watch folder failed");
  }
  return res.json();
}

export async function stopWatchingFolder(watcherId: string): Promise<void> {
  await fetch(`${API_BASE}/api/files/watch-folder/${watcherId}`, { method: "DELETE" });
}

export async function listWatchedFolders(): Promise<FolderWatcher[]> {
  const res = await fetch(`${API_BASE}/api/files/watched-folders`);
  const data = await res.json();
  return data.watchers ?? [];
}

/**
 * Stream a chat response grounded in specific files.
 * Calls the callback with each token as it arrives.
 * Returns a cleanup function to abort the stream.
 */
export function streamChatWithFiles(
  query: string,
  fileIds: string[],
  collection: string,
  onToken: (token: string) => void,
  onDone: () => void,
  onError: (err: string) => void
): () => void {
  const controller = new AbortController();

  (async () => {
    try {
      const res = await fetch(`${API_BASE}/api/files/chat-context`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, file_ids: fileIds, collection, n_results: 5 }),
        signal: controller.signal,
      });

      if (!res.ok || !res.body) {
        onError(`Request failed: ${res.status}`);
        return;
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (!line.startsWith("data:")) continue;
          const data = line.slice(5).trim();
          if (data === "[DONE]") {
            onDone();
            return;
          }
          try {
            const parsed = JSON.parse(data);
            if (parsed.token) onToken(parsed.token);
            if (parsed.error) onError(parsed.error);
          } catch {
            // ignore malformed SSE frames
          }
        }
      }
      onDone();
    } catch (err: unknown) {
      if (err instanceof Error && err.name !== "AbortError") {
        onError(err.message);
      }
    }
  })();

  return () => controller.abort();
}
