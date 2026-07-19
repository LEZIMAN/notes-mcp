"""Indexer 单测:增量建库四态 + touch + 多目录 + 容错 + BM25 持久化。

用 FakeEmbedder + Chroma EphemeralClient + tmp sqlite/bm25_dir,
不依赖真实 ollama / 持久 Chroma。
"""

import json

import chromadb
import pytest

from notes_mcp.indexer import Indexer, IndexerError

# —— fixtures ————————————————————————————————————————————


@pytest.fixture
def make_indexer(tmp_path):
    """工厂:造一个用 EphemeralClient + FakeEmbedder 的 Indexer。"""
    from tests.conftest import FakeEmbedder

    def _make(dim=8):
        client = chromadb.EphemeralClient()
        collection = client.get_or_create_collection(f"test_{dim}")
        embedder = FakeEmbedder(dim=dim)
        return Indexer(
            embedder=embedder,
            collection=collection,
            sqlite_path=tmp_path / "state.db",
            bm25_dir=tmp_path / "bm25",
        )

    return _make


@pytest.fixture
def notes_dir(tmp_path):
    """造一个含 3 篇 .md 的笔记目录。"""
    d = tmp_path / "notes"
    d.mkdir()
    (d / "RAG.md").write_text("# RAG\n检索增强生成是检索加生成。", encoding="utf-8")
    (d / "Embedding.md").write_text("# Embedding\n把文本变成向量捕捉语义。", encoding="utf-8")
    (d / "ReAct.md").write_text("# ReAct\n推理与行动循环调用工具。", encoding="utf-8")
    return d


# —— 首次建库 ————————————————————————————————————————————


def test_first_build_indexes_all_files(make_indexer, notes_dir):
    """首次 build:3 篇笔记全部新增,BuildResult 统计正确。"""
    idx = make_indexer()
    result = idx.build([notes_dir])

    assert result.added == 3
    assert result.modified == 0
    assert result.deleted == 0
    assert result.total_files == 3
    assert result.total_chunks > 0


def test_first_build_stores_chunks_in_chroma(make_indexer, notes_dir):
    """建库后 Chroma 有对应 chunk,且 metadata 含 source/title/root。"""
    idx = make_indexer()
    idx.build([notes_dir])

    data = idx.collection.get(include=["metadatas"])
    assert len(data["ids"]) > 0
    sources = {m["source"] for m in data["metadatas"]}
    assert any("RAG.md" in s for s in sources)
    titles = {m["title"] for m in data["metadatas"]}
    assert "RAG" in titles


def test_first_build_creates_bm25(make_indexer, notes_dir):
    """建库后 BM25 非 None,id_map 长度 == chunk 数。"""
    idx = make_indexer()
    idx.build([notes_dir])

    assert idx.bm25 is not None
    assert len(idx.bm25_id_map) == idx.collection.count()


# —— 增量:新增 ———————————————————————————————————————————


def test_incremental_added(make_indexer, notes_dir):
    """第二次 build 加一篇 → added=1,其余 0。"""
    idx = make_indexer()
    idx.build([notes_dir])

    (notes_dir / "新笔记.md").write_text("# 新\n新内容。", encoding="utf-8")
    result = idx.build([notes_dir])

    assert result.added == 1
    assert result.modified == 0
    assert result.deleted == 0


# —— 增量:修改 ———————————————————————————————————————————


def test_incremental_modified(make_indexer, notes_dir):
    """改一篇内容 → modified=1,旧 chunk 被删、新 chunk 入库。"""
    idx = make_indexer()
    idx.build([notes_dir])

    target = notes_dir / "RAG.md"
    target.write_text("# RAG\n完全不同的新内容,讲向量检索。", encoding="utf-8")
    result = idx.build([notes_dir])

    assert result.modified == 1
    # chunk 数应保持稳定(同样篇幅量级)
    assert idx.collection.count() > 0


def test_incremental_modified_replaces_chunks(make_indexer, notes_dir):
    """修改后,该文件旧 chunk 不残留(按 source 查数量一致)。"""
    idx = make_indexer()
    idx.build([notes_dir])

    target = notes_dir / "RAG.md"
    target.write_text("# RAG\n改短。", encoding="utf-8")
    idx.build([notes_dir])

    rag_chunks = idx.collection.get(
        where={"source": str((notes_dir / "RAG.md").resolve())}, include=["metadatas"]
    )
    # 内容改短后 chunk 应较少;关键是源唯一对应
    titles = {m["title"] for m in rag_chunks["metadatas"]}
    assert titles == {"RAG"}


# —— 增量:touch(mtime 变 hash 没变)——————————————————————


def test_incremental_touch_skips_reindex(make_indexer, notes_dir):
    """touch(只改 mtime 不改内容)→ skipped=1,不重 embed。"""
    idx = make_indexer()
    idx.build([notes_dir])

    target = notes_dir / "RAG.md"
    # 改 mtime 但内容不变
    import os

    new_mtime = target.stat().st_mtime + 100
    os.utime(target, (new_mtime, new_mtime))
    count_before = idx.collection.count()

    result = idx.build([notes_dir])

    assert result.skipped == 1
    assert result.added == 0
    assert result.modified == 0
    assert idx.collection.count() == count_before  # 没重 embed,count 不变


# —— 增量:删除 ———————————————————————————————————————————


def test_incremental_deleted(make_indexer, notes_dir):
    """删一篇 → deleted=1,Chroma 无该文件残留。"""
    idx = make_indexer()
    idx.build([notes_dir])

    target = notes_dir / "RAG.md"
    target_resolved = str(target.resolve())
    target.unlink()
    result = idx.build([notes_dir])

    assert result.deleted == 1
    remaining = idx.collection.get(where={"source": target_resolved}, include=["documents"])
    assert len(remaining["ids"]) == 0


