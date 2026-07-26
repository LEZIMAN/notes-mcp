"""检索 eval:对比「纯语义 vs 语义+rerank」检索质量。

数据集:eval/queries.jsonl,每行 {query, relevant_files, difficulty, type}。
  - positive:应命中(easy/medium/hard)
  - negative:完全无关,测 precision
  - ambiguous:术语堆砌无意图,测意图识别

双方法对比:
  - 纯语义(bi-encoder,Chroma cosine)
  - 语义+rerank(粗召回 top-20 → cross-encoder 精排)
指标:recall@1/3/5/10 + MRR(正例,按难度分组)。

用法:python scripts/eval_retrieval.py
输出:终端 + docs/04-测试/检索eval_<日期>_<版本>.md + 检索测试_<日期>_<版本>.md
      (测试报告规范:快照类带日期+版本,git 可 diff 追溯)
"""

import json
import logging
import subprocess
import sys
import time
from pathlib import Path

from notes_mcp import __version__ as PKG_VERSION
from notes_mcp.cli import _build_searcher
from notes_mcp.config import Config
from notes_mcp.search import Searcher

EVAL_FILE = Path(__file__).resolve().parent.parent / "eval" / "queries.jsonl"
REPORT_DIR = Path(__file__).resolve().parent.parent / "docs" / "04-测试"
K_LIST = [1, 3, 5, 10]
MAX_K = max(K_LIST)
DIFFS = ["easy", "medium", "hard"]
METHODS = ["纯语义", "语义+rerank"]

logger = logging.getLogger(__name__)


def get_version() -> tuple[str, str]:
    """语义版本(__version__)+ git short hash,双重追溯。返回 (展示串, 文件名串)。"""
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


def evaluate(
    searchers: dict, queries: list[dict]
) -> tuple[dict, dict, list[dict], list[dict], list[dict]]:
    """返回 (按难度×方法, 总体×方法, 每条, 负例, 歧义)。"""
    per_query: list[dict] = []
    for q in queries:
        sources = {}
        for m, s in searchers.items():
            sources[m] = hits_to_sources(s.search(q["query"], MAX_K))
        per_query.append(
            {
                "query": q["query"],
                "relevant": q.get("relevant_files", []),
                "difficulty": q.get("difficulty", "easy"),
                "type": q.get("type", "positive"),
                "sources": sources,
            }
        )

    summary = {
        m: {d: {**{f"recall@{k}": 0.0 for k in K_LIST}, "mrr": 0.0, "count": 0} for d in DIFFS}
        for m in METHODS
    }
    total = {m: {**{f"recall@{k}": 0.0 for k in K_LIST}, "mrr": 0.0, "count": 0} for m in METHODS}
    for pq in per_query:
        if pq["type"] != "positive":
            continue
        for m in METHODS:
            srcs = pq["sources"][m]
            d = pq["difficulty"]
            if d in DIFFS:
                summary[m][d]["count"] += 1
                for k in K_LIST:
                    summary[m][d][f"recall@{k}"] += recall_at_k(srcs, pq["relevant"], k)
                summary[m][d]["mrr"] += mrr(srcs, pq["relevant"])
            total[m]["count"] += 1
            for k in K_LIST:
                total[m][f"recall@{k}"] += recall_at_k(srcs, pq["relevant"], k)
            total[m]["mrr"] += mrr(srcs, pq["relevant"])
    for m in METHODS:
        for d in DIFFS:
            n = summary[m][d]["count"]
            if n:
                for k in K_LIST:
                    summary[m][d][f"recall@{k}"] /= n
                summary[m][d]["mrr"] /= n
        n = total[m]["count"]
        if n:
            for k in K_LIST:
                total[m][f"recall@{k}"] /= n
            total[m]["mrr"] /= n

    negatives = [pq for pq in per_query if pq["type"] == "negative"]
    ambiguities = [pq for pq in per_query if pq["type"] == "ambiguous"]
    return summary, total, per_query, negatives, ambiguities


