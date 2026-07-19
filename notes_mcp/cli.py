"""CLI 组装层:把 config/indexer/searcher/server 串起来。

命令:
  python -m notes_mcp serve --transport stdio|http  # 起 MCP server
  python -m notes_mcp index                          # 手动建库(不启 server)
  python -m notes_mcp query "RAG"                    # 命令行直查(不启 MCP)

生产入口:serve 流程为 config → 持久 Chroma → Indexer.build → Searcher → create_mcp → mcp.run。
stdio 模式禁 print(污染 JSON-RPC),全程用 logging。
"""

import argparse
import logging
import sys

import chromadb

from notes_mcp.config import Config, ConfigError
from notes_mcp.embedder import OllamaEmbedder
from notes_mcp.indexer import Indexer, IndexerError
from notes_mcp.search import Searcher
from notes_mcp.server import create_mcp, format_hits

logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    """CLI 入口。argv=None 时读 sys.argv(便于测试传参)。"""
    args = _build_parser().parse_args(argv)
    _setup_logging(getattr(args, "log_level", "INFO"))

    try:
        config = Config.from_env()
        config.validate()
    except ConfigError as e:
        print(f"配置错误,无法启动:\n{e}", file=sys.stderr)
        print("提示:检查 .env(可 cp .env.example .env),尤其 NOTES_DIR。", file=sys.stderr)
        return 2

    if args.command == "index":
        return _cmd_index(config)
    if args.command == "query":
        return _cmd_query(config, args.query, args.top_k)
    if args.command == "serve":
        return _cmd_serve(config, args.transport, args.host, args.port)
    return 1  # 不可达(argparse required)


# —— serve:起 MCP server ————————————————————————————————


def _cmd_serve(config: Config, transport: str, host: str, port: int) -> int:
    """建库 → 造 searcher → create_mcp → mcp.run。"""
    searcher, _result = _build_searcher(config)
    mcp = create_mcp(searcher, config)

    if transport == "stdio":
        logger.info("notes-mcp 启动(stdio,供 Claude Desktop / inspector 调)")
        mcp.run(transport="stdio")
    else:
        logger.info("notes-mcp 启动(HTTP %s:%s)", host, port)
        mcp.run(transport="http", host=host, port=port)
    return 0


# —— index:只建库 ————————————————————————————————————————


def _cmd_index(config: Config) -> int:
    """手动建库,打印统计,不启 server。"""
    _result = _build_index(config)
    return 0


# —— query:命令行直查 —————————————————————————————————————


def _cmd_query(config: Config, query: str, top_k: int) -> int:
    """建库后直接检索,print 结果(query 不走 MCP)。"""
    searcher, _result = _build_searcher(config)
    hits = searcher.search(query, top_k=top_k)
    print(format_hits(hits))  # query 是命令行工具,允许 print
    return 0


# —— 共用:建库 / 造 searcher ———————————————————————————————


def _build_index(config: Config):
    """造 Indexer 并增量建库,返回 (indexer, BuildResult)。失败抛 SystemExit。"""
    embedder = OllamaEmbedder(
        base_url=config.ollama_base_url,
        model=config.embed_model,
        api_key=config.ollama_api_key,
    )
    collection = _get_collection(config)
    indexer = Indexer(
        embedder=embedder,
        collection=collection,
        sqlite_path=config.sqlite_path,
        bm25_dir=_bm25_dir(config),
    )
    indexer.load()
    try:
        result = indexer.build(config.notes_dirs, config.chunk_size, config.overlap)
    except IndexerError as e:
        print(f"建库失败:\n{e}", file=sys.stderr)
        print(
            "提示:确认 ollama 已启动(ollama serve)且已拉模型(ollama pull bge-m3)。", file=sys.stderr
        )
        raise SystemExit(3) from e
    logger.info(
        "建库完成:+%d ~%d -%d(跳过 %d,未变 %d)→ 共 %d 文件 / %d chunks",
        result.added,
        result.modified,
        result.deleted,
        result.skipped,
        result.unchanged,
        result.total_files,
        result.total_chunks,
    )
    if result.errors:
        logger.warning("跳过 %d 个文件:%s", len(result.errors), result.errors[:3])
    return indexer, result


def _build_searcher(config: Config) -> tuple[Searcher, object]:
    """建库后造 Searcher,返回 (searcher, BuildResult)。"""
    indexer, result = _build_index(config)
    searcher = Searcher(
        collection=indexer.collection,
        bm25=indexer.bm25,
        id_map=indexer.bm25_id_map,
        embedder=indexer._embedder,  # noqa: SLF001 — 复用同一 embedder
    )
    return searcher, result


def _get_collection(config: Config):
    """持久 Chroma collection(生产用;测试用 EphemeralClient 注入)。

    collection 名带 embedding 维度,避免不同模型向量混进同一库(设计文档 §4.1)。
    """
    client = chromadb.PersistentClient(path=str(config.chroma_path))
    name = f"notes_{config.embed_model}_1024"  # bge-m3 固定 1024 维
    return client.get_or_create_collection(name)


def _bm25_dir(config: Config):
    """BM25 持久化目录(与 chroma 同级 data/ 下)。"""
    return config.chroma_path.parent / "bm25"


def _setup_logging(level: str) -> None:
    """配置 logging(stdio 模式下日志走 stderr,不污染 stdout 的 JSON-RPC)。"""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,
    )


def _build_parser() -> argparse.ArgumentParser:
    """构造 argparse:serve / index / query。"""
    parser = argparse.ArgumentParser(
        prog="python -m notes_mcp",
        description="notes-mcp:把 markdown 笔记目录变成 MCP 知识助手 server",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_serve = sub.add_parser("serve", help="起 MCP server")
    p_serve.add_argument("--transport", choices=["stdio", "http"], default="stdio", help="传输方式")
    p_serve.add_argument("--host", default="127.0.0.1", help="HTTP 模式监听地址")
    p_serve.add_argument("--port", type=int, default=8765, help="HTTP 模式端口")
    p_serve.add_argument("--log-level", default="INFO", help="日志级别")

    p_index = sub.add_parser("index", help="手动建库(不启 server)")
    p_index.add_argument("--log-level", default="INFO")

    p_query = sub.add_parser("query", help="命令行直查(不启 MCP)")
    p_query.add_argument("query", help="查询文本")
    p_query.add_argument("--top-k", type=int, default=5, help="返回条数")
    p_query.add_argument("--log-level", default="INFO")

    return parser


if __name__ == "__main__":
    sys.exit(main())
