"""Local Hugging Face Transformers Embedding Inference.

Provides embedding inference using local HF models (NOT LM Studio or Ollama).
Uses huggingface_hub to download models directly from Hugging Face.

Requirements:
- transformers>=4.35.0
- torch>=2.0.0
- huggingface_hub>=0.19.0
"""

import os
from pathlib import Path
from typing import Optional, List, Union

import numpy as np
from PIL import Image
from PIL.Image import OPEN
from transformers import AutoModelForSequenceClassification, AutoTokenizer
from torch import Tensor


class HFEmbeddingInference:
    """Local Hugging Face Embedding Inference Engine."""

    def __init__(self, model_id: str = "nomic-ai/nomic-embed-text-v1.5", cache_dir: Optional[Path] = None):
        """Initialize the embedding inference engine.

        Args:
            model_id: Hugging Face model identifier (e.g., "nomic-ai/nomic-embed-text-v1.5")
            cache_dir: Local directory for model caching. Defaults to backend/data/embeddings/hf_cache
        """
        self.model_id = model_id
        if cache_dir is None:
            from config import settings
            cache_dir = settings.HF_EMBEDDING_CACHE_DIR

        # Model path - use local cache or download via huggingface_hub
        self.local_model_path = str(cache_dir / Path(model_id).name)

        # Download model if not cached (handled by transformers)
        tokenizer = AutoTokenizer.from_pretrained(
            model_id,
            trust_remote_code=True,  # Required for some models like nomic-embed-text-v1.5
        )

    def embed(self, texts: Union[str, List[str]], batch_size: int = 32) -> np.ndarray:
        """Generate embeddings for text input(s).

        Args:
            texts: Single string or list of strings to embed
            batch_size: Batch size for inference (default: 32)

        Returns:
            numpy array of embeddings. Shape is (1,) if single text, (n,) if multiple texts
        """
        from transformers import AutoModelForSequenceClassification
        from torch.nn.functional import normalize

        # Get tokenizer and model
        tokenizer = AutoTokenizer.from_pretrained(
            self.model_id,
            trust_remote_code=True,
        )
        model = AutoModelForSequenceClassification.from_pretrained(
            self.model_id,
            trust_remote_code=True,
            torch_dtype="auto",  # Automatic dtype selection based on hardware
        )

        if isinstance(texts, str):
            texts = [texts]

        # Tokenize input(s)
        inputs = tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=512,  # Nomic-Embed-Text-v1.5 supports up to 8192 tokens
            return_tensors="pt",
        )

        # Generate embeddings with batching
        embeddings_list = []
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i : i + batch_size]
            batch_inputs = {k: v[i : i + batch_size] for k, v in inputs.items()}

            with torch.no_grad():
                outputs = model(**batch_inputs)

            # Extract embeddings from the last hidden layer (CLS token)
            batch_embeddings = outputs.logits.mean(dim=1)  # Mean pooling over sequence length

            embeddings_list.append(batch_embeddings.cpu().numpy())

        result = np.concatenate(embeddings_list, axis=-1) if len(embeddings_list) > 1 else embeddings_list[0]
        return result

    def embed_image(self, image: Image.Image) -> np.ndarray:
        """Generate embedding for an image (requires vision-capable model).

        Args:
            image: PIL Image object

        Returns:
            numpy array of image embedding
        """
        # Note: Requires a vision-capable model like nomic-ai/nomic-embed-text-v1.5 (visual variant)
        raise NotImplementedError("Image embeddings not yet implemented")


def get_embedding(text: str, model_id: str = "nomic-ai/nomic-embed-text-v1.5", cache_dir: Optional[Path] = None) -> np.ndarray:
    """Convenience function for single text embedding.

    Args:
        text: Text to embed
        model_id: Hugging Face model identifier (default: nomic-ai/nomic-embed-text-v1.5)
        cache_dir: Local caching directory

    Returns:
        numpy array of embedding vector
    """
    inference = HFEmbeddingInference(model_id=model_id, cache_dir=cache_dir)
    return inference.embed(text)


def get_embeddings(
    texts: Union[str, List[str]], model_id: str = "nomic-ai/nomic-embed-text-v1.5", batch_size: int = 32
) -> np.ndarray:
    """Convenience function for embedding multiple texts.

    Args:
        texts: Single string or list of strings to embed
        model_id: Hugging Face model identifier (default: nomic-ai/nomic-embed-text-v1.5)
        batch_size: Batch size for inference (default: 32)

    Returns:
        numpy array of embeddings
    """
    inference = HFEmbeddingInference(model_id=model_id)
    return inference.embed(texts, batch_size=batch_size)
