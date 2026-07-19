"""scripts/check_server.py — 真实 stdio 传输 e2e 验证。

用 fastmcp Client 连 `python -m notes_mcp serve --transport stdio` 子进程,
验证三大原语通过真实 stdio 传输可调——等同 inspector / Claude Desktop 部署
(跨进程、真实 JSON-RPC over stdio),比 in-memory 测试更真。

用法:python scripts/check_server.py
"""
import asyncio
import sys
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import StdioTransport

ROOT = Path(__file__).resolve().parent.parent


def _tool_text(result) -> str:
    """从 call_tool 结果取文本(兼容 data / content)。"""
    if getattr(result, "data", None) is not None:
        return str(result.data)
    contents = getattr(result, "content", None)
    if contents:
        return getattr(contents[0], "text", str(contents[0]))
    return str(result)


async def main() -> None:
    transport = StdioTransport(
        command=sys.executable,
        args=["-m", "notes_mcp", "serve", "--transport", "stdio"],
        cwd=str(ROOT),
    )
    print("连接 stdio server(子进程,首次会增量建库)...")
    async with Client(transport) as c:
        tools = await c.list_tools()
        print(f"✅ Tools({len(tools)}): {[t.name for t in tools]}")

        prompts = await c.list_prompts()
        print(f"✅ Prompts({len(prompts)}): {[p.name for p in prompts]}")

        templates = await c.list_resource_templates()
        resources = await c.list_resources()
        print(
            f"✅ Resources: {len(resources)} static + "
            f"templates {[t.uriTemplate for t in templates]}"
        )

        r = await c.call_tool("search_notes", {"query": "RAG", "top_k": 2})
        text = _tool_text(r).replace("\n", " ")
        print(f"✅ search_notes('RAG') → {text[:160]}...")


if __name__ == "__main__":
    asyncio.run(main())
