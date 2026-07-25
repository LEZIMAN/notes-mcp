"""语义检索(纯向量召回)+ 可选 rerank 精排。

链路:
  语义粗召回(bi-encoder,Chroma) → top-N 候选池
  → (可选) rerank 精排(cross-encoder,bge-reranker-v2-m3) → top_k

rerank 解决 bi-encoder 的"distance 近但语义无关"硬凑(见 eval 负例):
cross-encoder 把 (query,doc) 拼一起送模型,捕获交互,精准打分。
无 reranker 时退化为纯语义(向后兼容)。

业务层纯逻辑(开发规范 §2):不 import fastmcp,可直接单测。
"""

from dataclasses import dataclass
from pathlib import Path


@dataclass
class Hit:
    """一条带溯源的检索结果(给 server 拼返回文本用)。"""

    chunk_id: str
    text: str
    score: float  # rerank 分([0,1])或 -distance(越大越相关)
    source: Path
    title: str
    root: Path


class Searcher:
    """语义检索器 + 可选 rerank。依赖注入 collection/embedder/reranker。

    用法:
        searcher = Searcher(collection, embedder)              # 纯语义
        searcher = Searcher(collection, embedder, reranker)    # 语义 + rerank
        hits = searcher.search("RAG 是什么", top_k=5)
    """

    def __init__(self, collection, embedder, reranker=None, candidate_k: int = 20) -> None:
        self._collection = collection
        self._embedder = embedder
        self._reranker = reranker
        self._candidate_k = candidate_k

    @property
    def collection(self):
        """Chroma collection(给 server 列标题/统计用)。"""
        return self._collection

    def search(self, query: str, top_k: int = 5) -> list[Hit]:
        """语义粗召回 → (可选)rerank 精排 → top_k Hit。

        空库时返回空列表,不抛异常。
        """
        total = self._collection.count()
        if total == 0:
            return []

        # 粗召回候选池:有 reranker 时取 candidate_k(扩大给精排),否则取 top_k
        pool = self._candidate_k if self._reranker else top_k
        n = min(max(top_k, pool), total)
        query_vec = self._embedder.embed(query)
        result = self._collection.query(
            query_embeddings=[query_vec],
            n_results=n,
        )
        ids = result["ids"][0] if result["ids"] else []
        if not ids:
            return []
        dists = result["distances"][0] if result.get("distances") else [0.0] * len(ids)

        # 取 docs + metas(rerank 要 doc 文本;Chroma get 顺序不保证,建映射)
        data = self._collection.get(ids=ids, include=["documents", "metadatas"])
        id_to_doc = dict(zip(data["ids"], data["documents"], strict=False))
        id_to_meta = dict(zip(data["ids"], data["metadatas"], strict=False))

        # 排序:有 reranker 用 cross-encoder 分,否则用语义 -distance
        if self._reranker and len(ids) > 1:
            docs = [id_to_doc[c] for c in ids]
            scores = self._reranker.rerank(query, docs)
            ranked = sorted(zip(ids, scores, strict=False), key=lambda x: -x[1])
        else:
            # 语义结果已按 distance 升序(Chroma query 保证),保持原序
            ranked = list(zip(ids, [-d for d in dists], strict=False))

        return self._build_hits(ranked[:top_k], id_to_doc, id_to_meta)

    def _build_hits(self, ranked, id_to_doc, id_to_meta) -> list[Hit]:
        """按排名顺序拼 Hit(ranked=[(cid, score), ...])。"""
        hits: list[Hit] = []
        for cid, score in ranked:
            meta = id_to_meta.get(cid)
            if not meta:
                continue  # 极端:被并发删除
            hits.append(
                Hit(
                    chunk_id=cid,
                    text=id_to_doc.get(cid, ""),
                    score=score,
                    source=Path(meta["source"]),
                    title=meta["title"],
                    root=Path(meta["root"]),
                )
            )
        return hits