# —— 多目录溯源 ————————————————————————————————————————————


def test_multi_dirs_track_root(make_indexer, tmp_path):
    """两个 NOTES_DIR → chunk metadata.root 各自正确。"""
    d1 = tmp_path / "库1"
    d2 = tmp_path / "库2"
    d1.mkdir()
    d2.mkdir()
    (d1 / "a.md").write_text("# A\n内容A。", encoding="utf-8")
    (d2 / "b.md").write_text("# B\n内容B。", encoding="utf-8")

    idx = make_indexer()
    idx.build([d1, d2])

    roots = {m["root"] for m in idx.collection.get(include=["metadatas"])["metadatas"]}
    assert str(d1.resolve()) in roots
    assert str(d2.resolve()) in roots


# —— 容错:单文件读失败 ————————————————————————————————————


def test_corrupt_file_is_skipped(make_indexer, notes_dir):
    """一篇坏 .md(非 UTF-8 二进制)→ skip,其他正常,errors 记录。"""
    idx = make_indexer()

    # 写一个含非法 UTF-8 字节的文件
    bad = notes_dir / "坏文件.md"
    bad.write_bytes(b"\xff\xfe\x00bad binary")

    result = idx.build([notes_dir])

    assert result.added == 3  # 3 篇正常
    assert len(result.errors) == 1  # 1 篇跳过
    assert any("坏文件" in e for e in result.errors)


def test_empty_file_is_skipped(make_indexer, notes_dir):
    """空文件 → skip(切不出 chunk)。"""
    idx = make_indexer()
    (notes_dir / "空.md").write_text("", encoding="utf-8")

    result = idx.build([notes_dir])

    assert result.added == 3
    assert len(result.errors) == 1


# —— embed 失败 → 整体崩 ————————————————————————————————————


def test_embed_failure_raises_indexer_error(make_indexer, notes_dir):
    """embedder.embed 抛异常 → IndexerError(整体崩,不部分入库)。"""

    class BrokenEmbedder:
        dim = 8
        name = "broken"

        def embed(self, text):
            raise ConnectionError("ollama 挂了")

    client = chromadb.EphemeralClient()
    idx = Indexer(
        embedder=BrokenEmbedder(),
        collection=client.get_or_create_collection("broken"),
        sqlite_path=notes_dir.parent / "state.db",
        bm25_dir=notes_dir.parent / "bm25",
    )

    with pytest.raises(IndexerError, match="ollama"):
        idx.build([notes_dir])


# —— 排除目录 ————————————————————————————————————————————


def test_exclude_dirs_not_indexed(make_indexer, notes_dir):
    """notes_dir 下的 venv/ 里的 .md 不被索引。"""

    venv_dir = notes_dir / "venv"
    venv_dir.mkdir()
    (venv_dir / "dep.md").write_text("# 依赖\n不该被索引。", encoding="utf-8")

    idx = make_indexer()
    result = idx.build([notes_dir])

    assert result.added == 3  # 只 3 篇真实笔记,venv/dep.md 排除
    sources = {m["source"] for m in idx.collection.get(include=["metadatas"])["metadatas"]}
    assert not any("venv" in s for s in sources)


# —— BM25 持久化 + load ————————————————————————————————————


def test_bm25_persisted_to_disk(make_indexer, notes_dir, tmp_path):
    """build 后 bm25_dir 有 index/ 和 id_map.json。"""
    idx = make_indexer()
    idx.build([notes_dir])

    assert (idx._bm25_dir / "index").exists()
    id_map_file = idx._bm25_dir / "id_map.json"
    assert id_map_file.exists()
    id_map = json.loads(id_map_file.read_text(encoding="utf-8"))
    assert len(id_map) == idx.collection.count()


def test_load_restores_bm25(make_indexer, notes_dir, tmp_path):
    """新 Indexer 实例 load() 能从磁盘恢复 BM25 + id_map。"""
    idx1 = make_indexer()
    idx1.build([notes_dir])
    chunk_count = idx1.collection.count()

    # 新实例(模拟 server 重启),指向同一 sqlite/bm25_dir
    client = chromadb.EphemeralClient()
    idx2 = Indexer(
        embedder=idx1._embedder,
        collection=client.create_collection("reload"),
        sqlite_path=idx1._sqlite_path,
        bm25_dir=idx1._bm25_dir,
    )

    assert idx2.load() is True
    assert idx2.bm25 is not None
    assert len(idx2.bm25_id_map) == chunk_count


def test_load_returns_false_when_no_persist(make_indexer, tmp_path):
    """bm25_dir 为空时 load() 返回 False,不抛异常。"""
    idx = make_indexer()
    assert idx.load() is False
    assert idx.bm25 is None


# —— id 对齐(BM25 行号 ↔ chunk_id)——————————————————————


def test_bm25_id_map_aligns_with_chroma(make_indexer, notes_dir):
    """id_map 的每个 chunk_id 都能在 Chroma 找到对应记录。"""
    idx = make_indexer()
    idx.build([notes_dir])

    chroma_ids = set(idx.collection.get(include=[])["ids"])
    for chunk_id in idx.bm25_id_map:
        assert chunk_id in chroma_ids


def test_bm25_id_format_matches_chunker(make_indexer, notes_dir):
    """id_map 的 chunk_id 符合 {source}#{index} 格式。"""
    idx = make_indexer()
    idx.build([notes_dir])

    for chunk_id in idx.bm25_id_map:
        assert "#" in chunk_id
        source_part, index_part = chunk_id.rsplit("#", 1)
        assert index_part.isdigit()
        assert source_part.endswith(".md")
