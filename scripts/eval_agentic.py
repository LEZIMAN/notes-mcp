"""Agentic RAG eval(Step 2):对比 deep_search(分解多步)vs search_notes(单步)。

数据集:eval/queries_decompose.jsonl(对比类 query,带 relevant_files)。
双方法:
  - 基线(search_notes):Searcher.search(query) 单步
  - Agentic(deep_search):decompose → 多步 search → RRF 融合
指标:
  - recall@k(any):top-k 含任一 relevant(常规,宽松)
  - recall_all@k(全命中):每个 relevant 都在 top-k(对比类真正指标——双方都召回)
验证:对比类 query,deep 的 recall_all > 基线(bge 单步可能只召一方,多步覆盖双方)。

用法:python scripts/eval_agentic.py
输出:终端 + docs/04-测试/AgenticRAG-decompose_<日期>_v<版本>-<githash>.md
"""

import os

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

import json
import logging
import subprocess
import sys
import time
from pathlib import Path

from notes_mcp import __version__ as PKG_VERSION
from notes_mcp.agentic.decomposer import QuestionDecomposer
from notes_mcp.cli import _build_searcher
from notes_mcp.config import Config
from notes_mcp.server import fuse_hits

EVAL_FILE = Path(__file__).resolve().parent.parent / "eval" / "queries_decompose.jsonl"
REPORT_DIR = Path(__file__).resolve().parent.parent / "docs" / "04-测试"
K_LIST = [1, 3, 5]
MAX_K = max(K_LIST)
METHODS = ["基线(单步 search)", "Agentic(多步 decompose)"]

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
    """any 命中率:top-k 含任一 relevant(宽松)。"""
    return 1.0 if any(is_relevant(s, relevant_files) for s in sources[:k]) else 0.0


def recall_all_at_k(sources: list[str], relevant_files: list[str], k: int) -> float:
    """全命中率:每个 relevant 文件都在 top-k 的某 source 里(对比类真正指标——双方都召回)。"""
    top = sources[:k]
    return 1.0 if all(any(rf in s for s in top) for rf in relevant_files) else 0.0


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


def evaluate(queries: list[dict], searcher, decomposer) -> tuple[list[dict], dict]:
    per_query: list[dict] = []
    n = len(queries)
    for i, q in enumerate(queries, 1):
        subs = decomposer.decompose(q["query"])
        srcs_base = hits_to_sources(searcher.search(q["query"], MAX_K))
        if len(subs) == 1:
            deep_hits = searcher.search(subs[0], MAX_K)
        else:
            grouped = [searcher.search(sub, MAX_K) for sub in subs]
            deep_hits = fuse_hits(grouped, MAX_K)
        srcs_deep = hits_to_sources(deep_hits)
        per_query.append(
            {
                "query": q["query"],
                "subs": subs,
                "relevant": q.get("relevant_files", []),
                "sources": {"基线(单步 search)": srcs_base, "Agentic(多步 decompose)": srcs_deep},
            }
        )
        logger.info("[%d/%d] %s → %d 子查询", i, n, q["query"][:24], len(subs))

    metrics_keys = [f"recall@{k}" for k in K_LIST] + [f"recall_all@{k}" for k in K_LIST] + ["mrr"]
    total = {m: {**{k: 0.0 for k in metrics_keys}, "count": 0} for m in METHODS}
    for pq in per_query:
        for m in METHODS:
            srcs = pq["sources"][m]
            total[m]["count"] += 1
            for k in K_LIST:
                total[m][f"recall@{k}"] += recall_at_k(srcs, pq["relevant"], k)
                total[m][f"recall_all@{k}"] += recall_all_at_k(srcs, pq["relevant"], k)
            total[m]["mrr"] += mrr(srcs, pq["relevant"])
    for m in METHODS:
        n = total[m]["count"]
        if n:
            for k in metrics_keys:
                total[m][k] /= n
    return per_query, total


