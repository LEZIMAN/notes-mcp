"""search 单测:Searcher 语义检索集成。

Searcher 用 FakeEmbedder + 真实 Chroma(由 Indexer 建库)。
历史:RRF 纯函数测试随 BM25 一并移除(踩坑 #23,纯语义化)。
"""

import chromadb
import pytest

from notes_mcp.indexer import Indexer
from notes_mcp.search import Hit, Searcher

# —— Searcher 语义检索集成测试 ———————————————————————————————


@pytest.fixture
def searcher(tmp_path):
    """造一个建好库的 Searcher(3 篇笔记,FakeEmbedder)。"""
    from tests.conftest import FakeEmbedder

    d = tmp_path / "notes"
    d.mkdir()
    (d / "RAG.md").write_text("# RAG\n检索增强生成是检索加生成。", encoding="utf-8")
    (d / "Embedding.md").write_text("# Embedding\n把文本变成向量捕捉语义。", encoding="utf-8")
    (d / "ReAct.md").write_text("# ReAct\n推理与行动循环调用工具。", encoding="utf-8")

    embedder = FakeEmbedder(dim=8)
    client = chromadb.EphemeralClient()
    collection = client.get_or_create_collection(f"search_{tmp_path.name}")
    idx = Indexer(
        embedder=embedder,
        collection=collection,
        sqlite_path=tmp_path / "state.db",
    )
    idx.build([d])
    return Searcher(collection, embedder)


def test_search_returns_hits(searcher):
    """search 返回 Hit 列表,非空。"""
    hits = searcher.search("RAG", top_k=3)
    assert len(hits) > 0
    assert all(isinstance(h, Hit) for h in hits)


def test_search_hit_has_provenance(searcher):
    """每条 Hit 带溯源:source/title/root/score。"""
    hits = searcher.search("向量", top_k=2)
    for h in hits:
        assert h.source.name.endswith(".md")
        assert h.title  # 非空
        assert h.root.exists()  # root 是真实目录
        assert isinstance(h.score, float)  # 语义相似度(-distance 近似)


def test_search_respects_top_k(searcher):
    """top_k 限制返回数量。"""
    hits = searcher.search("检索", top_k=1)
    assert len(hits) <= 1


def test_search_keyword_matches_title(searcher):
    """关键词命中标题时,相关笔记应靠前(Embedding 查 embedding)。"""
    hits = searcher.search("Embedding", top_k=3)
    titles = [h.title for h in hits]
    assert "Embedding" in titles


def test_search_empty_library_returns_empty(tmp_path):
    """空库 → 返回空列表,不抛异常。"""
    from tests.conftest import FakeEmbedder

    client = chromadb.EphemeralClient()
    collection = client.get_or_create_collection("empty")
    searcher = Searcher(collection, FakeEmbedder(dim=8))
    assert searcher.search("anything", top_k=5) == []


def test_search_hits_sorted_by_score_desc(searcher):
    """返回的 Hit 按语义相似度降序(score=-distance,越大越相关)。"""
    hits = searcher.search("生成", top_k=5)
    scores = [h.score for h in hits]
    assert scores == sorted(scores, reverse=True)


def test_search_hit_text_from_chunk(searcher):
    """Hit.text 是 chunk 原文(含标题行)。"""
    hits = searcher.search("RAG", top_k=1)
    assert hits
    assert isinstance(hits[0].text, str)
    assert len(hits[0].text) > 0


# —— rerank 测试(用 FakeReranker,不依赖真模型) ————————————————————


class FakeReranker:
    """假 reranker:返回逆序归一化分(doc[0]=0, doc[-1]=1)。

    用于验证 Searcher 是否按 rerank 分重排(而非语义顺序)。
    接口与 notes_mcp.reranker.Reranker 对齐:.rerank(query, docs) → [float]。
    """

    @property
    def name(self) -> str:
        return "fake-reranker"

    def rerank(self, query: str, documents: list[str]) -> list[float]:
        n = len(documents)
        return [i / max(n - 1, 1) for i in range(n)]


def test_search_reranker_reorders(searcher):
    """带 reranker 时,结果按 rerank 分排序(与纯语义顺序不同)。"""
    sem_hits = searcher.search("RAG", top_k=3)
    if len(sem_hits) < 2:
        return  # 候选不足,无法验证重排
    rr_searcher = Searcher(  # noqa: SLF001 — 复用 fixture 的 collection/embedder
        searcher.collection, searcher._embedder, reranker=FakeReranker()
    )
    rr_hits = rr_searcher.search("RAG", top_k=3)
    # FakeReranker 逆序 → rerank 顺序应不同于纯语义
    assert [h.chunk_id for h in rr_hits] != [h.chunk_id for h in sem_hits]


def test_search_rerank_score_normalized(searcher):
    """rerank 后 Hit.score 是归一化分([0,1]),而非 -distance。"""
    rr_searcher = Searcher(  # noqa: SLF001
        searcher.collection, searcher._embedder, reranker=FakeReranker()
    )
    hits = rr_searcher.search("RAG", top_k=3)
    assert hits
    for h in hits:
        assert 0.0 <= h.score <= 1.0
    # 应按 score 降序(rerank 分高的在前)
    scores = [h.score for h in hits]
    assert scores == sorted(scores, reverse=True)

