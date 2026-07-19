"""Hybrid 检索:语义路(Chroma)+ 关键词路(BM25)+ RRF 融合。

设计文档 §3.2/§6:
  · 两路并行检索,各返 chunk_id 排序列表
  · RRF(Reciprocal Rank Fusion,k=60)融合:无需归一化分数、对异量纲鲁棒
  · 取融合后 top_k,从 Chroma metadata 拼溯源 Hit
  · id 对齐是命门:两路都用 chunk_id(BM25 经 id_map 映射)

业务层纯逻辑(开发规范 §2):不 import fastmcp,可直接单测。
"""

from dataclasses import dataclass
from pathlib import Path

import jieba


@dataclass
class Hit:
    """一条带溯源的检索结果(给 server 拼返回文本用)。"""

    chunk_id: str
    text: str
    score: float  # RRF 融合分(越大越相关)
    source: Path
    title: str
    root: Path


# —— RRF 融合(纯函数,单测核心)————————————————————————————


def rrf_fuse(
    ranked_lists: list[list[str]],
    k: int = 60,
) -> list[tuple[str, float]]:
    """RRF 融合多路排序结果 → 按 RRF 分降序的 [(chunk_id, score)]。

    公式:RRF(d) = Σ 1/(k + rank_r(d)),rank 从 1 起算。
    k=60 是经验默认(设计文档 §6),无需归一化分数尺度。

    Args:
        ranked_lists: 多路排序列表,每路是 chunk_id 列表(按相关性降序)。
        k: RRF 常数,默认 60。

    Returns:
        融合后 (chunk_id, score) 列表,按 score 降序。chunk_id 唯一(多路去重累加)。
    """
    scores: dict[str, float] = {}
    for ranked in ranked_lists:
        for rank, chunk_id in enumerate(ranked, start=1):  # rank 从 1 起
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank)
    # 按分降序;分相同则按 chunk_id 字典序(确定性,便于测试断言)
    return sorted(scores.items(), key=lambda x: (-x[1], x[0]))


# —— Searcher ————————————————————————————————————————————


class Searcher:
    """hybrid 检索器。依赖注入 collection/bm25/id_map/embedder。

    用法:
        searcher = Searcher(collection, bm25, id_map, embedder)
        hits = searcher.search("RAG 是什么", top_k=5)
    """

    def __init__(self, collection, bm25, id_map: list[str], embedder) -> None:
        self._collection = collection
        self._bm25 = bm25
        self._id_map = id_map  # BM25 行号 → chunk_id
        self._embedder = embedder

    @property
    def collection(self):
        """Chroma collection(给 server 列标题/统计用)。"""
        return self._collection

    def search(self, query: str, top_k: int = 5) -> list[Hit]:
        """hybrid 检索:语义路 + 关键词路 → RRF 融合 → top_k 带溯源 Hit。

        空库(bm25 为 None)或无结果时返回空列表,不抛异常。
        """
        if self._bm25 is None or self._collection.count() == 0:
            return []

        sem_ids = self._semantic_rank(query, top_k)
        bm25_ids = self._keyword_rank(query, top_k)

        fused = rrf_fuse([sem_ids, bm25_ids], k=60)[:top_k]
        if not fused:
            return []

        return self._build_hits(fused)

    # —— 两路检索 ————————————————————————————————

    def _semantic_rank(self, query: str, top_k: int) -> list[str]:
        """语义路:embed query → Chroma 查 → 返回 chunk_id 排序列表。"""
        query_vec = self._embedder.embed(query)
        result = self._collection.query(
            query_embeddings=[query_vec],
            n_results=min(top_k, self._collection.count()),
        )
        # result["ids"] 形如 [["id1","id2",...]] (batch=1)
        return list(result["ids"][0]) if result["ids"] else []

    def _keyword_rank(self, query: str, top_k: int) -> list[str]:
        """关键词路:jieba 分词 → BM25 检索 → 经 id_map 映射成 chunk_id。"""
        query_tokens = [list(jieba.cut(query))]  # bm25s 要 batch: list[list[str]]
        results, _scores = self._bm25.retrieve(query_tokens, k=min(top_k, len(self._id_map)))
        # results 形如 [[idx1, idx2, ...]] (batch=1),idx 是 corpus 行号
        indices = results[0] if len(results) > 0 else []
        return [self._id_map[i] for i in indices]

    # —— 拼溯源 Hit ————————————————————————————————

    def _build_hits(self, fused: list[tuple[str, float]]) -> list[Hit]:
        """从 Chroma 取 chunk_id 对应的文本 + metadata,拼成 Hit。"""
        chunk_ids = [cid for cid, _ in fused]
        data = self._collection.get(ids=chunk_ids, include=["documents", "metadatas"])
        # Chroma 返回顺序不保证与入参一致,建 id→index 映射
        id_to_meta = {
            cid: (doc, meta)
            for cid, doc, meta in zip(
                data["ids"], data["documents"], data["metadatas"], strict=False
            )
        }
        hits: list[Hit] = []
        for cid, score in fused:
            if cid not in id_to_meta:
                continue  # 被并发删除等极端情况,跳过
            doc, meta = id_to_meta[cid]
            hits.append(
                Hit(
                    chunk_id=cid,
                    text=doc,
                    score=score,
                    source=Path(meta["source"]),
                    title=meta["title"],
                    root=Path(meta["root"]),
                )
            )
        return hits
