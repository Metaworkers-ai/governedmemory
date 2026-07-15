"""
Unit tests for core/memory_store/embeddings.py.

NullEmbeddingProvider is exercised fully (it's the zero-dependency default
every other test in the suite relies on). The API-backed providers
(OpenAI/Cohere) and SentenceTransformerProvider aren't installed in the
unit-test environment by design (see requirements-dev.txt vs.
requirements-embed-local.txt) -- what's tested here is the fallback
contract: importing without the optional dependency raises a clear
ImportError telling the caller what to install, rather than an opaque
ModuleNotFoundError deep in a third-party import. That contract is what
api/main.py's _build_embedder() relies on to degrade to
NullEmbeddingProvider instead of crashing the server.
"""

from __future__ import annotations

import pytest

from core.memory_store.embeddings import (
    CohereEmbeddingProvider,
    NullEmbeddingProvider,
    OpenAIEmbeddingProvider,
    SentenceTransformerProvider,
)


class TestNullEmbeddingProvider:
    def test_default_dimensions_is_768(self):
        assert NullEmbeddingProvider().dimensions == 768

    def test_custom_dimensions(self):
        assert NullEmbeddingProvider(dimensions=384).dimensions == 384

    def test_embed_returns_a_zero_vector_of_the_right_length(self):
        provider = NullEmbeddingProvider(dimensions=5)
        assert provider.embed("anything") == [0.0, 0.0, 0.0, 0.0, 0.0]

    def test_embed_is_content_independent(self):
        provider = NullEmbeddingProvider(dimensions=8)
        assert provider.embed("hello") == provider.embed("completely different text")

    def test_embed_batch_returns_one_zero_vector_per_input(self):
        provider = NullEmbeddingProvider(dimensions=4)
        result = provider.embed_batch(["a", "b", "c"])
        assert result == [[0.0] * 4, [0.0] * 4, [0.0] * 4]

    def test_embed_batch_on_empty_list_returns_empty_list(self):
        assert NullEmbeddingProvider().embed_batch([]) == []


class TestOptionalProvidersRaiseHelpfulImportErrors:
    """These SDKs are deliberately not installed in the unit-test env
    (requirements-dev.txt doesn't pull them in) -- that's the scenario
    being tested, not worked around."""

    def test_sentence_transformer_provider_missing_dependency(self):
        with pytest.raises(ImportError, match="requirements-embed-local"):
            SentenceTransformerProvider()

    def test_openai_provider_missing_dependency(self):
        with pytest.raises(ImportError, match="pip install openai"):
            OpenAIEmbeddingProvider()

    def test_cohere_provider_missing_dependency(self):
        # The import failure happens before COHERE_API_KEY is ever read, so
        # no env var setup is needed to hit this path.
        with pytest.raises(ImportError, match="pip install cohere"):
            CohereEmbeddingProvider()
