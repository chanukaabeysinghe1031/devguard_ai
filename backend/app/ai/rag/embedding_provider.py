"""Embedding providers — deterministic hash baseline plus sentence-transformers."""

from __future__ import annotations

import hashlib
import math
import re
import threading
import time
from dataclasses import dataclass
from typing import Any, Literal

from app.domain.interfaces.ai_providers import EmbeddingProvider
from app.domain.services.secret_masker import mask_secrets

_WORD = re.compile(r"[a-z0-9_]+", re.IGNORECASE)

EmbeddingDevice = Literal["cpu", "mps", "cuda", "auto"]
EmbeddingHealthStatus = Literal["healthy", "unavailable", "not_configured", "degraded"]


class EmbeddingProviderError(RuntimeError):
    """Safe, sanitised embedding provider failure."""


class EmbeddingConfigurationError(EmbeddingProviderError):
    """Invalid or unavailable embedding configuration (e.g. device)."""


@dataclass
class EmbeddingUsageStats:
    """Process-local usage counters — never stores embedded text."""

    texts_embedded: int = 0
    characters_processed: int = 0
    batches_processed: int = 0
    truncated_input_count: int = 0
    latency_ms_total: float = 0.0

    def snapshot(self) -> dict[str, Any]:
        return {
            "texts_embedded": self.texts_embedded,
            "characters_processed": self.characters_processed,
            "batches_processed": self.batches_processed,
            "truncated_input_count": self.truncated_input_count,
            "latency_ms_total": round(self.latency_ms_total, 3),
        }


@dataclass(frozen=True)
class EmbeddingHealthResult:
    status: EmbeddingHealthStatus
    provider: str
    model: str | None
    device: str | None
    dimension: int | None
    normalised: bool | None
    local_execution: bool
    external_api_call: bool
    external_cost: str
    detail: str
    safe_error: str | None = None


@dataclass(frozen=True)
class EmbeddingSanitiseResult:
    text: str
    truncated: bool
    secrets_masked: int
    original_length: int


def embedding_config_identity(
    *,
    provider: str,
    model: str,
    dimension: int,
    normalised: bool,
) -> dict[str, str]:
    """Stable, non-secret embedding identity for collection metadata."""
    normalised_flag = "true" if normalised else "false"
    raw = f"{provider}|{model}|{dimension}|normalised={normalised_flag}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return {
        "devguard_embedding_provider": provider,
        "devguard_embedding_model": model,
        "devguard_embedding_dimension": str(dimension),
        "devguard_embedding_normalised": normalised_flag,
        "devguard_embedding_config_hash": digest,
    }


def sanitise_embedding_text(
    text: str,
    *,
    max_characters: int,
) -> EmbeddingSanitiseResult:
    """Mask secrets, strip nulls, normalise whitespace, bound length."""
    if not isinstance(text, str):
        raise TypeError("embedding input must be a string")
    original_length = len(text)
    masked, secrets_masked = mask_secrets(text)
    cleaned = masked.replace("\x00", " ")
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    truncated = False
    if max_characters > 0 and len(cleaned) > max_characters:
        truncated = True
        # Prefer keeping the start (error headers / commands) within the bound.
        cleaned = cleaned[:max_characters].rstrip()
        # Avoid cutting through a redaction token when possible.
        for token in (
            "[REDACTED_PRIVATE_KEY]",
            "[REDACTED_GITHUB_TOKEN]",
            "[REDACTED_BEARER_TOKEN]",
            "[REDACTED_AWS_KEY]",
            "[REDACTED_USER]",
            "[REDACTED_PASSWORD]",
            "[REDACTED]",
        ):
            idx = cleaned.rfind(token)
            if idx != -1 and idx + len(token) > max_characters - 32:
                cleaned = cleaned[: idx + len(token)]
                break
    return EmbeddingSanitiseResult(
        text=cleaned,
        truncated=truncated,
        secrets_masked=secrets_masked,
        original_length=original_length,
    )


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    norm_l = math.sqrt(sum(a * a for a in left)) or 1.0
    norm_r = math.sqrt(sum(b * b for b in right)) or 1.0
    return dot / (norm_l * norm_r)


