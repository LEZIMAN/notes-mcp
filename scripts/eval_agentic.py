"""Agentic RAG eval:对比 deep_search(rewrite+search)vs search_notes(基线)。

数据集:eval/queries_rewrite.jsonl(口语化/关键词不全 query,带 relevant_files)。
双方法:
  - 基线(search_notes):Searcher.search(query, top_k)
  - Agentic(deep_search):QueryRewriter.rewrite(query) → Searcher.search(rewritten, top_k)
指标:recall@1/3/5 + MRR。
验证:口语化 query,deep_search recall > 基线(rewrite 补正式术语后命中更好)。

用法:python scripts/eval_agentic.py
输出:终端 + docs/04-测试/AgenticRAG-rewrite_<日期>_v<版本>-<githash>.md
"""

import os

# reranker 离线(踩坑 #27:避免 huggingface_hub 联网超时)
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

import json
import logging
import subprocess
import sys
import time
from pathlib import Path

from notes_mcp import __version__ as PKG_VERSION
from notes_mcp.agentic.rewriter import QueryRewriter
from notes_mcp.cli import _build_searcher
from notes_mcp.config import Config

EVAL_FILE = Path(__file__).resolve().parent.parent / "eval" / "queries_rewrite.jsonl"
REPORT_DIR = Path(__file__).resolve().parent.parent / "docs" / "04-测试"
K_LIST = [1, 3, 5]
MAX_K = max(K_LIST)
METHODS = ["基线(search)", "Agentic(deep)"]

logger = logging.getLogger(__name__)


def get_version() -> tuple[str, str]:
    try:
        git_hash = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=Path(__file__).resolve().parent.parent,
            stderr=subprocess.DEVNULL,
        ).decode().strip()
    except Exception:
        git_hash = "nogit"
    return f"v{PKG_VERSION} ({git_hash})", f"v{PKG_VERSION}-{git_hash}"


def load_queries(path: Path) -> list[dict]:
    queries = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                queries.append(json.loads(line))
    return queries


def hits_to_sources(hits) -> list[str]:
    seen: list[str] = []
    for h in hits:
        s = str(h.source)
        if s not in seen:
            seen.append(s)
    return seen


def is_relevant(source: str, relevant_files: list[str]) -> bool:
    return any(rf in source for rf in relevant_files)


def recall_at_k(sources: list[str], relevant_files: list[str], k: int) -> float:
    return 1.0 if any(is_relevant(s, relevant_files) for s in sources[:k]) else 0.0


def mrr(sources: list[str], relevant_files: list[str]) -> float:
    for i, s in enumerate(sources, 1):
        if is_relevant(s, relevant_files):
            return 1.0 / i
    return 0.0


def first_hit_rank(sources: list[str], relevant_files: list[str]) -> int:
    for i, s in enumerate(sources, 1):
        if is_relevant(s, relevant_files):
            return i
    return -1


def evaluate(queries: list[dict], searcher, rewriter) -> tuple[list[dict], dict]:
    """双方法:基线 search(query) vs deep search(rewrite(query))。返回 (每条, 汇总)。"""
    per_query: list[dict] = []
    for i, q in enumerate(queries, 1):
        rewritten = rewriter.rewrite(q["query"])
        srcs_base = hits_to_sources(searcher.search(q["query"], MAX_K))
        srcs_deep = hits_to_sources(searcher.search(rewritten, MAX_K))
        per_query.append(
            {
                "query": q["query"],
                "rewritten": rewritten,
                "relevant": q.get("relevant_files", []),
                "sources": {"基线(search)": srcs_base, "Agentic(deep)": srcs_deep},
            }
        )
        logger.info(
            "[%d/%d] %s → %s",
            i,
            len(queries),
            q["query"][:20],
            rewritten[:30],
        )

    total = {m: {**{f"recall@{k}": 0.0 for k in K_LIST}, "mrr": 0.0, "count": 0} for m in METHODS}
    for pq in per_query:
        for m in METHODS:
            srcs = pq["sources"][m]
            total[m]["count"] += 1
            for k in K_LIST:
                total[m][f"recall@{k}"] += recall_at_k(srcs, pq["relevant"], k)
            total[m]["mrr"] += mrr(srcs, pq["relevant"])
    for m in METHODS:
        n = total[m]["count"]
        if n:
            for k in K_LIST:
                total[m][f"recall@{k}"] /= n
            total[m]["mrr"] /= n
    return per_query, total