def render_table(total: dict, n_pos: int, n_neg: int, n_amb: int) -> str:
    lines = [
        f"\n检索 Eval(正例 {n_pos} + 负例 {n_neg} + 歧义 {n_amb})\n",
        "| 方法 | " + " | ".join(f"recall@{k}" for k in K_LIST) + " | MRR |",
        "|" + "---|" * (len(K_LIST) + 2),
    ]
    for m in METHODS:
        row = [m] + [f"{total[m][f'recall@{k}']:.1%}" for k in K_LIST]
        row.append(f"{total[m]['mrr']:.3f}")
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def render_by_diff(summary: dict) -> str:
    lines = [
        "",
        "按难度 recall@1 / MRR:",
        "",
        "| 难度 | n | 纯语义 r@1 | +rerank r@1 | 纯语义 MRR | +rerank MRR |",
        "|---|---|---|---|---|---|",
    ]
    for d in DIFFS:
        c = summary["纯语义"][d]["count"]
        if c == 0:
            continue
        sem, rr = summary["纯语义"][d], summary["语义+rerank"][d]
        lines.append(
            f"| {d} | {c} | {sem['recall@1']:.1%} | {rr['recall@1']:.1%} | "
            f"{sem['mrr']:.3f} | {rr['mrr']:.3f} |"
        )
    return "\n".join(lines)


