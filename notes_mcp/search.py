"""语义检索(纯向量召回,Chroma 向量库)。

历史:原 hybrid(语义 + BM25 + RRF)已于 2026-07-21 移除——eval 证明 BM25 独占命中=0
且拖累 MRR(踩坑 #23,详见 docs/检索eval报告.md)。简化为纯语义单路。
RRF/BM25 实现见 git 历史。

业务层纯逻辑(开发规范 §2):不 import fastmcp,可直接单测。
"""

from dataclasses import dataclass
from pathlib import Path


@dataclass
class Hit:
    """一条带溯源的检索结果(给 server 拼返回文本用)。"""

    chunk_id: str
    text: str
    score: float  # 语义相似度(越大越相关,-distance 近似)
    source: Path
    title: str
    root: Path


class Searcher:
    """语义检索器。依赖注入 collection/embedder。

    用法:
        searcher = Searcher(collection, embedder)
        hits = searcher.search("RAG 是什么", top_k=5)
    """

    def __init__(self, collection, embedder) -> None:
        self._collection = collection
        self._embedder = embedder

    @property
    def collection(self):
        """Chroma collection(给 server 列标题/统计用)。"""
        return self._collection

    def search(self, query: str, top_k: int = 5) -> list[Hit]:
        """语义检索:embed query → Chroma 查 → top_k 带溯源 Hit。

        空库时返回空列表,不抛异常。
        """
        if self._collection.count() == 0:
            return []

        query_vec = self._embedder.embed(query)
        result = self._collection.query(
            query_embeddings=[query_vec],
            n_results=min(top_k, self._collection.count()),
        )
        ids = result["ids"][0] if result["ids"] else []
        if not ids:
            return []
        dists = result["distances"][0] if result.get("distances") else [0.0] * len(ids)
        # Chroma distance 越小越相似;转成"越大越相关"的 score
        ranked = [(cid, -d) for cid, d in zip(ids, dists, strict=False)]
        return self._build_hits(ranked)

    def _build_hits(self, ranked: list[tuple[str, float]]) -> list[Hit]:
        """从 Chroma 取 chunk_id 对应文本+metadata,拼成 Hit(按入参排名顺序)。

        ⚠️ Chroma collection.get 返回顺序不保证(踩坑 #21),必须建 id→meta 映射后
        按入参排名重排,否则结果顺序错乱。
        """
        chunk_ids = [cid for cid, _ in ranked]
        data = self._collection.get(ids=chunk_ids, include=["documents", "metadatas"])
        id_to_meta = {
            cid: (doc, meta)
            for cid, doc, meta in zip(
                data["ids"], data["documents"], data["metadatas"], strict=False
            )
        }
        hits: list[Hit] = []
        for cid, score in ranked:
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