def render_terminal(total: dict, n: int) -> str:
    lines = [
        f"\nAgentic RAG eval(rewrite,{n} 条口语化 query)",
        "",
        "| 方法 | " + " | ".join(f"recall@{k}" for k in K_LIST) + " | MRR |",
        "|" + "---|" * (len(K_LIST) + 2),
    ]
    for m in METHODS:
        row = [m] + [f"{total[m][f'recall@{k}']:.1%}" for k in K_LIST] + [f"{total[m]['mrr']:.3f}"]
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def write_md_report(per_query, total, version_display, date_str, rewrite_model, path: Path) -> None:
    n = len(per_query)
    L: list[str] = [
        "# Agentic RAG(查询改写)eval 报告",
        "",
        f"> **测试日期**:{date_str}  ",
        f"> **版本**:{version_display}  ",
        f"> **rewrite 模型**:{rewrite_model} + think:false  ",
        f"> **数据集**:`eval/queries_rewrite.jsonl`({n} 条口语化/关键词不全 query)  ",
        "",
        "> **测什么**:对比 deep_search(rewrite+search)vs search_notes(基线),",
        "> 验证 rewrite 能否提升口语化 query 的召回。",
        "",
        "## 总体对比",
        "",
        "| 方法 | " + " | ".join(f"recall@{k}" for k in K_LIST) + " | MRR |",
        "|" + "---|" * (len(K_LIST) + 2),
    ]
    for m in METHODS:
        row = [m] + [f"{total[m][f'recall@{k}']:.1%}" for k in K_LIST] + [f"{total[m]['mrr']:.3f}"]
        L.append("| " + " | ".join(row) + " |")
    L += [
        "",
        "## 逐条明细(改写对比 + rank,每条标注日期+版本)",
        "",
        "| 编号 | 原 query | 改写后 | 基线 rank | deep rank | 测试日期 | 版本 |",
        "|---|---|---|---|---|---|---|",
    ]
    for i, pq in enumerate(per_query, 1):
        rb = first_hit_rank(pq["sources"]["基线(search)"], pq["relevant"])
        rd = first_hit_rank(pq["sources"]["Agentic(deep)"], pq["relevant"])
        fmt = lambda r: f"rank={r}" if r > 0 else "未命中"  # noqa: E731
        L.append(
            f"| T{i:03d} | {pq['query']} | {pq['rewritten']} | {fmt(rb)} | "
            f"{fmt(rd)} | {date_str} | {version_display} |"
        )
    L += [
        "",
        "## 说明",
        "",
        "- **基线(search)**:Searcher.search(query)(语义 + rerank)。",
        "- **Agentic(deep)**:QueryRewriter.rewrite(query) → Searcher.search(rewritten)。",
        "- 预期:口语化 query,deep 的 recall > 基线(rewrite 补正式术语后命中更好)。",
        "- 若 deep 反而差,说明 rewrite 过度(丢关键词),需调 prompt 或加回退。",
    ]
    path.write_text("\n".join(L) + "\n", encoding="utf-8")


def main() -> int:
    logging.basicConfig(level=logging.INFO, stream=sys.stderr, format="%(message)s")
    config = Config.from_env()
    config.validate()
    searcher, result = _build_searcher(config)
    rewriter = QueryRewriter(config.ollama_base_url, config.rewrite_model)
    logger.info(
        "库就绪:%d 文件 / %d chunks(rewrite 模型 %s)",
        result.total_files,
        result.total_chunks,
        config.rewrite_model,
    )
    version_display, version_file = get_version()
    date_str = time.strftime("%Y-%m-%d")
    queries = load_queries(EVAL_FILE)
    logger.info("加载 %d 条口语化 query\n", len(queries))
    per_query, total = evaluate(queries, searcher, rewriter)
    print(render_terminal(total, len(per_query)))
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / f"AgenticRAG-rewrite_{date_str}_{version_file}.md"
    write_md_report(per_query, total, version_display, date_str, config.rewrite_model, path)
    logger.info("报告: %s", path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
