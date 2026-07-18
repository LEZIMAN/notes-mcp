"""chunker 单测:切块 / 标题提取 / id 格式。

纯逻辑,毫秒级,不依赖文件 I/O / ollama / Chroma。
"""

from pathlib import Path

from notes_mcp.chunker import (
    _chunk_id,
    _extract_title,
    _split_text,
    chunk_markdown,
)

# —— _split_text(滑动窗口)——


def test_split_text_empty_returns_empty():
    assert _split_text("", 100, 20) == []


def test_split_text_shorter_than_chunk_size_returns_one():
    assert _split_text("短", 100, 20) == ["短"]


def test_split_text_multi_chunk_with_overlap():
    text = "0123456789"
    chunks = _split_text(text, size=5, overlap=2)
    # step=3 → [0:5]="01234", [3:8]="34567", [6:10]="6789", [9:10]="9"
    assert len(chunks) == 4
    assert chunks[0] == "01234"
    assert chunks[1] == "34567"
    assert chunks[2] == "6789"
    assert chunks[3] == "9"


def test_split_text_exact_chunk_size():
    text = "ABCDEF"  # 6 chars
    chunks = _split_text(text, size=3, overlap=0)
    assert len(chunks) == 2
    assert chunks == ["ABC", "DEF"]


# —— _extract_title(取 H1)——


def test_extract_title_from_h1():
    assert _extract_title("# RAG 笔记\n正文") == "RAG 笔记"


def test_extract_title_no_h1_returns_none():
    assert _extract_title("正文\n## 二级") is None


def test_extract_title_h2_before_h1():
    md = "## 二级\n# 真正标题"
    assert _extract_title(md) == "真正标题"


def test_extract_title_empty_content():
    assert _extract_title("") is None


# —— _chunk_id ——


def test_chunk_id_formats_as_source_hash_index():
    src = Path("/notes/RAG.md")
    assert _chunk_id(src, 0) == f"{src}#0"
    assert _chunk_id(src, 3) == f"{src}#3"


# —— chunk_markdown(集成)——


def test_empty_content_returns_empty():
    assert chunk_markdown("", Path("x.md"), Path("root"), mtime=0.0) == []


def test_single_chunk_with_h1_title():
    source = Path("/notes/RAG.md")
    root = Path("/notes")
    chunks = chunk_markdown(
        "# RAG 入门\n检索增强生成。",
        source,
        root,
        mtime=1.5,
        chunk_size=100,
        overlap=20,
    )
    assert len(chunks) == 1
    c = chunks[0]
    assert c.id == _chunk_id(source, 0)
    assert c.text == "# RAG 入门\n检索增强生成。"
    assert c.source == source
    assert c.root == root
    assert c.title == "RAG 入门"
    assert c.chunk_index == 0
    assert c.mtime == 1.5


def test_multi_chunk_index_incrementing():
    source = Path("/notes/Test.md")
    # 每块100,overlap=0 → 300 chars = 3 chunks exact
    content = "A" * 250
    chunks = chunk_markdown(content, source, Path("/root"), 0.0, chunk_size=100, overlap=0)
    assert len(chunks) == 3
    for i, c in enumerate(chunks):
        assert c.chunk_index == i
        assert c.id == _chunk_id(source, i)


def test_title_fallback_to_filename_when_no_h1():
    source = Path("/notes/机器学习.md")
    chunks = chunk_markdown("没有标题", source, Path("/notes"), 0.0, chunk_size=100)
    assert chunks[0].title == "机器学习"