def cosine_similarity(left: list[float], right: list[float]) -> float:
    return _cosine_similarity(left, right)


def _vector_to_floats(row: Any) -> list[float]:
    if hasattr(row, "tolist"):
        row = row.tolist()
    return [float(x) for x in row]


def _assert_finite_vector(vector: list[float], *, expected_dim: int | None = None) -> None:
    if not vector:
        raise EmbeddingProviderError("embedding vector is empty")
    if expected_dim is not None and len(vector) != expected_dim:
        raise EmbeddingProviderError(
            f"embedding dimension mismatch: expected {expected_dim}, got {len(vector)}"
        )
    if any(not math.isfinite(v) for v in vector):
        raise EmbeddingProviderError("embedding vector contains non-finite values")


class HashingEmbeddingProvider(EmbeddingProvider):
    """Deterministic bag-of-features embedding for tests and offline MVP retrieval."""

    def __init__(self, dimensions: int = 256) -> None:
        self._dimensions = dimensions
        self.usage = EmbeddingUsageStats()

    @property
    def name(self) -> str:
        return "hashing-v1"

    @property
    def provider_name(self) -> str:
        return "hash"

    @property
    def model_name(self) -> str:
        return "hashing-v1"

    @property
    def embedding_dimension(self) -> int:
        return self._dimensions

    @property
    def normalisation_enabled(self) -> bool:
        return True

    def embed(self, texts: list[str]) -> list[list[float]]:
        return self.embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        vectors = self.embed_documents([text])
        return vectors[0] if vectors else []

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        started = time.perf_counter()
        out = [self._embed_one(text) for text in texts]
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        self.usage.texts_embedded += len(texts)
        self.usage.characters_processed += sum(len(t) for t in texts)
        self.usage.batches_processed += 1
        self.usage.latency_ms_total += elapsed_ms
        return out

    def _embed_one(self, text: str) -> list[float]:
        vector = [0.0] * self._dimensions
        tokens = _WORD.findall(text.lower())
        if not tokens:
            return vector
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            idx = int.from_bytes(digest[:4], "big") % self._dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[idx] += sign
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector]

    def health_check(self) -> EmbeddingHealthResult:
        try:
            vector = self.embed_query("DevGuard AI embedding health check")
            _assert_finite_vector(vector, expected_dim=self._dimensions)
            return EmbeddingHealthResult(
                status="healthy",
                provider=self.provider_name,
                model=self.model_name,
                device="cpu",
                dimension=self._dimensions,
                normalised=True,
                local_execution=True,
                external_api_call=False,
                external_cost="not_applicable",
                detail="hash embedding provider healthy",
            )
        except Exception as exc:  # noqa: BLE001 - health never raises
            return EmbeddingHealthResult(
                status="unavailable",
                provider=self.provider_name,
                model=self.model_name,
                device="cpu",
                dimension=self._dimensions,
                normalised=True,
                local_execution=True,
                external_api_call=False,
                external_cost="not_applicable",
                detail="hash embedding health check failed",
                safe_error=type(exc).__name__,
            )

    def config_identity(self) -> dict[str, str]:
        return embedding_config_identity(
            provider=self.provider_name,
            model=self.model_name,
            dimension=self._dimensions,
            normalised=True,
        )

    def metadata(self) -> dict[str, Any]:
        return {
            "provider_name": self.provider_name,
            "model_name": self.model_name,
            "selected_device": "cpu",
            "embedding_dimension": self._dimensions,
            "normalisation_enabled": True,
            "batch_size": 1,
            "local_execution": True,
            "external_api_call": False,
            "external_cost": "not_applicable",
            "usage": self.usage.snapshot(),
        }


