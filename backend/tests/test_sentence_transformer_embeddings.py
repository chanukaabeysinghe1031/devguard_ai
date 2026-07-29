"""Unit tests for sentence-transformer embedding provider (mocked model)."""

from __future__ import annotations

import math
from typing import Any
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from app.ai.rag.embedding_provider import (
    EmbeddingConfigurationError,
    EmbeddingProviderError,
    HashingEmbeddingProvider,
    SentenceTransformerEmbeddingProvider,
    build_embedding_provider,
    clear_embedding_provider_cache,
    sanitise_embedding_text,
)
from app.ai.rag.vector_store import ChromaVectorStore, CollectionCompatibilityError
from app.core.config import Settings
from app.domain.interfaces.ai_providers import EmbeddedChunk


class _FakeModel:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.device = kwargs.get("device", "cpu")
        self.encode_calls: list[tuple[str, list[str]]] = []
        self.loaded = True

    def get_sentence_embedding_dimension(self) -> int:
        return 4

    def encode(self, texts: list[str], **kwargs: Any) -> list[list[float]]:
        self.encode_calls.append(("encode", list(texts)))
        return [_fake_vector(t, normalize=kwargs.get("normalize_embeddings", False)) for t in texts]

    def encode_query(self, texts: list[str], **kwargs: Any) -> list[list[float]]:
        self.encode_calls.append(("encode_query", list(texts)))
        return [_fake_vector(t, normalize=kwargs.get("normalize_embeddings", False)) for t in texts]

    def encode_document(self, texts: list[str], **kwargs: Any) -> list[list[float]]:
        self.encode_calls.append(("encode_document", list(texts)))
        return [_fake_vector(t, normalize=kwargs.get("normalize_embeddings", False)) for t in texts]


def _fake_vector(text: str, *, normalize: bool) -> list[float]:
    base = [float(len(text) % 7 + 1), 2.0, 3.0, 4.0]
    if not normalize:
        return base
    norm = math.sqrt(sum(v * v for v in base)) or 1.0
    return [v / norm for v in base]


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    clear_embedding_provider_cache()
    yield
    clear_embedding_provider_cache()


def test_config_accepts_sentence_transformers() -> None:
    settings = Settings(
        EMBEDDING_PROVIDER="sentence_transformers",
        EMBEDDING_MODEL="sentence-transformers/all-MiniLM-L6-v2",
        EMBEDDING_DEVICE="cpu",
        EMBEDDING_BATCH_SIZE=16,
        EMBEDDING_NORMALIZE=True,
        EMBEDDING_MAX_INPUT_CHARACTERS=12000,
    )
    assert settings.embedding_provider == "sentence_transformers"
    assert settings.embedding_normalize is True


def test_config_rejects_empty_model_for_st() -> None:
    with pytest.raises(ValidationError):
        Settings(
            EMBEDDING_PROVIDER="sentence_transformers",
            EMBEDDING_MODEL="   ",
        )


def test_config_rejects_zero_batch_size() -> None:
    with pytest.raises(ValidationError):
        Settings(EMBEDDING_BATCH_SIZE=0)


def test_config_rejects_negative_max_chars() -> None:
    with pytest.raises(ValidationError):
        Settings(EMBEDDING_MAX_INPUT_CHARACTERS=-1)


def test_config_rejects_invalid_device() -> None:
    with pytest.raises(ValidationError):
        Settings(EMBEDDING_DEVICE="tpu")


def test_factory_hash_still_available() -> None:
    provider = build_embedding_provider("hash")
    assert isinstance(provider, HashingEmbeddingProvider)
    assert provider.name == "hashing-v1"


def test_factory_selects_sentence_transformers() -> None:
    with patch(
        "sentence_transformers.SentenceTransformer",
        _FakeModel,
    ):
        provider = build_embedding_provider("sentence_transformers", lazy_load=False)
        assert isinstance(provider, SentenceTransformerEmbeddingProvider)
        assert provider.provider_name == "sentence_transformers"


def test_factory_rejects_unsupported_provider() -> None:
    with pytest.raises(EmbeddingConfigurationError, match="Unsupported"):
        build_embedding_provider("openai_embeddings")


def test_explicit_st_failure_does_not_return_hash() -> None:
    with patch(
        "sentence_transformers.SentenceTransformer",
        side_effect=RuntimeError("boom"),
    ):
        provider = build_embedding_provider("sentence_transformers", lazy_load=True)
        assert isinstance(provider, SentenceTransformerEmbeddingProvider)
        with pytest.raises(EmbeddingProviderError):
            provider.embed_query("hello")
        # Must not silently become hash
        assert provider.provider_name == "sentence_transformers"


def test_model_loads_once() -> None:
    with patch("sentence_transformers.SentenceTransformer", _FakeModel):
        provider = SentenceTransformerEmbeddingProvider(lazy_load=True)
        provider.embed_query("one")
        provider.embed_documents(["two", "three"])
        provider.health_check()
        assert provider.load_count == 1


def test_embed_query_shape_and_finite() -> None:
    with patch("sentence_transformers.SentenceTransformer", _FakeModel):
        provider = SentenceTransformerEmbeddingProvider(normalize=True)
        vector = provider.embed_query("AWS AccessDenied")
        assert isinstance(vector, list)
        assert all(isinstance(x, float) for x in vector)
        assert len(vector) == 4
        assert all(math.isfinite(x) for x in vector)
        mag = math.sqrt(sum(v * v for v in vector))
        assert mag == pytest.approx(1.0, abs=1e-5)


