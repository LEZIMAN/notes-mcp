"""search 单测:RRF 纯函数 + Searcher hybrid 集成。

RRF 部分纯逻辑毫秒级;Searcher 部分用 FakeEmbedder + 真实 Chroma/BM25(由 Indexer 建库)。
"""

import chromadb
import pytest

from notes_mcp.indexer import Indexer
from notes_mcp.search import Hit, Searcher, rrf_fuse

# —— RRF 纯函数测试 ————————————————————————————————————————


def test_rrf_empty_lists_returns_empty():
    assert rrf_fuse([]) == []
    assert rrf_fuse([[], []]) == []


def test_rrf_single_list_passthrough():
    """单路:RRF 分 = 1/(60+rank),顺序不变。"""
    fused = rrf_fuse([["a", "b", "c"]])
    assert [cid for cid, _ in fused] == ["a", "b", "c"]
    # rank=1 → 1/61, rank=2 → 1/62
    scores = {cid: s for cid, s in fused}
    assert abs(scores["a"] - 1 / 61) < 1e-9
    assert abs(scores["b"] - 1 / 62) < 1e-9


def test_rrf_prefers_doc_in_both_lists():
    """两路都靠前的 chunk_id 应排第一(设计文档 §6 示例)。"""
    sem = ["a", "b", "c"]
    bm = ["b", "d", "a"]
    fused = rrf_fuse([sem, bm])
    # b 在 sem 第2、bm 第1 → 分最高
    assert fused[0][0] == "b"


def test_rrf_dedupes_and_accumulates():
    """同一 chunk_id 出现在多路,分数累加(不是去重取一)。"""
    fused = rrf_fuse([["a", "b"], ["a", "c"]])
    scores = dict(fused)
    # a 在两路都第1:1/61 + 1/61
    assert abs(scores["a"] - 2 * (1 / 61)) < 1e-9


def test_rrf_sorted_descending_by_score():
    """结果按 RRF 分降序。"""
    fused = rrf_fuse([["x", "y", "z"], ["y", "z", "w"]])
    scores = [s for _, s in fused]
    assert scores == sorted(scores, reverse=True)


def test_rrf_tiebreak_by_id_is_deterministic():
    """分相同时按 chunk_id 字典序,保证确定性(测试可断言)。"""
    # a/b/c 各出现一次且同 rank → 分相同 → 按 id 排
    fused = rrf_fuse([["a"], ["b"], ["c"]])
    assert [cid for cid, _ in fused] == ["a", "b", "c"]


def test_rrf_custom_k():
    """k 参数影响分数但不影响融合顺序的本质。"""
    fused_default = rrf_fuse([["a", "b"], ["b", "a"]], k=60)
    fused_custom = rrf_fuse([["a", "b"], ["b", "a"]], k=10)
    # 两者都应让 a/b 同分(对称),顺序按 id
    assert [cid for cid, _ in fused_default] == ["a", "b"]
    assert [cid for cid, _ in fused_custom] == ["a", "b"]


# —— Searcher hybrid 集成测试 ———————————————————————————————


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
    collection = client.get_or_create_collection("search_test")
    idx = Indexer(
        embedder=embedder,
        collection=collection,
        sqlite_path=tmp_path / "state.db",
        bm25_dir=tmp_path / "bm25",
    )
    idx.build([d])
    return Searcher(collection, idx.bm25, idx.bm25_id_map, embedder)


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
        assert h.score > 0


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
    """空库(bm25 None)→ 返回空列表,不抛异常。"""
    from tests.conftest import FakeEmbedder

    client = chromadb.EphemeralClient()
    collection = client.get_or_create_collection("empty")
    searcher = Searcher(collection, None, [], FakeEmbedder(dim=8))
    assert searcher.search("anything", top_k=5) == []


def test_search_hits_sorted_by_score_desc(searcher):
    """返回的 Hit 按 RRF 分降序。"""
    hits = searcher.search("生成", top_k=5)
    scores = [h.score for h in hits]
    assert scores == sorted(scores, reverse=True)


def test_search_hit_text_from_chunk(searcher):
    """Hit.text 是 chunk 原文(含标题行)。"""
    hits = searcher.search("RAG", top_k=1)
    assert hits
    assert isinstance(hits[0].text, str)
    assert len(hits[0].text) > 0
