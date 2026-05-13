"""Vector Store Implementation for Nexus OS using ChromaDB + HuggingFace embeddings."""

import asyncio
import logging
from collections import Counter
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

try:
    import chromadb
except ImportError:  # pragma: no cover - optional runtime dependency
    chromadb = None

    class _MemoryCollection:
        def __init__(self, name: str):
            self.name = name
            self._docs: dict[str, dict[str, Any]] = {}

        def upsert(self, documents: list[str], ids: list[str], metadatas: list[dict] | None = None):
            metadatas = metadatas or [{} for _ in documents]
            for doc, doc_id, metadata in zip(documents, ids, metadatas):
                self._docs[doc_id] = {"document": doc, "metadata": metadata or {}}

        def get(
            self,
            include: list[str] | None = None,
            limit: int | None = None,
            offset: int | None = None,
            where: dict[str, Any] | None = None,
        ):
            include = include or ["documents", "metadatas"]
            ids = list(self._docs.keys())
            if where:
                def _matches(doc_id: str) -> bool:
                    metadata = self._docs[doc_id]["metadata"]
                    return all(metadata.get(key) == value for key, value in where.items())
                ids = [doc_id for doc_id in ids if _matches(doc_id)]
            start = offset or 0
            end = start + limit if limit is not None else None
            ids = ids[start:end]
            documents = [self._docs[_id]["document"] for _id in ids]
            metadatas = [self._docs[_id]["metadata"] for _id in ids]
            result = {"ids": ids}
            if "documents" in include:
                result["documents"] = documents
            if "metadatas" in include:
                result["metadatas"] = metadatas
            return result

        def query(self, query_texts: list[str], n_results: int, include: list[str] | None = None):
            query_text = query_texts[0].lower() if query_texts else ""
            query_tokens = Counter(query_text.split())
            scored = []
            for doc_id, payload in self._docs.items():
                doc_text = payload["document"]
                doc_tokens = Counter(doc_text.lower().split())
                overlap = sum(min(query_tokens[token], doc_tokens[token]) for token in query_tokens)
                denom = max(sum(doc_tokens.values()), 1)
                distance = 1.0 - min(overlap / denom, 1.0)
                scored.append((doc_id, doc_text, payload["metadata"], distance))
            scored.sort(key=lambda item: item[3])
            scored = scored[:n_results]
            return {
                "ids": [[item[0] for item in scored]],
                "documents": [[item[1] for item in scored]],
                "metadatas": [[item[2] for item in scored]],
                "distances": [[item[3] for item in scored]],
            }

        def delete(self, where: dict[str, Any] | None = None):
            if where and "file_id" in where:
                target = where["file_id"]
                self._docs = {
                    doc_id: payload
                    for doc_id, payload in self._docs.items()
                    if payload["metadata"].get("file_id") != target
                }
            else:
                self._docs.clear()

    class _MemoryClient:
        def __init__(self, path: str | None = None):
            self.path = path
            self._collections: dict[str, _MemoryCollection] = {}

        def list_collections(self):
            return [type("CollectionInfo", (), {"name": name})() for name in self._collections]

        def get_or_create_collection(self, name: str, metadata: dict | None = None, embedding_function: Any | None = None):
            if name not in self._collections:
                self._collections[name] = _MemoryCollection(name)
            return self._collections[name]

    class _ChromadbShim:
        PersistentClient = _MemoryClient
        EmbeddingFunction = object
        Collection = _MemoryCollection
        Embeddings = list

    chromadb = _ChromadbShim()  # type: ignore[assignment]

from backend.config import settings
from backend.core.resilience import EmbeddingUnavailable, is_chromadb_locked