def render_terminal(total: dict, n: int) -> str:
    lines = [
        f"\nAgentic RAG eval(Step 2 decompose,{n} 条对比类 query)",
        "",
        "| 方法 | recall@5(any) | recall_all@5(全命中) | MRR |",
        "|---|---|---|---|",
    ]
    for m in METHODS:
        lines.append(
            f"| {m} | {total[m]['recall@5']:.1%} | **{total[m]['recall_all@5']:.1%}** | {total[m]['mrr']:.3f} |"
        )
    lines.append("")
    lines.append("(recall_all@5 = 每个 relevant 都在 top-5;对比类真正指标——双方都召回)")
    return "\n".join(lines)


def write_md_report(per_query, total, version_display, date_str, model, path: Path) -> None:
    n = len(per_query)
    L: list[str] = [
        "# Agentic RAG(多步检索)eval 报告",
        "",
        f"> **测试日期**:{date_str}  ",
        f"> **版本**:{version_display}  ",
        f"> **decompose 模型**:{model} + think:false  ",
        f"> **数据集**:`eval/queries_decompose.jsonl`({n} 条对比类 query)  ",
        "",
        "> **测什么**:对比 deep_search(分解多步+RRF 融合)vs search_notes(单步)。",
        "> **关键指标 recall_all@5**(每个 relevant 都在 top-5):对比类的真正挑战是「双方都召回」,",
        "> recall(any)太宽松(漏一方也算过),recall_all 才看出多步覆盖双方的价值。",
        "",
        "## 总体对比",
        "",
        "| 方法 | recall@5(any) | recall_all@1 | recall_all@3 | **recall_all@5** | MRR |",
        "|---|---|---|---|---|---|",
    ]
    for m in METHODS:
        L.append(
            f"| {m} | {total[m]['recall@5']:.1%} | {total[m]['recall_all@1']:.1%} | "
            f"{total[m]['recall_all@3']:.1%} | **{total[m]['recall_all@5']:.1%}** | {total[m]['mrr']:.3f} |"
        )
    L += [
        "",
        "## 逐条明细(分解 + 双方命中,每条标注日期+版本)",
        "",
        "| 编号 | query | 子查询数 | 基线双方命中? | deep 双方命中? | 测试日期 | 版本 |",
        "|---|---|---|---|---|---|---|",
    ]
    for i, pq in enumerate(per_query, 1):
        base_all = "✅" if recall_all_at_k(pq["sources"]["基线(单步 search)"], pq["relevant"], MAX_K) else "❌"
        deep_all = "✅" if recall_all_at_k(pq["sources"]["Agentic(多步 decompose)"], pq["relevant"], MAX_K) else "❌"
        L.append(
            f"| T{i:03d} | {pq['query']} | {len(pq['subs'])} | {base_all} | "
            f"{deep_all} | {date_str} | {version_display} |"
        )
    L += ["", "## 子查询分解示例", ""]
    for pq in per_query[:5]:
        L.append(f"- `{pq['query']}` → {pq['subs']}")
    L += [
        "",
        "## 说明",
        "",
        "- **recall(any)**:top-k 含任一 relevant(宽松,漏一方也算过)。",
        "- **recall_all**(关键):每个 relevant 都在 top-k(对比类真正指标——双方都召回)。",
        "- 预期:对比类 deep 的 recall_all > 基线(多步覆盖 A/B,单步可能只召一方)。",
    ]
    path.write_text("\n".join(L) + "\n", encoding="utf-8")


def main() -> int:
    logging.basicConfig(level=logging.INFO, stream=sys.stderr, format="%(message)s")
    config = Config.from_env()
    config.validate()
    searcher, result = _build_searcher(config)
    decomposer = QuestionDecomposer(config.ollama_base_url, config.rewrite_model)
    logger.info(
        "库就绪:%d 文件 / %d chunks(decompose 模型 %s)",
        result.total_files,
        result.total_chunks,
        config.rewrite_model,
    )
    version_display, version_file = get_version()
    date_str = time.strftime("%Y-%m-%d")
    queries = load_queries(EVAL_FILE)
    logger.info("加载 %d 条对比类 query\n", len(queries))
    per_query, total = evaluate(queries, searcher, decomposer)
    print(render_terminal(total, len(per_query)))
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / f"AgenticRAG-decompose_{date_str}_{version_file}.md"
    write_md_report(per_query, total, version_display, date_str, config.rewrite_model, path)
    logger.info("报告: %s", path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