def test_embed_documents_order_and_batching() -> None:
    with patch("sentence_transformers.SentenceTransformer", _FakeModel):
        provider = SentenceTransformerEmbeddingProvider(batch_size=2, normalize=False)
        docs = ["a", "bb", "ccc", "dddd", "eeeee"]
        vectors = provider.embed_documents(docs)
        assert len(vectors) == 5
        assert [int(v[0]) for v in vectors] == [len(d) % 7 + 1 for d in docs]
        assert provider.usage.batches_processed == 3  # 2+2+1


def test_empty_documents_return_empty() -> None:
    with patch("sentence_transformers.SentenceTransformer", _FakeModel):
        provider = SentenceTransformerEmbeddingProvider()
        assert provider.embed_documents([]) == []


def test_invalid_document_entry_rejected() -> None:
    with patch("sentence_transformers.SentenceTransformer", _FakeModel):
        provider = SentenceTransformerEmbeddingProvider()
        with pytest.raises(TypeError):
            provider.embed_documents(["ok", 123])  # type: ignore[list-item]


def test_secrets_masked_before_encode() -> None:
    with patch("sentence_transformers.SentenceTransformer", _FakeModel):
        provider = SentenceTransformerEmbeddingProvider()
        provider._encode_capture = []
        text = (
            "AKIAIOSFODNN7EXAMPLE fail "
            "ghp_abcdefghijklmnopqrstuvwxyz0123456789 "
            "Bearer eyJhbGciOiJIUzI1NiJ9.abc "
            "password=supersecret "
            "postgres://user:pass@db.example.com/app "
            "-----BEGIN RSA PRIVATE KEY-----\nabc\n-----END RSA PRIVATE KEY-----"
        )
        provider.embed_query(text)
        assert provider._encode_capture is not None
        seen = provider._encode_capture[0]
        assert "AKIAIOSFODNN7EXAMPLE" not in seen
        assert "ghp_" not in seen
        assert "Bearer eyJ" not in seen
        assert "supersecret" not in seen
        assert "user:pass@" not in seen
        assert "BEGIN RSA PRIVATE KEY" not in seen
        assert "[REDACTED" in seen


def test_null_bytes_removed_and_truncation_recorded() -> None:
    cleaned = sanitise_embedding_text("a\x00b" + ("x" * 100), max_characters=10)
    assert "\x00" not in cleaned.text
    assert cleaned.truncated is True
    with patch("sentence_transformers.SentenceTransformer", _FakeModel):
        provider = SentenceTransformerEmbeddingProvider(max_input_characters=20)
        provider.embed_query("y" * 200)
        assert provider.usage.truncated_input_count == 1


def test_device_cpu_works() -> None:
    with patch("sentence_transformers.SentenceTransformer", _FakeModel):
        provider = SentenceTransformerEmbeddingProvider(device="cpu", lazy_load=False)
        assert provider.selected_device == "cpu"


def test_unavailable_mps_raises() -> None:
    with (
        patch("torch.cuda.is_available", return_value=False),
        patch("torch.backends.mps.is_available", return_value=False),
        patch("sentence_transformers.SentenceTransformer", _FakeModel),
    ):
        provider = SentenceTransformerEmbeddingProvider(device="mps", lazy_load=True)
        with pytest.raises(EmbeddingConfigurationError, match="MPS"):
            provider.embed_query("x")


def test_unavailable_cuda_raises() -> None:
    with (
        patch("torch.cuda.is_available", return_value=False),
        patch("sentence_transformers.SentenceTransformer", _FakeModel),
    ):
        provider = SentenceTransformerEmbeddingProvider(device="cuda", lazy_load=True)
        with pytest.raises(EmbeddingConfigurationError, match="CUDA"):
            provider.embed_query("x")


def test_auto_falls_back_to_cpu() -> None:
    with (
        patch("torch.cuda.is_available", return_value=False),
        patch("torch.backends.mps.is_available", return_value=False),
        patch("sentence_transformers.SentenceTransformer", _FakeModel),
    ):
        provider = SentenceTransformerEmbeddingProvider(device="auto", lazy_load=False)
        assert provider.selected_device == "cpu"


def test_metadata_and_usage() -> None:
    with patch("sentence_transformers.SentenceTransformer", _FakeModel):
        provider = SentenceTransformerEmbeddingProvider(batch_size=8)
        provider.embed_query("hello")
        meta = provider.metadata()
        assert meta["provider_name"] == "sentence_transformers"
        assert meta["external_cost"] == "not_applicable"
        assert meta["external_api_call"] is False
        assert meta["local_execution"] is True
        assert meta["usage"]["texts_embedded"] == 1


def test_chroma_dimension_mismatch_detected() -> None:
    class _FakeCollection:
        def __init__(self) -> None:
            self.metadata = {
                "devguard_embedding_config_hash": "abc",
                "devguard_embedding_dimension": "256",
                "devguard_embedding_model": "hashing-v1",
                "devguard_embedding_provider": "hash",
            }

        def count(self) -> int:
            return 3

        def upsert(self, **kwargs: Any) -> None:
            raise AssertionError("upsert should not run on mismatch")

    store = object.__new__(ChromaVectorStore)
    store._collection_name = "test"
    store._embedding_identity = {
        "devguard_embedding_config_hash": "different",
        "devguard_embedding_dimension": "384",
        "devguard_embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
        "devguard_embedding_provider": "sentence_transformers",
        "devguard_embedding_normalised": "true",
    }
    store._collection = _FakeCollection()
    with pytest.raises(CollectionCompatibilityError):
        store.upsert(
            [EmbeddedChunk(chunk_id="1", text="x", metadata={})],
            [[0.1] * 384],
        )


def test_hash_provider_unchanged() -> None:
    provider = HashingEmbeddingProvider()
    a = provider.embed(["AccessDenied"])[0]
    b = provider.embed_query("AccessDenied")
    assert a == b
    assert len(a) == 256
