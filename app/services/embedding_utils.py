from __future__ import annotations

import hashlib
import os
import re
import threading
from typing import Iterable, List

import numpy as np

DEFAULT_EMBEDDING_DIM = int(os.environ.get("EMBEDDING_DIM", "768"))
DEFAULT_EMBEDDING_MODEL_NAME = os.environ.get(
    "EMBEDDING_MODEL_NAME", "intfloat/multilingual-e5-base"
)

_MODEL_CACHE = {}
_MODEL_LOCK = threading.Lock()


def _is_hashing_model(model_name: str) -> bool:
    return model_name.startswith("hashing-")


def _is_e5_model(model_name: str) -> bool:
    return "e5" in model_name.lower()


def _get_sentence_model(model_name: str):
    cached = _MODEL_CACHE.get(model_name)
    if cached is not None:
        return cached
    with _MODEL_LOCK:
        cached = _MODEL_CACHE.get(model_name)
        if cached is not None:
            return cached
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError(
                "sentence-transformers is required for embedding models. "
                "Install it before running embedding builds."
            ) from exc
        model = SentenceTransformer(model_name)
        _MODEL_CACHE[model_name] = model
        return model


def _prepare_texts(texts: List[str], model_name: str, is_query: bool) -> List[str]:
    if _is_e5_model(model_name):
        prefix = "query: " if is_query else "passage: "
        return [prefix + (text or "") for text in texts]
    return [text or "" for text in texts]


def embed_texts(
    texts: Iterable[str],
    model_name: str,
    dim: int | None = None,
    *,
    is_query: bool = False,
) -> np.ndarray:
    text_list = list(texts)
    if not text_list:
        out_dim = dim or DEFAULT_EMBEDDING_DIM
        return np.zeros((0, out_dim), dtype=np.float32)

    if _is_hashing_model(model_name):
        if dim is None:
            raise ValueError("dim is required for hashing embeddings.")
        tokens_re = re.compile(r"[0-9A-Za-z\uac00-\ud7a3]+")
        vectors = np.zeros((len(text_list), dim), dtype=np.float32)
        for idx, text in enumerate(text_list):
            tokens = tokens_re.findall((text or "").lower())
            for token in tokens:
                digest = hashlib.md5(token.encode("utf-8")).digest()
                bucket = int.from_bytes(digest, "little") % dim
                vectors[idx, bucket] += 1.0
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        vectors /= norms
        return vectors

    model = _get_sentence_model(model_name)
    prepared = _prepare_texts(text_list, model_name, is_query)
    vectors = model.encode(
        prepared,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    vectors = vectors.astype(np.float32, copy=False)
    if dim is not None and vectors.shape[1] != dim:
        raise ValueError(
            f"Embedding dim mismatch: model={vectors.shape[1]} config={dim}."
        )
    return vectors


def encode_embedding(vector: np.ndarray) -> bytes:
    return vector.astype(np.float32).tobytes()


def decode_embedding(blob: bytes, dim: int) -> np.ndarray | None:
    if blob is None:
        return None
    arr = np.frombuffer(blob, dtype=np.float32)
    if arr.size != dim:
        return None
    return arr
