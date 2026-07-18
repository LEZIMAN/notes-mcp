"""Markdown 文本切块器(纯逻辑,不依赖 Chroma/BM25/ollama)。

切块策略:滑动窗口(每个 chunk_size 字符,重叠 overlap)。
标题提取:优先 Markdown H1(# Title),其次用文件名。
Chunk id: "{source}#{chunk_index}",与 Chroma/BM25 的 id 对齐(设计文档 §4.1/§4.3)。
"""

from dataclasses import dataclass
from pathlib import Path

# —— 数据模型 ————————————————————————————————————————————


@dataclass
class Chunk:
    """一个切块,对应 Chroma collection / BM25 索引中的一条。

    id 格式保证全局唯一:不同源文件的 chunk 不会冲突。
    """

    id: str  # "{source}#{chunk_index}",如 "/a/b/RAG.md#0"
    text: str  # 切块文本(保留 markdown 标记)
    source: Path  # 源文件绝对路径
    title: str  # 笔记标题(Markdown H1,其次文件名)
    chunk_index: int  # 该文件内序号(0-based)
    mtime: float  # 源文件修改时间戳
    root: Path  # 所属 NOTES_DIR 根(多目录溯源)


# —— 公共接口 ————————————————————————————————————————————


def chunk_markdown(
    content: str,
    source: Path,
    root: Path,
    mtime: float,
    *,
    chunk_size: int = 300,
    overlap: int = 50,
) -> list[Chunk]:
    """把一篇 markdown 切成 Chunk 列表。

    Args:
        content: markdown 全文。
        source: 源文件的绝对路径。
        root: 所属 NOTES_DIR 根目录(多目录场景用于溯源)。
        mtime: 源文件修改时间戳(由调用方从文件系统取,保持本函数无 I/O)。
        chunk_size: 每块最大字符数(默认 300)。
        overlap: 相邻块重叠字符数(默认 50)。

    Returns:
        Chunk 列表(可能为空,如 content 为空)。chunk_index 从 0 递增。
    """
    title = _extract_title(content) or source.stem
    segments = _split_text(content, chunk_size, overlap)
    return [
        Chunk(
            id=_chunk_id(source, i),
            text=seg,
            source=source,
            title=title,
            chunk_index=i,
            mtime=mtime,
            root=root,
        )
        for i, seg in enumerate(segments)
    ]


# —— 内部实现 ————————————————————————————————————————————


def _extract_title(md: str) -> str | None:
    """从 markdown 文本取第一个 H1 标题(# 开头的行)。去首尾空白与 # 前缀。"""
    for line in md.splitlines():
        stripped = line.strip()
        if stripped.startswith("# ") and not stripped.startswith("## "):
            return stripped[2:].strip()
    return None


def _split_text(text: str, size: int, overlap: int) -> list[str]:
    """滑动窗口切分纯文本。

    Args:
        text: 原始文本。
        size: 窗口大小(字符数)。
        overlap: 相邻窗口重叠字符数。

    Returns:
        片段列表;text 为空时返回空列表。
    """
    if not text:
        return []
    segments: list[str] = []
    pos = 0
    step = size - overlap
    while pos < len(text):
        end = min(pos + size, len(text))
        segments.append(text[pos:end])
        pos += step
        if step <= 0:  # 防御:overlap ≥ size 会导致死循环
            break
    return segments


def _chunk_id(source: Path, index: int) -> str:
    """Chroma/BM25 通用的 chunk 标识: "{source}#{index}"。"""
    return f"{source}#{index}"
