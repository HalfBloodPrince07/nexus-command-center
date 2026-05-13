"""NEXUS OS Inference Service.

Provides chat completion and embedding inference using:
- LM Studio API for text generation (local inference)
- Hugging Face Transformers for embeddings (local HF model, NOT LM Studio/Ollama)

This service is the "brain" of NEXUS OS — it handles all reasoning, analysis, and knowledge extraction.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import numpy as np
import requests
from PIL.Image import OPEN
from transformers import AutoModelForSequenceClassification, AutoTokenizer
from torch import Tensor

# Configure logging
logger = logging.getLogger(__name__)


class LMStudioInference:
    """LM Studio Chat Completion Inference.

    Wraps the LM Studio v1 REST API for local text generation and image inputs.
    All inference happens locally — no cloud calls.
    """

    def __init__(self, base_url: str = "http://localhost:1234/v1", api_key: str = "lm-studio"):
        self.base_url = base_url.rstrip("/") + "/chat"
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        stream: bool = False,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        vision_model: Optional[str] = None,
    ) -> Union[Dict[str, Any], requests.Response]:
        """Send a chat completion request to LM Studio.

        Args:
            messages: List of message dicts with "role" and "content" keys
            model: Model identifier (optional, uses default if not provided)
            stream: Whether to stream response (default: False)
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
            vision_model: Vision-capable model for image inputs

        Returns:
            Response dict (non-streaming) or streaming Response object
        """
        payload = {
            "model": model,  # e.g., "llama3.2" — the LLM identifier
            "input": messages,
            "stream": stream,
            "temperature": temperature,
            "max_output_tokens": max_tokens,
            "store": False,  # Don't store chat history in LM Studio
        }

        # Add vision model if image inputs are present
        has_images = any(
            isinstance(msg.get("content"), list) and any(item.get("type") == "image" for item in msg.get("content", []))
            for msg in messages
        )

        if has_images and vision_model:
            payload["integrations"] = [
                {
                    "type": "plugin",
                    "id": f"vision/{vision_model}",  # Vision model as plugin identifier
                }
            ]

        logger.debug(f"Sending chat to LM Studio at {self.base_url}: {messages}")
        response = requests.post(self.base_url, json=payload, headers=self.headers)

        if not stream:
            try:
                response.raise_for_status()
                data = response.json()
                logger.info("LM Studio response received: %d tokens", data.get("stats", {}).get("total_output_tokens", 0))
                return data
            except requests.exceptions.HTTPError as e:
                if "429" in str(e):
                    logger.error("LM Studio rate limit exceeded. Please wait.")
                    raise
                logger.exception(f"LM Studio error: %s. Response: %s", e, response.text)
                return {"error": str(e), "raw": response.text}

        # Streaming mode
        if not response.ok:
            try:
                data = response.json()
                return {"error": f"{response.status_code}: {data.get('message', response.text)}"}
            except ValueError:
                logger.error("LM Studio returned invalid JSON for stream")
                return {"error": f"{response.status_code}: {response.text}"}

        return response.iter_lines()  # Returns generator of (key, value) pairs


class HFEmbeddingInference:
    """Local Hugging Face Embeddings Inference.

    Uses local HF models downloaded via huggingface_hub + torch.
    NOT LM Studio or Ollama — this is a dedicated local embedding model.
    """

    def __init__(self, model_id: str = "nomic-ai/nomic-embed-text-v1.5", cache_dir: Optional[Path] = None):
        self.model_id = model_id
        if cache_dir is None:
            from config import settings
            cache_dir = settings.HF_EMBEDDING_CACHE_DIR

        # Model path - use local cache or download via huggingface_hub
        self.local_model_path = str(cache_dir / Path(model_id).name)

        logger.info(f"Initializing HF Embedding model: {model_id} (local)")

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
            trust_remote_code=True,  # Required for some models like nomic-embed-text-v1.5
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


class InferenceService:
    """Main NEXUS OS inference service.

    Orchestrates chat completion and embedding inference using LM Studio (local)
    and Hugging Face Transformers (local HF model, not LM Studio/Ollama).
    """

    def __init__(self):
        self.lm_studio = LMStudioInference()
        from config import settings
        self.hf_embeddings = HFEmbeddingInference(
            model_id=settings.HF_EMBEDDING_MODEL_ID,
            cache_dir=settings.HF_EMBEDDING_CACHE_DIR,
        )

    def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        stream: bool = False,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        vision_model: Optional[str] = None,
    ) -> Union[Dict[str, Any], requests.Response]:
        """Send a chat completion request using LM Studio (local inference).

        Args:
            messages: List of message dicts with "role" and "content" keys
            model: Model identifier
            stream: Whether to stream response
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
            vision_model: Vision-capable model for image inputs

        Returns:
            Response dict or streaming Response object
        """
        return self.lm_studio.chat(
            messages=messages,
            model=model,
            stream=stream,
            temperature=temperature,
            max_tokens=max_tokens,
            vision_model=vision_model,
        )

    def embed(self, texts: Union[str, List[str]], batch_size: int = 32) -> np.ndarray:
        """Generate embeddings using local HF model (NOT LM Studio/Ollama).

        Args:
            texts: Single string or list of strings to embed
            batch_size: Batch size for inference

        Returns:
            numpy array of embeddings
        """
        return self.hf_embeddings.embed(texts, batch_size=batch_size)


# Singleton instance
_inference_service = None


def get_inference_service() -> InferenceService:
    """Get the singleton inference service instance."""
    global _inference_service
    if _inference_service is None:
        logger.info("Initializing NEXUS OS inference service (LM Studio + HF embeddings)")
        _inference_service = InferenceService()

    return _inference_service


# Convenience functions for direct imports
def chat(
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
    stream: bool = False,
) -> Union[Dict[str, Any], requests.Response]:
    """Convenience function for chat completion (LM Studio)."""
    return get_inference_service().chat(
        messages=messages,
        model=model,
        stream=stream,
    )


def embed(texts: Union[str, List[str]]) -> np.ndarray:
    """Convenience function for embeddings (local HF model - NOT LM Studio/Ollama)."""
    return get_inference_service().embed(texts)
