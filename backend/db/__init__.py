"""Nexus OS Database Module - Exports database components."""

from .vector_store import (
    HuggingFaceEmbeddingFunction,
    VectorStore,
    _get_vector_store,
    get_or_create_collection,
    init_vector_store,
    vector_store,
)

__all__ = [
    "HuggingFaceEmbeddingFunction",
    "VectorStore",
    "_get_vector_store",
    "get_or_create_collection",
    "init_vector_store",
    "vector_store",
]
