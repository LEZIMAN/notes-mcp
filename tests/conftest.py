"""公共测试 fixtures(开发规范 §5.3)。

⚠️ 官方提醒:别在 fixture 里 open FastMCP Client(event loop 坑),
在 test 内 `async with Client(server) as c` 才安全。
"""

import hashlib
from collections.abc import Callable
from pathlib import Path

import pytest


class FakeEmbedder:
    """假嵌入器(测试用,不依赖 ollama)。

    用文本的 shake 摘要生成**确定性**向量:同输入永远同输出,
    让 Chroma/BM25/RRF 测试可重复。维度默认 8(够测、快),
    与真实 bge-m3(1024 维)无关——测试只关心:
      ① 同文本 → 同向量(确定性)
      ② 向量长度 == dim
    接口与未来 OllamaEmbedder 对齐:.embed() / .dim / .name,
    这样 Indexer/Searcher 的依赖注入在测试里直接换上它即可。
    """

    def __init__(self, dim: int = 8, name: str = "fake") -> None:
        self._dim = dim
        self._name = name

    @property
    def dim(self) -> int:
        """向量维度。"""
        return self._dim

    @property
    def name(self) -> str:
        """嵌入器名(参与 Chroma collection 命名,如 notes_fake_8)。"""
        return self._name

    def embed(self, text: str) -> list[float]:
        """文本 → dim 维确定性向量(无真实语义,仅供测试)。"""
        # shake_128 可生成任意长度摘要,适配任意 dim(含真实 1024)
        digest = hashlib.shake_128(text.encode("utf-8")).digest(self._dim)
        return [(byte - 128) / 128.0 for byte in digest]

    def embed_batch(self, texts: list[str], batch_size: int = 128) -> list[list[float]]:
        """批量嵌入(fake:循环调 embed,顺序与输入一致)。"""
        return [self.embed(t) for t in texts]


@pytest.fixture
def fake_embedder() -> FakeEmbedder:
    """默认假 embedder(dim=8),不依赖 ollama。"""
    return FakeEmbedder(dim=8)


@pytest.fixture
def make_embedder() -> Callable[..., FakeEmbedder]:
    """工厂:造任意 dim/name 的 FakeEmbedder(测维度可配置性)。"""

    def _make(dim: int = 8, name: str = "fake") -> FakeEmbedder:
        return FakeEmbedder(dim=dim, name=name)

    return _make


@pytest.fixture
def tmp_notes(tmp_path: Path) -> Path:
    """临时笔记目录(几篇 .md),测完自动清(借 pytest 的 tmp_path)。"""
    notes = [
        ("RAG.md", "# RAG\n检索增强生成 = 检索 + 生成。"),
        ("Embedding.md", "# Embedding\n把文本变成向量,捕捉语义。"),
        ("ReAct.md", "# ReAct\nReason + Act 循环,LLM 边想边调工具。"),
    ]
    for filename, content in notes:
        (tmp_path / filename).write_text(content, encoding="utf-8")
    return tmp_path


@pytest.fixture
def memory_chroma():
    """内存 Chroma client(测完即销毁,不落盘)。

    等 indexer.py 实现后,Indexer 通过依赖注入接收它。
    延迟 import,避免收集阶段就强依赖 chromadb。
    """
    import chromadb

    return chromadb.EphemeralClient()
