"""FastMCP server:三大原语(Tools/Resources/Prompts)+ 双传输(协议层)。

开发规范 §3.3:server 是薄封装,只转发业务层,不含检索/建库逻辑。
设计文档 §5:Tools(找,model-controlled)/Resources(拿,application)/Prompts(用,user)。

设计:用工厂 create_mcp(searcher, config) 闭包捕获 searcher。
  · 生产:cli 启动时 build 好 searcher 再 create_mcp → mcp.run
  · 测试:直接注入小库 searcher(不依赖 ollama/真实库)
"""

import json
from pathlib import Path

from fastmcp import FastMCP

from notes_mcp.config import Config
from notes_mcp.search import Hit, Searcher


def create_mcp(searcher: Searcher, config: Config) -> FastMCP:
    """用已建库的 searcher + config 创建 FastMCP server,注册三大原语。"""
    mcp = FastMCP("notes-mcp")

    # —— Tools(找 · model-controlled)———————————————————

    @mcp.tool()
    def search_notes(query: str, top_k: int = 5) -> str:
        """hybrid 检索学习笔记(语义 + 关键词融合),返回带出处。"""
        hits = searcher.search(query, top_k)
        return format_hits(hits)

    @mcp.tool()
    def get_note(title: str) -> str:
        """按标题取整篇笔记。"""
        return _read_note_by_title(title, config.notes_dirs)

    @mcp.tool()
    def list_topics() -> str:
        """列出所有笔记标题(markdown H1)。"""
        titles = _all_titles(searcher.collection)
        if not titles:
            return "知识库为空。"
        return "\n".join(f"- {t}" for t in sorted(titles))

    # —— Resources(拿 · application-controlled)———————————

    @mcp.resource("notes://stats")
    def stats() -> str:
        """知识库统计:笔记数、chunk 数、embedding 模型、笔记目录。"""
        return json.dumps(
            {
                "total_files": len(_all_sources(searcher.collection)),
                "total_chunks": searcher.collection.count(),
                "embed_model": config.embed_model,
                "notes_dirs": [str(d) for d in config.notes_dirs],
            },
            ensure_ascii=False,
            indent=2,
        )

    @mcp.resource("notes://note/{title}")
    def note_by_title(title: str) -> str:
        """按标题取整篇笔记(模板 URI;路径安全,拒绝 ../)。"""
        return _read_note_by_title(title, config.notes_dirs)

    # —— Prompts(用 · user-controlled)P0 核心 ————————————

    @mcp.prompt()
    def explain(concept: str) -> str:
        """用笔记把某概念讲清楚(检索 + 组织讲解 + 举例)。"""
        hits = searcher.search(concept, top_k=5)
        return _prompt_with_context(
            f"请基于以下笔记,把「{concept}」讲清楚。",
            "要求:先给一句话定义,再用类比/举例展开,最后点出常见误区。",
            hits,
        )

    @mcp.prompt()
    def review(topic: str) -> str:
        """生成某主题复习提纲 + 关键点 + 自测题。"""
        hits = searcher.search(topic, top_k=5)
        return _prompt_with_context(
            f"请基于以下笔记,为「{topic}」生成复习材料。",
            "要求:提纲(分层要点)+ 易错点 + 3 道自测题(附答案)。",
            hits,
        )

    @mcp.prompt()
    def quiz(topic: str) -> str:
        """基于笔记出题,检测掌握度(主动回忆)。"""
        hits = searcher.search(topic, top_k=5)
        return _prompt_with_context(
            f"请基于以下笔记,围绕「{topic}」出 5 道题考我。",
            "要求:题型混合(选择/填空/简答),先出题,我答后再给答案与解析。",
            hits,
        )

    @mcp.prompt()
    def compare(a: str, b: str) -> str:
        """对比两个概念(检索 + 制对比表)。"""
        hits = _merge_hits(searcher.search(a, top_k=3), searcher.search(b, top_k=3))
        return _prompt_with_context(
            f"请基于以下笔记,对比「{a}」与「{b}」。",
            "要求:用表格从 定义/原理/适用场景/联系 等维度对比,并指出关键区别。",
            hits,
        )

    return mcp


# —— 文本格式化(tool / prompt 共用)——————————————————————


def format_hits(hits: list[Hit]) -> str:
    """把检索结果拼成带出处的文本(search_notes 返回)。"""
    if not hits:
        return "知识库里没找到相关笔记。"
    parts = []
    for i, h in enumerate(hits, 1):
        parts.append(f"### {i}. {h.title}\n\n{h.text}\n\n*来源:{h.source}*")
    return "\n\n".join(parts)


def _prompt_with_context(task: str, requirement: str, hits: list[Hit]) -> str:
    """拼 prompt:任务 + 参考资料 + 要求(给 LLM 的完整指令)。"""
    context = format_hits(hits) if hits else "(知识库中无直接相关笔记,可结合通用知识作答。)"
    return f"{task}\n\n**参考资料:**\n\n{context}\n\n**{requirement}**"


def _merge_hits(*groups: list[Hit]) -> list[Hit]:
    """合并多组 hits,按 chunk_id 去重(顺序保留首次出现)。"""
    seen: set[str] = set()
    merged: list[Hit] = []
    for group in groups:
        for h in group:
            if h.chunk_id not in seen:
                seen.add(h.chunk_id)
                merged.append(h)
    return merged


# —— 内部辅助(读笔记 / 列标题)——————————————————————————


def _read_note_by_title(title: str, notes_dirs: list[Path]) -> str:
    """按标题取笔记:先按文件名匹配(含子目录),再按 H1 标题匹配。

    路径安全:is_relative_to 防 ../ 遍历。
    """
    for root in notes_dirs:
        root_resolved = Path(root).resolve()
        # 策略 1:文件名匹配(扫描子目录找 {title}.md)
        try:
            for md_path in root_resolved.rglob(f"{title}.md"):
                if md_path.resolve().is_relative_to(root_resolved):
                    return md_path.read_text(encoding="utf-8")
        except (OSError, PermissionError):
            pass
        # 策略 2:按 H1 标题匹配(扫 .md 文件,取第一行的 # 标题)
        try:
            for md_path in root_resolved.rglob("*.md"):
                if not md_path.resolve().is_relative_to(root_resolved):
                    continue
                with open(md_path, encoding="utf-8") as f:
                    first_line = f.readline().strip()
                h1 = first_line.lstrip("#").strip()
                if h1 == title:
                    return md_path.read_text(encoding="utf-8")
        except (OSError, PermissionError):
            continue
    return f"未找到标题为「{title}」的笔记。"


def _all_titles(collection) -> set[str]:
    """从 Chroma 取所有 distinct 笔记标题。"""
    data = collection.get(include=["metadatas"])
    return {m["title"] for m in data["metadatas"]}


def _all_sources(collection) -> set[str]:
    """从 Chroma 取所有 distinct 源文件路径(算笔记数)。"""
    data = collection.get(include=["metadatas"])
    return {m["source"] for m in data["metadatas"]}
