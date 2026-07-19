"""agent.py — 消费侧 ReAct agent,连多个 MCP server 演示工具动态发现。

用法:
  python agent.py                    # stdio:agent spawn notes-mcp 子进程(默认)
  python agent.py --transport http   # http:连已起的 notes-mcp(先 serve --transport http)

连 3 个 server,工具运行时动态汇总:
  · notes-mcp(自己)  → search_notes / get_note / explain / quiz ...
  · filesystem(官方) → 读写笔记文件(范围:NOTES_DIR)
  · fetch(官方)      → 抓网页

LLM:ollama qwen3:8b。对照笔记⑳:「不改 ReAct 循环,只换工具来源」。
"""

import argparse
import asyncio
import contextlib
import sys
from pathlib import Path

from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from notes_mcp.config import Config

PROJECT_ROOT = Path(__file__).resolve().parent
NOTES_SERVER_HTTP_URL = "http://127.0.0.1:8765/mcp"


def build_servers(transport: str, notes_dir: Path) -> dict:
    """构造 MultiServerMCPClient 的 connections 配置(纯函数,可单测)。

    filesystem/fetch 固定 stdio(npx 拉起官方 server);notes-mcp 按 transport 选
    stdio(spawn 本项目 server 子进程)或 http(连已起的远程 server)。
    """
    servers = {
        "filesystem": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem", str(notes_dir)],
            "transport": "stdio",
        },
        # 注:官方 @modelcontextprotocol/server-fetch 已下架(npm 404,2026)。
        # 如需抓网页,装社区 mcp-fetch-server 或 pip mcp-server-fetch 后在此加回。
    }
    if transport == "http":
        servers["notes-mcp"] = {
            "url": NOTES_SERVER_HTTP_URL,
            "transport": "streamable-http",
        }
    else:
        servers["notes-mcp"] = {
            "command": sys.executable,
            "args": ["-m", "notes_mcp", "serve", "--transport", "stdio"],
            "cwd": str(PROJECT_ROOT),
            "transport": "stdio",
        }
    return servers


def build_llm(config: Config) -> ChatOpenAI:
    """造 LLM(ollama qwen3:8b,走 OpenAI 兼容 /v1 端点)。"""
    return ChatOpenAI(
        base_url=config.ollama_base_url,
        api_key=config.ollama_api_key,
        model=config.ollama_model,
    )


async def chat(agent, tools: list) -> None:
    """命令行对话循环:input → ainvoke → 打印 AI 回复。exit/quit/Ctrl+C 退出。"""
    print(f"\n🤖 agent 就绪,发现 {len(tools)} 个工具: {[t.name for t in tools]}")
    print("输入问题(exit/quit 退出):\n")
    messages = []
    while True:
        try:
            user = input("你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见")
            break
        if not user or user.lower() in ("exit", "quit"):
            print("再见")
            break
        messages.append({"role": "user", "content": user})
        result = await agent.ainvoke({"messages": messages})
        messages = result["messages"]
        print(f"AI: {messages[-1].content}\n")


async def amain(transport: str) -> None:
    """async 主流程:config → LLM → 多 server client → get_tools → agent → 对话。"""
    config = Config.from_env()
    config.validate()
    notes_dir = config.notes_dirs[0]

    llm = build_llm(config)
    client = MultiServerMCPClient(build_servers(transport, notes_dir))
    tools = await client.get_tools()
    if not tools:
        print("⚠️ 没发现任何工具,检查 server 是否可启动(npx / notes-mcp)。", file=sys.stderr)
        return

    agent = create_react_agent(llm, tools)
    await chat(agent, tools)


def main() -> int:
    parser = argparse.ArgumentParser(description="notes-mcp 消费侧 ReAct agent")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default="stdio",
        help="连 notes-mcp 的方式:stdio(spawn 子进程,默认)/ http(连已起 server)",
    )
    args = parser.parse_args()
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(amain(args.transport))
    return 0


if __name__ == "__main__":
    sys.exit(main())