def write_report(summary, total, n_pos, negatives, ambiguities, version_display, date_str, path: Path) -> None:
    lines = [
        "# 检索 Eval 报告(纯语义 vs 语义+rerank)",
        "",
        f"> **测试日期**:{date_str}  ",
        f"> **版本**:{version_display}  ",
        f"> 正例 {n_pos} + 负例 {len(negatives)} + 歧义 {len(ambiguities)}。",
        "",
        "## 总体对比",
        "",
        "| 方法 | " + " | ".join(f"recall@{k}" for k in K_LIST) + " | MRR |",
        "|" + "---|" * (len(K_LIST) + 2),
    ]
    for m in METHODS:
        row = [m] + [f"{total[m][f'recall@{k}']:.1%}" for k in K_LIST]
        row.append(f"{total[m]['mrr']:.3f}")
        lines.append("| " + " | ".join(row) + " |")
    lines += [
        "",
        "## 按难度 recall@1 / MRR",
        "",
        "| 难度 | n | 纯语义 r@1 | +rerank r@1 | 纯语义 MRR | +rerank MRR |",
        "|---|---|---|---|---|---|",
    ]
    for d in DIFFS:
        c = summary["纯语义"][d]["count"]
        if c == 0:
            continue
        sem, rr = summary["纯语义"][d], summary["语义+rerank"][d]
        lines.append(
            f"| {d} | {c} | {sem['recall@1']:.1%} | {rr['recall@1']:.1%} | "
            f"{sem['mrr']:.3f} | {rr['mrr']:.3f} |"
        )
    lines += ["", "## 负例(rerank 后 top-3,检查硬凑)", ""]
    for nq in negatives:
        top3 = [Path(s).name for s in nq["sources"]["语义+rerank"][:3]]
        lines.append(f"- `{nq['query']}` → {top3 if top3 else '(空)'}")
    lines += ["", "## 歧义(rerank 后 top-3)", ""]
    for aq in ambiguities:
        top3 = [Path(s).name for s in aq["sources"]["语义+rerank"][:3]]
        lines.append(f"- `{aq['query']}` → {top3 if top3 else '(空)'}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_test_report(per_query: list[dict], version_display, date_str, path: Path) -> None:
    """正例双方法 rank 对比 + 负例/歧义(rerank top-3)。"""
    pos_rows, neg_rows, amb_rows = [], [], []
    passed = 0
    for i, pq in enumerate(per_query, 1):
        tid = f"T{i:03d}"
        if pq["type"] == "negative":
            top3 = ", ".join(Path(s).stem for s in pq["sources"]["语义+rerank"][:3]) or "(空)"
            neg_rows.append(f"| {tid} | {pq['query']} | {top3} | ⚠️ 人工 review |")
            continue
        if pq["type"] == "ambiguous":
            top3 = ", ".join(Path(s).stem for s in pq["sources"]["语义+rerank"][:3]) or "(空)"
            amb_rows.append(f"| {tid} | {pq['query']} | {top3} | ⚠️ 人工 review |")
            continue
        rel = pq["relevant"]
        rank_sem = first_hit_rank(pq["sources"]["纯语义"], rel)
        rank_rr = first_hit_rank(pq["sources"]["语义+rerank"], rel)
        ok = 1 <= rank_rr <= 5
        if ok:
            passed += 1
        verdict = "✅ PASS" if ok else "❌ FAIL"
        fmt = lambda r: f"rank={r}" if r > 0 else "未命中"  # noqa: E731
        pos_rows.append(
            f"| {tid} | {pq['query']} | {pq['difficulty']} | {fmt(rank_sem)} | "
            f"{fmt(rank_rr)} | {verdict} |"
        )

    n_pos = len(pos_rows)
    lines = [
        "# 检索测试报告(纯语义 vs 语义+rerank)",
        "",
        f"> **测试日期**:{date_str}  ",
        f"> **版本**:{version_display}  ",
        f"> 正例 {n_pos} 条(rerank 通过 {passed}) + 负例 {len(neg_rows)} + 歧义 {len(amb_rows)}。",
        "",
        "## 一、正例(rank 对比:看 rerank 是否提升头部排名)",
        "",
        "| 编号 | 测试项 | 难度 | 纯语义 rank | +rerank rank | 通过(rerank) |",
        "|---|---|---|---|---|---|",
    ]
    lines += pos_rows
    lines += [
        "",
        "## 二、负例(rerank 后 top-3,检查硬凑)",
        "",
        "| 编号 | 测试项 | 返回 top-3 | 状态 |",
        "|---|---|---|---|",
    ]
    lines += neg_rows if neg_rows else ["| — | (无) | — | — |"]
    lines += [
        "",
        "## 三、歧义(rerank 后 top-3)",
        "",
        "| 编号 | 测试项 | 返回 top-3 | 状态 |",
        "|---|---|---|---|",
    ]
    lines += amb_rows if amb_rows else ["| — | (无) | — | — |"]
    lines += [
        "",
        "## 说明",
        "",
        "- **纯语义 rank vs +rerank rank**:若 rerank 把 rank>1 提到 1,说明精排生效。",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    logging.basicConfig(level=logging.INFO, stream=sys.stderr, format="%(message)s")
    config = Config.from_env()
    config.validate()
    searcher_rr, result = _build_searcher(config)
    searcher_sem = Searcher(  # noqa: SLF001 — 复用 embedder 做纯语义对比
        searcher_rr.collection,
        searcher_rr._embedder,
        reranker=None,
    )
    logger.info("库就绪:%d 文件 / %d chunks", result.total_files, result.total_chunks)
    queries = load_queries(EVAL_FILE)
    logger.info("加载 %d 条 query\n", len(queries))
    searchers = {"纯语义": searcher_sem, "语义+rerank": searcher_rr}
    summary, total, per_query, negatives, ambiguities = evaluate(searchers, queries)
    n_pos = len([pq for pq in per_query if pq["type"] == "positive"])
    print(render_table(total, n_pos, len(negatives), len(ambiguities)))
    print(render_by_diff(summary))

    version_display, version_file = get_version()
    date_str = time.strftime("%Y-%m-%d")
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORT_DIR / f"检索eval_{date_str}_{version_file}.md"
    test_path = REPORT_DIR / f"检索测试_{date_str}_{version_file}.md"
    write_report(summary, total, n_pos, negatives, ambiguities, version_display, date_str, report_path)
    write_test_report(per_query, version_display, date_str, test_path)
    logger.info("\n汇总报告: %s", report_path)
    logger.info("测试用例报告: %s", test_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