class SentenceTransformerEmbeddingProvider(EmbeddingProvider):
    """Local sentence-transformers embedding provider (CPU default)."""

    def __init__(
        self,
        *,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        device: EmbeddingDevice = "cpu",
        batch_size: int = 16,
        normalize: bool = True,
        max_input_characters: int = 12_000,
        lazy_load: bool = True,
    ) -> None:
        if not (model_name or "").strip():
            raise EmbeddingConfigurationError("EMBEDDING_MODEL must not be empty")
        if batch_size <= 0:
            raise EmbeddingConfigurationError("EMBEDDING_BATCH_SIZE must be greater than zero")
        if max_input_characters <= 0:
            raise EmbeddingConfigurationError(
                "EMBEDDING_MAX_INPUT_CHARACTERS must be greater than zero"
            )
        self._model_name = model_name.strip()
        self._requested_device = device
        self._batch_size = batch_size
        self._normalize = normalize
        self._max_input_characters = max_input_characters
        self._model: Any | None = None
        self._selected_device: str | None = None
        self._dimension: int | None = None
        self._load_lock = threading.Lock()
        self._load_count = 0
        self.usage = EmbeddingUsageStats()
        # Optional hook for tests — captures sanitised text reaching the encoder.
        self._encode_capture: list[str] | None = None
        if not lazy_load:
            self._ensure_model()

    @property
    def name(self) -> str:
        return f"sentence-transformers:{self._model_name}"

    @property
    def provider_name(self) -> str:
        return "sentence_transformers"

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def embedding_dimension(self) -> int:
        self._ensure_model()
        assert self._dimension is not None
        return self._dimension

    @property
    def normalisation_enabled(self) -> bool:
        return self._normalize

    @property
    def selected_device(self) -> str:
        self._ensure_model()
        assert self._selected_device is not None
        return self._selected_device

    @property
    def load_count(self) -> int:
        return self._load_count

    def config_identity(self) -> dict[str, str]:
        return embedding_config_identity(
            provider=self.provider_name,
            model=self._model_name,
            dimension=self.embedding_dimension,
            normalised=self._normalize,
        )

    def metadata(self) -> dict[str, Any]:
        dimension = self._dimension
        device = self._selected_device
        if self._model is not None:
            dimension = self.embedding_dimension
            device = self.selected_device
        return {
            "provider_name": self.provider_name,
            "model_name": self._model_name,
            "selected_device": device,
            "embedding_dimension": dimension,
            "normalisation_enabled": self._normalize,
            "batch_size": self._batch_size,
            "local_execution": True,
            "external_api_call": False,
            "external_cost": "not_applicable",
            "usage": self.usage.snapshot(),
        }

    def _resolve_device(self) -> str:
        try:
            import torch
        except ImportError as exc:  # pragma: no cover - optional dependency chain
            raise EmbeddingConfigurationError(
                "torch is required for EMBEDDING_PROVIDER=sentence_transformers"
            ) from exc

        requested = self._requested_device
        if requested == "cpu":
            return "cpu"
        if requested == "cuda":
            if not torch.cuda.is_available():
                raise EmbeddingConfigurationError(
                    "EMBEDDING_DEVICE=cuda requested but CUDA is not available"
                )
            return "cuda"
        if requested == "mps":
            mps_ok = bool(
                getattr(torch.backends, "mps", None) and torch.backends.mps.is_available()
            )
            if not mps_ok:
                raise EmbeddingConfigurationError(
                    "EMBEDDING_DEVICE=mps requested but MPS is not available"
                )
            return "mps"
        # auto: cuda → mps → cpu
        if torch.cuda.is_available():
            return "cuda"
        if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            return "mps"
        return "cpu"

    def _ensure_model(self) -> Any:
        if self._model is not None:
            return self._model
        with self._load_lock:
            if self._model is not None:
                return self._model
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:  # pragma: no cover - optional dependency
                raise EmbeddingProviderError(
                    "sentence-transformers is required for "
                    "EMBEDDING_PROVIDER=sentence_transformers "
                    "(install optional AI dependencies)"
                ) from exc

            device = self._resolve_device()
            try:
                model = SentenceTransformer(self._model_name, device=device)
            except EmbeddingConfigurationError:
                raise
            except Exception as exc:  # noqa: BLE001 - sanitise load failures
                raise EmbeddingProviderError(
                    f"Failed to load embedding model '{self._model_name}': {type(exc).__name__}"
                ) from exc

            try:
                if hasattr(model, "get_embedding_dimension"):
                    dim = int(model.get_embedding_dimension())
                else:
                    dim = int(model.get_sentence_embedding_dimension())
            except Exception:  # noqa: BLE001
                probe = model.encode(
                    ["dimension probe"],
                    normalize_embeddings=self._normalize,
                    convert_to_numpy=True,
                )
                dim = len(_vector_to_floats(probe[0]))

            self._model = model
            self._selected_device = device
            self._dimension = dim
            self._load_count += 1
            return self._model

    def _sanitise_batch(self, texts: list[str]) -> tuple[list[str], int]:
        cleaned: list[str] = []
        truncated = 0
        for text in texts:
            if not isinstance(text, str):
                raise TypeError("embedding documents must be strings")
            result = sanitise_embedding_text(text, max_characters=self._max_input_characters)
            cleaned.append(result.text)
            if result.truncated:
                truncated += 1
        return cleaned, truncated

    def _encode_rows(
        self, texts: list[str], *, kind: Literal["query", "document"]
    ) -> list[list[float]]:
        model = self._ensure_model()
        assert self._dimension is not None
        if self._encode_capture is not None:
            self._encode_capture.extend(texts)

        encode_kwargs = {
            "batch_size": self._batch_size,
            "normalize_embeddings": self._normalize,
            "convert_to_numpy": True,
            "show_progress_bar": False,
        }
        if kind == "query" and hasattr(model, "encode_query"):
            raw = model.encode_query(texts, **encode_kwargs)
        elif kind == "document" and hasattr(model, "encode_document"):
            raw = model.encode_document(texts, **encode_kwargs)
        else:
            raw = model.encode(texts, **encode_kwargs)

        if len(texts) == 1 and not isinstance(raw, list) and getattr(raw, "ndim", 2) == 1:
            rows = [raw]
        else:
            rows = list(raw)

        vectors = [_vector_to_floats(row) for row in rows]
        if len(vectors) != len(texts):
            raise EmbeddingProviderError("encoder returned unexpected vector count")
        for vector in vectors:
            _assert_finite_vector(vector, expected_dim=self._dimension)
        return vectors

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Batch embed texts as documents (indexing / generic path)."""
        return self.embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        cleaned, truncated = self._sanitise_batch([text])
        started = time.perf_counter()
        vectors = self._encode_rows(cleaned, kind="query")
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        self.usage.texts_embedded += 1
        self.usage.characters_processed += len(cleaned[0])
        self.usage.batches_processed += 1
        self.usage.truncated_input_count += truncated
        self.usage.latency_ms_total += elapsed_ms
        return vectors[0]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        cleaned, truncated = self._sanitise_batch(texts)
        started = time.perf_counter()
        out: list[list[float]] = []
        batches = 0
        for start in range(0, len(cleaned), self._batch_size):
            batch = cleaned[start : start + self._batch_size]
            out.extend(self._encode_rows(batch, kind="document"))
            batches += 1
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        self.usage.texts_embedded += len(texts)
        self.usage.characters_processed += sum(len(t) for t in cleaned)
        self.usage.batches_processed += batches
        self.usage.truncated_input_count += truncated
        self.usage.latency_ms_total += elapsed_ms
        return out

    def health_check(self) -> EmbeddingHealthResult:
        try:
            vector = self.embed_query("DevGuard AI embedding health check")
            _assert_finite_vector(vector, expected_dim=self.embedding_dimension)
            return EmbeddingHealthResult(
                status="healthy",
                provider=self.provider_name,
                model=self._model_name,
                device=self.selected_device,
                dimension=self.embedding_dimension,
                normalised=self._normalize,
                local_execution=True,
                external_api_call=False,
                external_cost="not_applicable",
                detail="sentence-transformers embedding provider healthy",
            )
        except EmbeddingConfigurationError as exc:
            return EmbeddingHealthResult(
                status="not_configured",
                provider=self.provider_name,
                model=self._model_name,
                device=None,
                dimension=None,
                normalised=self._normalize,
                local_execution=True,
                external_api_call=False,
                external_cost="not_applicable",
                detail="embedding provider configuration error",
                safe_error=str(exc),
            )
        except Exception as exc:  # noqa: BLE001
            return EmbeddingHealthResult(
                status="unavailable",
                provider=self.provider_name,
                model=self._model_name,
                device=self._selected_device,
                dimension=self._dimension,
                normalised=self._normalize,
                local_execution=True,
                external_api_call=False,
                external_cost="not_applicable",
                detail="sentence-transformers embedding health check failed",
                safe_error=f"{type(exc).__name__}: {exc}"[:240],
            )


def build_embedding_provider(
    provider: str,
    *,
    model: str = "sentence-transformers/all-MiniLM-L6-v2",
    device: EmbeddingDevice = "cpu",
    batch_size: int = 16,
    normalize: bool = True,
    max_input_characters: int = 12_000,
    lazy_load: bool = True,
) -> EmbeddingProvider:
    """Construct an embedding provider. Never silently falls back from ST → hash."""
    if provider == "hash":
        return HashingEmbeddingProvider()
    if provider == "sentence_transformers":
        return SentenceTransformerEmbeddingProvider(
            model_name=model,
            device=device,
            batch_size=batch_size,
            normalize=normalize,
            max_input_characters=max_input_characters,
            lazy_load=lazy_load,
        )
    raise EmbeddingConfigurationError(
        f"Unsupported EMBEDDING_PROVIDER={provider!r}; approved values: hash, sentence_transformers"
    )


# Process-local cache keyed by configuration identity (reuse model across requests).
_PROVIDER_CACHE: dict[str, EmbeddingProvider] = {}
_PROVIDER_CACHE_LOCK = threading.Lock()


def build_embedding_provider_from_settings(
    settings: Any,
    *,
    use_cache: bool = True,
) -> EmbeddingProvider:
    """Factory entry used by application wiring — one reusable instance per config."""
    key = (
        f"{settings.embedding_provider}|{settings.embedding_model}|"
        f"{settings.embedding_device}|{settings.embedding_batch_size}|"
        f"{settings.embedding_normalize}|{settings.embedding_max_input_characters}"
    )
    if not use_cache:
        return build_embedding_provider(
            settings.embedding_provider,
            model=settings.embedding_model,
            device=settings.embedding_device,
            batch_size=settings.embedding_batch_size,
            normalize=settings.embedding_normalize,
            max_input_characters=settings.embedding_max_input_characters,
        )
    with _PROVIDER_CACHE_LOCK:
        cached = _PROVIDER_CACHE.get(key)
        if cached is not None:
            return cached
        provider = build_embedding_provider(
            settings.embedding_provider,
            model=settings.embedding_model,
            device=settings.embedding_device,
            batch_size=settings.embedding_batch_size,
            normalize=settings.embedding_normalize,
            max_input_characters=settings.embedding_max_input_characters,
        )
        _PROVIDER_CACHE[key] = provider
        return provider


def clear_embedding_provider_cache() -> None:
    """Test helper — drop process-local provider cache."""
    with _PROVIDER_CACHE_LOCK:
        _PROVIDER_CACHE.clear()