class HuggingFaceEmbeddingFunction(chromadb.EmbeddingFunction):
    """Local HuggingFace embedding function using raw transformers — no wrappers.

    Loads the model once on first call (lazy init), then runs all future batches
    on the cached model. Automatically uses CUDA when available, otherwise CPU.

    Recommended model: ``BAAI/bge-m3``
    - 1024-dim dense embeddings, 8192-token context window
    - CLS-token pooling + L2 normalisation
    - No query/document prefix required (safe for ChromaDB's symmetric call pattern)
    - ~570 MB download, MIT licence

    Args:
        model_id:          HuggingFace repo id (default: ``BAAI/bge-m3``).
        cache_dir:         Local directory to cache downloaded model weights.
        batch_size:        Texts per forward pass (default 32).
        max_length:        Token truncation limit (default 8192 for bge-m3, 512 for others).
        pooling_strategy:  ``"cls"`` — use the [CLS] token (recommended for BGE models);
                           ``"mean"`` — average all non-padding tokens.
        trust_remote_code: Set ``True`` for models that ship custom model code
                           (e.g. nomic-embed-text-v1.5). Not needed for bge-m3.
    """

    def __init__(
        self,
        model_id: str,
        cache_dir: str | None = None,
        batch_size: int = 32,
        max_length: int = 8192,
        pooling_strategy: str = "cls",
        trust_remote_code: bool = False,
    ) -> None:
        if pooling_strategy not in ("cls", "mean"):
            raise ValueError(f"pooling_strategy must be 'cls' or 'mean', got {pooling_strategy!r}")
        self._model_id = model_id
        self._cache_dir = cache_dir
        self._batch_size = batch_size
        self._max_length = max_length
        self._pooling_strategy = pooling_strategy
        self._trust_remote_code = trust_remote_code
        self._tokenizer: Any = None
        self._model: Any = None
        self._device: str | None = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Lazy-load the tokenizer and model on first call."""
        if self._model is not None:
            return

        try:
            import torch
            from transformers import AutoModel, AutoTokenizer
        except ImportError as exc:
            raise RuntimeError(
                "torch and transformers are required for HuggingFace embeddings. "
                "Run: conda run -n Command pip install torch transformers"
            ) from exc

        logger.info("Loading HuggingFace embedding model: %s", self._model_id)

        self._device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info("Embedding device: %s", self._device)

        try:
            self._tokenizer = AutoTokenizer.from_pretrained(
                self._model_id,
                cache_dir=self._cache_dir,
                trust_remote_code=self._trust_remote_code,
            )
            self._model = AutoModel.from_pretrained(
                self._model_id,
                cache_dir=self._cache_dir,
                trust_remote_code=self._trust_remote_code,
            ).to(self._device)
        except (OSError, RuntimeError, ValueError) as exc:
            raise EmbeddingUnavailable(f"Embedding model unavailable: {exc}") from exc
        self._model.eval()

        logger.info(
            "HuggingFace embedding model ready — device=%s  pooling=%s  model=%s",
            self._device,
            self._pooling_strategy,
            self._model_id,
        )

    @staticmethod
    def _cls_pool(last_hidden_state: Any) -> Any:
        """Return the [CLS] token embedding (index 0)."""
        return last_hidden_state[:, 0]

    @staticmethod
    def _mean_pool(last_hidden_state: Any, attention_mask: Any) -> Any:
        """Average non-padding token embeddings."""
        import torch

        mask = attention_mask.unsqueeze(-1).expand(last_hidden_state.size()).float()
        return torch.sum(last_hidden_state * mask, dim=1) / torch.clamp(mask.sum(dim=1), min=1e-9)

    # ------------------------------------------------------------------
    # ChromaDB EmbeddingFunction interface
    # ------------------------------------------------------------------

    def __call__(self, input: list[str]) -> chromadb.Embeddings:  # noqa: A002
        """Embed a list of text strings and return L2-normalised vectors.

        Args:
            input: List of text strings to embed.

        Returns:
            List of float lists, shape ``(len(input), embedding_dim)``.
        """
        if not input:
            return []

        # Guard against empty strings that ChromaDB occasionally passes
        texts = [t if t else " " for t in input]

        self._load()

        import torch
        import torch.nn.functional as F

        all_embeddings: list[list[float]] = []

        for batch_start in range(0, len(texts), self._batch_size):
            batch = texts[batch_start : batch_start + self._batch_size]

            encoded = self._tokenizer(
                batch,
                padding=True,
                truncation=True,
                max_length=self._max_length,
                return_tensors="pt",
            ).to(self._device)

            with torch.no_grad():
                output = self._model(**encoded)

            if self._pooling_strategy == "cls":
                pooled = self._cls_pool(output.last_hidden_state)
            else:
                pooled = self._mean_pool(output.last_hidden_state, encoded["attention_mask"])

            normalised = F.normalize(pooled, p=2, dim=1)
            all_embeddings.extend(normalised.cpu().tolist())

        return all_embeddings


class VectorStore:
    """Vector store using ChromaDB with local HuggingFace embeddings (BAAI/bge-m3).

    Provides persistent storage and retrieval of document chunks with semantic search.
    Embeddings are computed 100% locally via ``HuggingFaceEmbeddingFunction`` —
    no LM Studio, no Ollama, no external API calls required.

    Collections:
        - "files": Document chunks indexed by file ID for quick lookup/deletion
        - "research": Research notes and findings
        - "journal": Personal journal entries
        - "memory": User memories, preferences, learned information
    """

    COLLECTIONS = ["files", "research", "journal", "memory"]
    COLLECTIONS_PREFIX: str | None = settings.CHROMA_COLLECTION_PREFIX or None

    def __init__(self, persist_dir: str) -> None:  # noqa: D107
        self.persist_path = Path(persist_dir).expanduser().resolve()
        self._client: chromadb.PersistentClient | None = None
        self._embed_function: HuggingFaceEmbeddingFunction | None = None

    @property
    def _chroma_client(self) -> chromadb.PersistentClient:  # noqa: D107
        if self._client is None:
            self._client = chromadb.PersistentClient(path=str(self.persist_path))
        return self._client

    @property
    def _embedding_function(self) -> HuggingFaceEmbeddingFunction:
        """Lazy-initialize the local HuggingFace embedding function.

        Settings are driven by config.py:
          - HF_EMBEDDING_MODEL_ID  (default: BAAI/bge-m3)
          - HF_EMBEDDING_CACHE_DIR (default: data/embeddings/hf_cache)

        bge-m3 uses CLS pooling and supports up to 8192 tokens, so we pass
        those as defaults. Override in config if you swap to a different model.
        """
        if self._embed_function is None:
            self._embed_function = HuggingFaceEmbeddingFunction(
                model_id=settings.HF_EMBEDDING_MODEL_ID,
                cache_dir=str(settings.HF_EMBEDDING_CACHE_DIR),
                batch_size=32,
                max_length=8192,
                pooling_strategy="cls",
                trust_remote_code=False,
            )
        return self._embed_function

    async def initialize(self) -> None:  # noqa: D107
        """Called during app lifespan startup. Creates PersistentClient and all collections."""
        try:
            client = self._chroma_client

            # Create default collection (optional - you may want this for general memory)
            existing_collections = list(client.list_collections())
            default_collection_name = f"{self.COLLECTIONS_PREFIX}_default" if self.COLLECTIONS_PREFIX else "default"
            has_default = any(col.name == default_collection_name for col in existing_collections)
            if not has_default:
                client.get_or_create_collection(
                    name=default_collection_name,
                    metadata={"description": "General-purpose vector store"},
                    embedding_function=self._embedding_function,
                )

            # Create all standard collections
            for collection_name in self.COLLECTIONS:
                collection_metadata = {
                    "type": "nexus",  # Tag for Nexus OS collections
                    "category": collection_name,  # For filtering/queries
                }

                self.get_collection(collection_name)

            return None

        except Exception as e:  # noqa: BLE001 - broad catch for startup resilience
            print(f"Warning: Failed to initialize vector store at {self.persist_path}: {e}")  # noqa: T201
            raise RuntimeError(f"Failed to initialize ChromaDB: {e}") from e

    def get_collection(self, name: str) -> chromadb.Collection:  # noqa: D107
        """Get or create a named collection.

        Args:
            name: Collection name (must be one of COLLECTIONS).

        Returns:
            ChromaDB Collection object for querying/upserting.
        """
        if not self._client:
            raise RuntimeError("VectorStore must be initialized before use")  # noqa: TRY003

        collection_name = f"{self.COLLECTIONS_PREFIX}_{name}" if self.COLLECTIONS_PREFIX else name
        return self._chroma_client.get_or_create_collection(
            name=collection_name,
            embedding_function=self._embedding_function,
        )

    async def upsert_chunks(
        self,
        collection_name: str,
        chunks: list[dict],  # {"id": str, "text": str, "metadata": dict}
    ) -> None:
        """Upsert (insert or update) document chunks into a collection.

        Args:
            collection_name: Name of the collection to store chunks in.
            chunks: List of chunk dictionaries with 'id', 'text', and optional 'metadata'.
                    - id: Unique identifier for this chunk (used for updates/deletions).
                    - text: The actual text content to embed.
                    - metadata: Optional dictionary of additional context (e.g., source file, date).

        Returns:
            None
        """
        if not self._client:
            raise RuntimeError("VectorStore must be initialized before use")  # noqa: TRY003

        if not chunks:
            return None

        collection = self.get_collection(collection_name)

        ids = [chunk["id"] for chunk in chunks]
        texts = [chunk["text"] for chunk in chunks]
        metadata_list = []

        for chunk in chunks:
            meta = dict(chunk.get("metadata", {}) or {})
            # Always include the Nexus OS collection type and category as metadata
            if "type" not in meta:
                meta["type"] = "nexus"
            if "category" not in meta:
                meta["category"] = collection_name

            metadata_list.append(meta)

        for attempt in range(1, 4):
            try:
                collection.upsert(
                    documents=texts,
                    ids=ids,
                    metadatas=metadata_list if metadata_list else None,
                )
                return None
            except Exception as exc:
                if is_chromadb_locked(exc) and attempt < 3:
                    logger.warning(
                        "ChromaDB upsert locked; retrying",
                        extra={"collection": collection_name, "attempt": attempt, "error": str(exc)},
                    )
                    await asyncio.sleep(0.2)
                    continue
                raise EmbeddingUnavailable(f"ChromaDB upsert failed for {collection_name}: {exc}") from exc

    async def query(
        self,
        collection_name: str,
        query_text: str,
        n_results: int = 10,
    ) -> list[dict]:
        """Query the vector store for semantically similar chunks.

        Args:
            collection_name: Name of the collection to search.
            query_text: The text to find similar content for.
            n_results: Number of results to return (default 10).

        Returns:
            List of dictionaries with keys: id, text, metadata, distance.
            Sorted by distance (lower = more similar) in ascending order.
        """
        if not self._client:
            raise RuntimeError("VectorStore must be initialized before use")  # noqa: TRY003

        collection = self.get_collection(collection_name)

        for attempt in range(1, 4):
            try:
                results = collection.query(
                    query_texts=[query_text],
                    n_results=n_results,
                    include=["documents", "metadatas", "distances"],
                )
                break
            except Exception as exc:
                if is_chromadb_locked(exc) and attempt < 3:
                    logger.warning(
                        "ChromaDB query locked; retrying",
                        extra={"collection": collection_name, "attempt": attempt, "error": str(exc)},
                    )
                    await asyncio.sleep(0.2)
                    continue
                raise EmbeddingUnavailable(f"ChromaDB query failed for {collection_name}: {exc}") from exc
        else:
            return []

        documents = results["documents"][0] or []
        metadatas = results["metadatas"][0] or [{}] * len(documents)
        distances = results["distances"][0] or [1.0] * len(documents)
        ids = results["ids"][0] or []

        # Combine into result list, handling missing metadata gracefully
        query_results: list[dict] = []
        for i in range(len(documents)):
            if documents[i]:
                query_results.append({
                    "id": ids[i] if len(ids) > i else documents[i],
                    "text": documents[i],  # Chroma stores texts as "documents"
                    "metadata": metadatas[i] if metadatas and len(metadatas) > i else {},
                    "distance": float(distances[i]) if distances else 1.0,
                })

        return query_results

    async def delete_by_file_id(
        self, collection_name: str, file_id: str
    ) -> None:
        """Delete all chunks associated with a specific file ID from a collection.

        Uses the 'type' and 'category' metadata fields created during upsert_chunks()
        to identify Nexus OS documents for deletion.

        Args:
            collection_name: Name of the collection to search in.
            file_id: The file ID to delete chunks by (must match 'id' field in chunks).
        """
        if not self._client:
            raise RuntimeError("VectorStore must be initialized before use")  # noqa: TRY003

        collection = self.get_collection(collection_name)

        try:
            collection.delete(where={"file_id": file_id})
        except Exception as e:  # noqa: BLE001 - broad catch for resilience
            print(f"Warning: Failed to delete chunks by file_id={file_id}: {e}")  # noqa: T201


# Module-level exports for dependency injection / lazy initialization
vector_store: VectorStore | None = None

_async_vector_store_lock: asyncio.Lock = asyncio.Lock()


async def init_vector_store(
    settings_override=None,  # Optional settings override (defaults to module-level import)
    persist_path: str | None = None,  # Override path for testing (default: use CHROMA_PERSIST_DIR from settings)
) -> VectorStore:
    """Initialize and return the global vector store instance.

    This is a convenience function that creates a new VectorStore instance
    using settings.CHROMA_PERSIST_DIR and assigns it to the module-level
    `vector_store` variable for easy access throughout the application.

    Usage:
        # During app lifespan startup (FastAPI lifespan event)
        vector_store = await init_vector_store()
        await vector_store.initialize()

        # Or call this function directly anywhere
        vs = await init_vector_store()

        # For testing - override the persist path
        vs = await init_vector_store(persist_path="./data/chroma_test")

    Args:
        settings: Optional Settings object for CHROMA_PERSIST_DIR. If None,
                  uses the module-level imported settings from config.py.
        persist_path: Override the persistence directory (for testing). Defaults to
                     using CHROMA_PERSIST_DIR from settings if provided.

    Returns:
        VectorStore instance ready for use.
    """
    global vector_store

    # Use provided persist_path if set (for testing), otherwise use CHROMA_PERSIST_DIR from settings
    if persist_path is not None:
        final_persist_dir = persist_path
    else:
        effective_settings = settings_override or settings
        final_persist_dir = str(effective_settings.CHROMA_PERSIST_DIR)

    async with _async_vector_store_lock:
        if vector_store is not None:
            if getattr(vector_store, "_client", None) is None:
                await vector_store.initialize()
            return vector_store

        try:
            # Ensure the directory exists (creates parents=True for nested paths like ./data/chroma)
            Path(final_persist_dir).mkdir(parents=True, exist_ok=True)

            vector_store = VectorStore(persist_dir=final_persist_dir)
            await vector_store.initialize()
            return vector_store

        except Exception as e:  # noqa: BLE001 - broad catch for startup resilience
            print(f"Failed to initialize vector store at {final_persist_dir}: {e}")  # noqa: T201
            raise


def _get_vector_store() -> VectorStore:
    """Get the global vector store instance (synchronous accessor).

    This is a helper function that raises an error if the vector store
    hasn't been initialized yet. Prefer `await init_vector_store()` or
    use the async context manager for initialization.

    Returns:
        The configured VectorStore instance.

    Raises:
        RuntimeError: If the vector store has not been initialized via init_vector_store().
    """
    global vector_store

    if vector_store is None:
        raise RuntimeError(  # noqa: TRY003
            "VectorStore must be initialized with await init_vector_store() before use"
        )

    return vector_store


async def get_or_create_collection(collection_name: str) -> chromadb.Collection:
    """Get or create a collection using the global vector store.

    A convenience wrapper that initializes the vector store if needed
    and returns the appropriate ChromaDB Collection object.

    Args:
        collection_name: Name of the collection to get or create.

    Returns:
        chromadb.Collection for upserting/querying documents.
    """
    vs = await init_vector_store()
    return vs.get_collection(collection_name)


# Add ChromaDB to exports if not already present
__all__ = [  # noqa: RUF023 - add all public names to __all__
    "HuggingFaceEmbeddingFunction",
    "VectorStore",
    "init_vector_store",
    "vector_store",
    "_get_vector_store",
    "get_or_create_collection",
]
