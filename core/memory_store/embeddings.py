"""
Model-agnostic embedding interface.

Why abstract? The embedding model is not core governance logic — it's a pluggable
infrastructure choice. Different deployments may use:
  - sentence-transformers (local, no API key, works offline)
  - OpenAI text-embedding-3-* (API, higher quality, costs money)
  - Cohere embed-* (API, multilingual)
  - AWS Bedrock Titan embed (stays on AWS)
  - Azure OpenAI (enterprise compliance)

The EmbeddingProvider ABC decouples the memory store from any specific model or cloud.
Unit tests use NullEmbeddingProvider (zero vectors, no dependencies, fast).

ADDING A NEW PROVIDER
---------------------
1. Subclass EmbeddingProvider.
2. Implement embed(), embed_batch(), and the dimensions property.
3. Make sure dimensions matches your Postgres vector column size.
   If you change the default model and its dimension differs from 768,
   update EMBEDDING_DIM in .env and create a new migration to change the column type.
4. Add your provider class to this file and export it from core/memory_store/__init__.py.
5. Write a unit test in tests/unit/test_embeddings.py.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    """Abstract base — implement this to plug in any embedding model."""

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        """Return the embedding vector for a single text string."""

    @abstractmethod
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Return embeddings for a list of texts. More efficient than looping embed()."""

    @property
    @abstractmethod
    def dimensions(self) -> int:
        """
        Vector length this provider outputs.
        Must match the `vector(N)` column in the Postgres schema.
        Default schema uses 768 (all-mpnet-base-v2).
        """


# ---------------------------------------------------------------------------
# Local provider — no API key, works offline
# ---------------------------------------------------------------------------


class SentenceTransformerProvider(EmbeddingProvider):
    """
    Embedding via sentence-transformers (runs locally on CPU or GPU).

    Default model: all-mpnet-base-v2  → 768 dims  (~420 MB download)
    Faster alternative: all-MiniLM-L6-v2 → 384 dims (~80 MB download)

    If you switch models, make sure the dimension matches the DB column.

    Usage:
        provider = SentenceTransformerProvider()                     # default 768-dim
        provider = SentenceTransformerProvider("all-MiniLM-L6-v2")  # 384-dim (faster)

    Install:
        pip install sentence-transformers
    """

    def __init__(self, model_name: str = "all-mpnet-base-v2"):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise ImportError(
                "sentence-transformers is not installed. "
                "Run: pip install -r requirements-embed-local.txt"
            ) from exc
        self._model = SentenceTransformer(model_name)
        self._dims: int = self._model.get_sentence_embedding_dimension()

    def embed(self, text: str) -> list[float]:
        return self._model.encode(text, show_progress_bar=False).tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return self._model.encode(texts, show_progress_bar=False).tolist()

    @property
    def dimensions(self) -> int:
        return self._dims


# ---------------------------------------------------------------------------
# Test provider — zero vectors, no model needed
# ---------------------------------------------------------------------------


class NullEmbeddingProvider(EmbeddingProvider):
    """
    Returns all-zero vectors. Use ONLY in unit tests and CI.

    Vector search with zero embeddings returns arbitrary results — this provider
    exists so tests can run without downloading a model or hitting an API.
    Never use in production or integration tests that validate retrieval quality.
    """

    def __init__(self, dimensions: int = 768):
        self._dimensions = dimensions

    def embed(self, text: str) -> list[float]:
        return [0.0] * self._dimensions

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * self._dimensions for _ in texts]

    @property
    def dimensions(self) -> int:
        return self._dimensions


# ---------------------------------------------------------------------------
# API providers (optional — install the relevant SDK to use)
# ---------------------------------------------------------------------------


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """
    OpenAI embeddings via the openai SDK.
    Requires OPENAI_API_KEY environment variable (read by the OpenAI() client
    itself -- never pass keys through call sites or logs).

    Models:
        text-embedding-3-small → 1536 dims natively (cheaper)
        text-embedding-3-large → 3072 dims natively (higher quality)

    Both text-embedding-3-* models are Matryoshka-trained, so the API accepts
    a `dimensions` param to truncate the output to any smaller size without a
    meaningful quality cliff. Default here is 768 to match this repo's
    existing `vector(768)` schema column with zero migration required --
    override via the EMBEDDING_DIM env var (see _build_embedder in
    api/main.py) if you've migrated the column to a different width.

    Install: pip install openai
    """

    def __init__(self, model: str = "text-embedding-3-small", dimensions: int = 768):
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ImportError("Run: pip install openai") from exc
        if not os.environ.get("OPENAI_API_KEY"):
            raise RuntimeError(
                "OPENAI_API_KEY is not set -- required to use OpenAIEmbeddingProvider."
            )
        self._client = OpenAI()
        self._model = model
        self._dims = dimensions

    def embed(self, text: str) -> list[float]:
        resp = self._client.embeddings.create(
            input=[text], model=self._model, dimensions=self._dims
        )
        return resp.data[0].embedding

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        resp = self._client.embeddings.create(input=texts, model=self._model, dimensions=self._dims)
        return [d.embedding for d in resp.data]

    @property
    def dimensions(self) -> int:
        return self._dims


class CohereEmbeddingProvider(EmbeddingProvider):
    """
    Cohere embeddings (multilingual support, good for non-English CX).
    Requires COHERE_API_KEY environment variable.

    Model: embed-multilingual-v3.0 → 1024 dims

    Install: pip install cohere
    """

    def __init__(self, model: str = "embed-multilingual-v3.0"):
        try:
            import cohere
        except ImportError as exc:
            raise ImportError("Run: pip install cohere") from exc
        import os

        self._client = cohere.Client(os.environ["COHERE_API_KEY"])
        self._model = model
        self._dims = 1024

    def embed(self, text: str) -> list[float]:
        resp = self._client.embed(texts=[text], model=self._model, input_type="search_document")
        return resp.embeddings[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        resp = self._client.embed(texts=texts, model=self._model, input_type="search_document")
        return resp.embeddings

    @property
    def dimensions(self) -> int:
        return self._dims
