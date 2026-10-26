"""文档检索模块（论文 §4.3 Software Documentation Retrieval）。

切块(512 token, 10% 重叠) → SFR-Embedding-Code-400M_R 向量化 → Top-K 按预算取。
嵌入模型惰性加载，无模型时退化为关键词匹配，保证可导入可单测。
"""
from __future__ import annotations
import os
import sys
from dataclasses import dataclass
from typing import Sequence

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config import settings

_TOKEN_EST_CHARS = 4  # 粗估：1 token ≈ 4 字符


def _approx_tokens(text: str) -> int:
    return max(1, len(text) // _TOKEN_EST_CHARS)


@dataclass
class Chunk:
    text: str
    source_path: str
    index: int


def chunk_document(doc_text: str, source_path: str = "",
                   chunk_tokens: int = 512, overlap_pct: int = 10) -> list[Chunk]:
    """按 token 预算切块，保留 overlap 边界上下文。

    对 snippet 级文档按语法元素切（此处简化为按段落/行块），
    对 file/module 级按 Markdown 标题切（# / ##）。这里用通用滑窗。
    """
    if not doc_text:
        return []
    target_chars = chunk_tokens * _TOKEN_EST_CHARS
    overlap_chars = int(target_chars * overlap_pct / 100)
    step = max(1, target_chars - overlap_chars)
    chunks: list[Chunk] = []
    i, idx = 0, 0
    while i < len(doc_text):
        window = doc_text[i:i + target_chars]
        chunks.append(Chunk(text=window, source_path=source_path, index=idx))
        if i + target_chars >= len(doc_text):
            break
        i += step
        idx += 1
    return chunks


class _Embedder:
    _inst = None

    @classmethod
    def get(cls):
        if cls._inst is not None:
            return cls._inst
        try:
            from sentence_transformers import SentenceTransformer
            cls._inst = SentenceTransformer(settings.embedding_model)
        except Exception:
            cls._inst = False  # 无模型，退化为关键词
        return cls._inst


def _embed(texts: Sequence[str]):
    model = _Embedder.get()
    if model is False:
        return None
    return model.encode(list(texts), convert_to_numpy=True, show_progress_bar=False)


def retrieve(chunks: Sequence[Chunk], query: str, top_k_tokens: int = 2048) -> list[Chunk]:
    """按 token 预算检索 Top-K 相关 chunk。

    有嵌入模型时用余弦相似度；无模型时退化为词项重叠（保流程可跑）。
    """
    if not chunks:
        return []
    vecs = _embed([c.text for c in chunks] + [query])
    if vecs is None:
        return _retrieve_keyword(chunks, query, top_k_tokens)
    import numpy as np
    chunk_vecs = vecs[:-1]
    q_vec = vecs[-1]
    sims = (chunk_vecs @ q_vec) / (
        np.linalg.norm(chunk_vecs, axis=1) * np.linalg.norm(q_vec) + 1e-9)
    order = sims.argsort()[::-1]
    return _pack_by_budget([chunks[i] for i in order], top_k_tokens)


def _retrieve_keyword(chunks: Sequence[Chunk], query: str, budget: int) -> list[Chunk]:
    q_terms = set(query.lower().split())
    scored = []
    for c in chunks:
        terms = set(c.text.lower().split())
        scored.append((len(q_terms & terms), c))
    scored.sort(key=lambda x: -x[0])
    positive = [c for s, c in scored if s > 0]
    return _pack_by_budget(positive or list(chunks), budget)


def _pack_by_budget(ranked: list[Chunk], budget: int) -> list[Chunk]:
    out, used = [], 0
    for c in ranked:
        t = _approx_tokens(c.text)
        if used + t > budget:
            break
        out.append(c)
        used += t
    return out
