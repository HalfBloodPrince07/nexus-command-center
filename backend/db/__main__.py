"""Test script for VectorStore implementation.

Usage:
    uv run -m backend.db  # or python -m backend.db

This tests all core functionality of the vector store without requiring
LM Studio to be running (embeddings will fail gracefully).
"""

import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch

# Import everything we need upfront before mocking httpx.post
from backend.config import settings


async def test_vector_store(settings=settings):
    print("=" * 50)
    print("VectorStore Implementation Test")
    print("=" * 50)

    # Mock httpx.post to avoid actual network calls
    with patch("httpx.post") as mock_post:
        # Set up a mock response for embedding requests
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {"embedding": [0.1] * 768},  # Mock embedding vector
                {"embedding": [0.2] * 768},
            ]
        }
        mock_post.return_value = mock_response

        from backend.db.vector_store import (
            VectorStore,
            _get_vector_store,
            get_or_create_collection,
            init_vector_store,
            vector_store,
        )

    # Test 1: Initialize vector store
    print("\n[Test 1] Initializing VectorStore...")
    persist_dir = Path("./data/chroma_test").resolve()
    vs = await init_vector_store(settings=settings, persist_path=str(persist_dir))
    assert vs is not None, "VectorStore should be initialized"
    assert vs.persist_path == persist_dir, f"Expected {persist_dir}, got {vs.persist_path}"
    print(f"[PASS] VectorStore initialized at: {vs.persist_path}")

    # Test 2: Initialize collections (mock chromadb)
    print("\n[Test 2] Creating collections...")
    with patch.object(vs._chroma_client, "list_collections", return_value=[]):
        with patch.object(
            vs._chroma_client, "get_or_create_collection"
        ) as mock_get_collection:
            # Mock collection objects
            mock_col = MagicMock()
            mock_get_collection.return_value = mock_col

            await vs.initialize()

            # Verify collections were created
            expected_collections = ["default"] + VectorStore.COLLECTIONS
            names_created = [
                call.kwargs.get("name", call.args[0] if call.args else None)
                for call in mock_get_collection.call_args_list
            ]
            expected_sorted = sorted(expected_collections)
            actual_sorted = sorted(names_created)
            assert expected_sorted == actual_sorted, f"Expected collections {expected_sorted}, got {actual_sorted}"
            print(f"[PASS] Created collections: {', '.join(sorted(names_created))}")

    # Test 3: Get collection
    print("\n[Test 3] Getting collection...")
    with patch.object(vs._chroma_client, "get_or_create_collection") as mock_get:
        mock_col = MagicMock()
        mock_get.return_value = mock_col

        col = vs.get_collection("memory")
        assert col is not None
        print("[PASS] Collection retrieved successfully")

    # Test 4: Upsert chunks (mock)
    print("\n[Test 4] Upserting chunks...")
    with patch.object(vs._chroma_client, "get_or_create_collection") as mock_get:
        mock_col = MagicMock()
        mock_get.return_value = mock_col

        chunks = [
            {
                "id": f"chunk_{i}",
                "text": f"This is test chunk number {i}",
                "metadata": {"source": "test", "file_id": "file_1"},
            }
            for i in range(3)
        ]

        await vs.upsert_chunks("memory", chunks)

        mock_col.upsert.assert_called_once()
        call_args = mock_col.upsert.call_args
        docs = call_args[1]["documents"] if "documents" in call_args[1] else call_args[0][2]
        assert len(docs) == 3, f"Expected 3 documents, got {len(docs)}"
        print("[PASS] Chunks upserted successfully")

    # Test 5: Query (mock)
    print("\n[Test 5] Querying vector store...")
    with patch.object(vs._chroma_client, "get_or_create_collection") as mock_get:
        mock_col = MagicMock()
        mock_results = {
            "documents": [["chunk_0", "chunk_1"]],
            "metadatas": [[{"source": "test"}, {"source": "test"}]],
            "distances": [[0.95, 0.87]],
        }
        mock_col.query.return_value = mock_results
        mock_get.return_value = mock_col

        results = await vs.query("memory", "query text")

        assert len(results) == 2, f"Expected 2 results, got {len(results)}"
        for r in results:
            required_keys = {"id", "text", "metadata", "distance"}
            assert all(k in r for k in required_keys), f"Result missing keys: {required_keys - set(r.keys())}"
        print(f"[PASS] Query returned {len(results)} results")

    # Test 6: Delete by file_id (mock)
    print("\n[Test 6] Deleting by file_id...")
    with patch.object(vs._chroma_client, "get_or_create_collection") as mock_get:
        mock_col = MagicMock()
        mock_get.return_value = mock_col

        await vs.delete_by_file_id("memory", "file_123")

        # Verify delete was called with correct filter
        assert "where" in mock_col.delete.call_args[1]
        filter_expr = mock_col.delete.call_args[1]["where"]
        print(f"[PASS] Delete executed with filter: {filter_expr}")

    # Test 7: Module-level exports
    print("\n[Test 7] Testing module-level functions...")
    global vector_store, _async_vector_store_lock

    # Note: We don't re-import here; the module was already imported above
    from backend.db.vector_store import vector_store as vs_module, get_or_create_collection as get_col

    assert isinstance(vs_module, VectorStore), "vector_store should be instance of VectorStore"
    print("[PASS] Module-level exports working correctly")


if __name__ == "__main__":
    asyncio.run(test_vector_store())
    print("\n" + "=" * 50)
    print("All tests passed!")
    print("=" * 50)
