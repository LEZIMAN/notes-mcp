"""server 单测:FastMCP in-memory Client 验证三大原语注册 + 调用。

用 FakeEmbedder + 临时 notes 建小库,create_mcp 后用 Client(同进程,毫秒级)。
开发规范 §5.1:in-memory Client 跑真实 MCP 协议,不部署。
"""

import json

import chromadb
import pytest
from fastmcp import Client

from notes_mcp.config import Config
from notes_mcp.indexer import Indexer
from notes_mcp.search import Searcher
from notes_mcp.server import create_mcp
from tests.conftest import FakeEmbedder


@pytest.fixture
def app(tmp_path):
    """造一个建好库的 FastMCP app(3 篇笔记)。"""
    d = tmp_path / "notes"
    d.mkdir()
    (d / "RAG.md").write_text("# RAG\n检索增强生成是检索加生成。", encoding="utf-8")
    (d / "Embedding.md").write_text("# Embedding\n把文本变成向量捕捉语义。", encoding="utf-8")
    (d / "ReAct.md").write_text("# ReAct\n推理与行动循环调用工具。", encoding="utf-8")

    embedder = FakeEmbedder(dim=8)
    client = chromadb.EphemeralClient()
    collection = client.get_or_create_collection(f"server_{tmp_path.name}")
    idx = Indexer(embedder, collection, tmp_path / "state.db", tmp_path / "bm25")
    idx.build([d])

    config = Config.from_env(env_file=tmp_path / "noenv")
    config.notes_dirs = [d]
    searcher = Searcher(collection, idx.bm25, idx.bm25_id_map, embedder)
    return create_mcp(searcher, config)


# —— Tools 注册与调用 ————————————————————————————————————


async def test_tools_registered(app):
    """list_tools 含三大 tool。"""
    async with Client(app) as c:
        tools = await c.list_tools()
    names = {t.name for t in tools}
    assert {"search_notes", "get_note", "list_topics"} <= names


async def test_search_notes_tool_returns_text(app):
    """call_tool search_notes 返回带出处的文本。"""
    async with Client(app) as c:
        result = await c.call_tool("search_notes", {"query": "RAG", "top_k": 3})
    text = _tool_text(result)
    assert "来源" in text or "RAG" in text


async def test_get_note_tool_returns_full_note(app):
    """get_note 按标题返回整篇(含标题行)。"""
    async with Client(app) as c:
        result = await c.call_tool("get_note", {"title": "RAG"})
    text = _tool_text(result)
    assert "检索增强生成" in text


async def test_get_note_unknown_title(app):
    """get_note 不存在的标题 → 友好提示,不抛异常。"""
    async with Client(app) as c:
        result = await c.call_tool("get_note", {"title": "不存在"})
    text = _tool_text(result)
    assert "未找到" in text


async def test_list_topics_tool(app):
    """list_topics 列出所有标题。"""
    async with Client(app) as c:
        result = await c.call_tool("list_topics", {})
    text = _tool_text(result)
    assert "RAG" in text
    assert "Embedding" in text
    assert "ReAct" in text


# —— Resources ————————————————————————————————————————————


async def test_stats_resource(app):
    """notes://stats 返回 JSON 统计。"""
    async with Client(app) as c:
        result = await c.read_resource("notes://stats")
    text = _resource_text(result)
    stats = json.loads(text)
    assert stats["total_files"] == 3
    assert stats["total_chunks"] > 0
    assert stats["embed_model"] == "bge-m3"


async def test_note_by_title_resource(app):
    """notes://note/{title} 模板取整篇。"""
    async with Client(app) as c:
        result = await c.read_resource("notes://note/RAG")
    text = _resource_text(result)
    assert "检索增强生成" in text


async def test_note_by_title_path_traversal_blocked(app):
    """notes://note/../x 路径遍历被拦(返回未找到,不读库外文件)。"""
    async with Client(app) as c:
        result = await c.read_resource("notes://note/..%2F..%2Fetc%2Fpasswd")
    text = _resource_text(result)
    assert "未找到" in text


async def test_resources_registered(app):
    """list_resources / list_resource_templates 含 notes://stats 和模板。"""
    async with Client(app) as c:
        templates = await c.list_resource_templates()
    uris = {t.uriTemplate for t in templates}
    assert "notes://note/{title}" in uris


# —— Prompts(P0)————————————————————————————————————————


async def test_prompts_registered(app):
    """list_prompts 含 4 个 P0 prompt。"""
    async with Client(app) as c:
        prompts = await c.list_prompts()
    names = {p.name for p in prompts}
    assert {"explain", "review", "quiz", "compare"} <= names


async def test_explain_prompt_includes_context_and_instruction(app):
    """explain prompt 含检索参考资料 + 讲解要求。"""
    async with Client(app) as c:
        result = await c.get_prompt("explain", {"concept": "RAG"})
    text = _prompt_text(result)
    assert "RAG" in text
    assert "参考资料" in text
    assert "定义" in text  # 要求里


async def test_compare_prompt_takes_two_args(app):
    """compare 接 a/b 两参数,检索两路。"""
    async with Client(app) as c:
        result = await c.get_prompt("compare", {"a": "RAG", "b": "ReAct"})
    text = _prompt_text(result)
    assert "RAG" in text
    assert "ReAct" in text
    assert "对比" in text


# —— 辅助:从 fastmcp 结果取文本(兼容 content/data)——————————————


def _tool_text(result) -> str:
    """call_tool 结果 → 文本(优先 data,回退 content[0].text)。"""
    if getattr(result, "data", None) is not None:
        return str(result.data)
    contents = getattr(result, "structured_content", None) or getattr(result, "content", [])
    if contents and len(contents) > 0:
        first = contents[0]
        return getattr(first, "text", str(first))
    return str(result)


def _resource_text(result) -> str:
    """read_resource 结果 → 文本(fastmcp 3.x 返回 list[TextResourceContents])。"""
    items = result if isinstance(result, list) else getattr(result, "contents", None) or []
    if items:
        return getattr(items[0], "text", str(items[0]))
    return str(result)


def _prompt_text(result) -> str:
    """get_prompt 结果 → 拼 messages 文本。"""
    messages = getattr(result, "messages", None) or []
    parts = []
    for m in messages:
        role = getattr(m, "role", "")
        content = getattr(m, "content", "")
        if hasattr(content, "text"):
            content = content.text
        parts.append(f"{role}: {content}")
    return "\n".join(parts) if parts else str(result)
