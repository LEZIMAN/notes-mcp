"""检索 eval:量化语义检索质量(正例分难度 + 负例 + 歧义)。

数据集:eval/queries.jsonl,每行 {query, relevant_files, difficulty, type}。
  - positive:应命中 relevant(difficulty: easy/medium/hard)
  - negative:完全无关(relevant=[]),测 precision——不该硬凑
  - ambiguous:术语堆砌无意图(relevant=[]),测意图识别——应提示细化

指标:recall@1/3/5/10 + MRR(正例,按难度分组)。
命中判定:检索结果 source 路径包含任一 relevant 片段即算相关(文件级)。

用法:python scripts/eval_retrieval.py
输出:终端表 + docs/检索eval报告.md + docs/检索测试报告.md
"""

import json
import logging
import sys
from pathlib import Path

from notes_mcp.cli import _build_searcher
from notes_mcp.config import Config

EVAL_FILE = Path(__file__).resolve().parent.parent / "eval" / "queries.jsonl"
REPORT_FILE = Path(__file__).resolve().parent.parent / "docs" / "检索eval报告.md"
TEST_REPORT_FILE = Path(__file__).resolve().parent.parent / "docs" / "检索测试报告.md"
K_LIST = [1, 3, 5, 10]
MAX_K = max(K_LIST)
DIFFS = ["easy", "medium", "hard"]

logger = logging.getLogger(__name__)


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
    """首个相关 source 的排名(1-based),未命中返回 -1。"""
    for i, s in enumerate(sources, 1):
        if is_relevant(s, relevant_files):
            return i
    return -1


def evaluate(
    searcher, queries: list[dict]
) -> tuple[dict, dict, list[dict], list[dict], list[dict]]:
    """返回 (按难度分组, 总体, 每条详情, 负例, 歧义)。"""
    per_query: list[dict] = []
    for q in queries:
        hits = searcher.search(q["query"], MAX_K)
        sources = hits_to_sources(hits)
        per_query.append({
            "query": q["query"],
            "relevant": q.get("relevant_files", []),
            "difficulty": q.get("difficulty", "easy"),
            "type": q.get("type", "positive"),
            "sources": sources,
        })

    # 正例按难度分组
    summary = {d: {**{f"recall@{k}": 0.0 for k in K_LIST}, "mrr": 0.0, "count": 0} for d in DIFFS}
    pos_all = [pq for pq in per_query if pq["type"] == "positive"]
    for pq in pos_all:
        d = pq["difficulty"]
        if d not in summary:
            continue
        summary[d]["count"] += 1
        for k in K_LIST:
            summary[d][f"recall@{k}"] += recall_at_k(pq["sources"], pq["relevant"], k)
        summary[d]["mrr"] += mrr(pq["sources"], pq["relevant"])
    for d in DIFFS:
        n = summary[d]["count"]
        if n:
            for k in K_LIST:
                summary[d][f"recall@{k}"] /= n
            summary[d]["mrr"] /= n

    # 总体(全部正例)
    total = {**{f"recall@{k}": 0.0 for k in K_LIST}, "mrr": 0.0, "count": len(pos_all)}
    for pq in pos_all:
        for k in K_LIST:
            total[f"recall@{k}"] += recall_at_k(pq["sources"], pq["relevant"], k)
        total["mrr"] += mrr(pq["sources"], pq["relevant"])
    n = len(pos_all)
    if n:
        for k in K_LIST:
            total[f"recall@{k}"] /= n
        total["mrr"] /= n

    negatives = [pq for pq in per_query if pq["type"] == "negative"]
    ambiguities = [pq for pq in per_query if pq["type"] == "ambiguous"]
    return summary, total, per_query, negatives, ambiguities


def render_table(summary, total, n_pos, n_neg, n_amb) -> str:
    lines = [
        f"\n检索 Eval(纯语义 · 正例 {n_pos} + 负例 {n_neg} + 歧义 {n_amb})\n",
        "| 难度 | 样本 | " + " | ".join(f"recall@{k}" for k in K_LIST) + " | MRR |",
        "|" + "---|" * (len(K_LIST) + 3),
    ]
    for d in DIFFS:
        c = summary[d]["count"]
        if c == 0:
            continue
        row = [d, str(c)] + [f"{summary[d][f'recall@{k}']:.1%}" for k in K_LIST]
        row.append(f"{summary[d]['mrr']:.3f}")
        lines.append("| " + " | ".join(row) + " |")
    row = ["总计", str(n_pos)] + [f"{total[f'recall@{k}']:.1%}" for k in K_LIST]
    row.append(f"{total['mrr']:.3f}")
    lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def write_report(summary, total, n_pos, negatives, ambiguities) -> None:
    lines = [
        "# 检索 Eval 报告(纯语义)",
        "",
        f"> 正例 {n_pos} 条(分难度) + 负例 {len(negatives)} 条 + 歧义 {len(ambiguities)} 条。",
        "",
        "## 按难度分组(正例)",
        "",
        "| 难度 | 样本 | " + " | ".join(f"recall@{k}" for k in K_LIST) + " | MRR |",
        "|" + "---|" * (len(K_LIST) + 3),
    ]
    for d in DIFFS:
        c = summary[d]["count"]
        if c == 0:
            continue
        row = [d, str(c)] + [f"{summary[d][f'recall@{k}']:.1%}" for k in K_LIST]
        row.append(f"{summary[d]['mrr']:.3f}")
        lines.append("| " + " | ".join(row) + " |")
    row = ["总计", str(n_pos)] + [f"{total[f'recall@{k}']:.1%}" for k in K_LIST]
    row.append(f"{total['mrr']:.3f}")
    lines.append("| " + " | ".join(row) + " |")
    lines += ["", "## 负例(完全无关,测 precision——不该硬凑)", ""]
    for nq in negatives:
        top3 = [Path(s).name for s in nq["sources"][:3]]
        lines.append(f"- `{nq['query']}` → top3: {top3 if top3 else '(空)'}")
    lines += ["", "## 歧义(术语堆砌无意图,测意图识别——应提示细化)", ""]
    for aq in ambiguities:
        top3 = [Path(s).name for s in aq["sources"][:3]]
        lines.append(f"- `{aq['query']}` → top3: {top3 if top3 else '(空)'}")
    lines += [
        "",
        "## 改进方向",
        "",
        "- **hard 题** recall/MRR 最能体现检索质量,是 rerank 的主战场。",
        "- **负例**全硬凑 → 需 score 阈值过滤(不相关的不返回)。",
        "- **歧义**词相关无意图 → 产品应提示用户明确意图。",
        "- 加 rerank + score 阈值后在此报告对比。",
    ]
    REPORT_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_test_report(per_query: list[dict]) -> None:
    """正例 PASS/FAIL + 负例 + 歧义 人工 review + 难度分组。"""
    pos_rows, neg_rows, amb_rows = [], [], []
    passed = 0
    for i, pq in enumerate(per_query, 1):
        tid = f"T{i:03d}"
        if pq["type"] == "negative":
            top3 = ", ".join(Path(s).stem for s in pq["sources"][:3]) or "(空)"
            neg_rows.append(f"| {tid} | {pq['query']} | {top3} | ⚠️ 人工 review(硬凑?) |")
            continue
        if pq["type"] == "ambiguous":
            top3 = ", ".join(Path(s).stem for s in pq["sources"][:3]) or "(空)"
            amb_rows.append(f"| {tid} | {pq['query']} | {top3} | ⚠️ 人工 review(沾边?) |")
            continue
        rank = first_hit_rank(pq["sources"], pq["relevant"])
        if 1 <= rank <= 5:
            verdict, actual, passed = "✅ PASS", f"rank={rank}", passed + 1
        elif rank > 5:
            verdict, actual = "❌ FAIL", f"rank={rank}(>5)"
        else:
            verdict, actual = "❌ FAIL", "未命中"
        pos_rows.append(
            f"| {tid} | {pq['query']} | {pq['difficulty']} | top-5 命中 | {actual} | {verdict} |"
        )

    n_pos = len(pos_rows)
    lines = [
        "# 检索测试报告",
        "",
        f"> 正例 {n_pos} 条(通过 {passed}) + 负例 {len(neg_rows)} 条 + 歧义 {len(amb_rows)} 条。",
        "",
        "## 一、正例(应命中)",
        "",
        "| 编号 | 测试项(query) | 难度 | 预期 | 实际(rank) | 通过 |",
        "|---|---|---|---|---|---|",
    ]
    lines += pos_rows
    lines += [
        "",
        "## 二、负例(完全无关,测 precision——不该硬凑)",
        "",
        "| 编号 | 测试项(query) | 返回 top-3 | 状态 |",
        "|---|---|---|---|",
    ]
    lines += neg_rows if neg_rows else ["| — | (无) | — | — |"]
    lines += [
        "",
        "## 三、歧义(术语堆砌无意图,测意图识别——应提示细化)",
        "",
        "| 编号 | 测试项(query) | 返回 top-3 | 状态 |",
        "|---|---|---|---|",
    ]
    lines += amb_rows if amb_rows else ["| — | (无) | — | — |"]
    lines += [
        "", "## 四、按难度通过率(正例)", "",
        "| 难度 | 样本 | 通过 | 通过率 |", "|---|---|---|---|",
    ]
    for d in DIFFS:
        in_diff = [pq for pq in per_query if pq["type"] == "positive" and pq["difficulty"] == d]
        cnt = len(in_diff)
        if cnt == 0:
            continue
        ok = sum(1 for pq in in_diff if 1 <= first_hit_rank(pq["sources"], pq["relevant"]) <= 5)
        lines.append(f"| {d} | {cnt} | {ok} | {ok / cnt:.1%} |")
    lines += [
        "",
        "## 说明",
        "",
        "- **正例 PASS**:top-5 命中 relevant(rank≤5)。",
        "- **负例**:完全无关(relevant=[]),检查是否硬凑(precision 缺陷)。",
        "- **歧义**:术语堆砌无意图(relevant=[]),检查是否沾边合理,",
        "  产品应提示用户细化意图。",
        "- **难度**:easy/medium/hard(仅正例)。",
        "- **FAIL 排查**:先看是检索器召回差还是标注错(eval 反向校验标注)。",
    ]
    TEST_REPORT_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    logging.basicConfig(level=logging.INFO, stream=sys.stderr, format="%(message)s")
    config = Config.from_env()
    config.validate()
    searcher, result = _build_searcher(config)
    logger.info("库就绪:%d 文件 / %d chunks", result.total_files, result.total_chunks)
    queries = load_queries(EVAL_FILE)
    logger.info("加载 %d 条 query(正例+负例+歧义)\n", len(queries))
    summary, total, per_query, negatives, ambiguities = evaluate(searcher, queries)
    n_pos = len([pq for pq in per_query if pq["type"] == "positive"])
    print(render_table(summary, total, n_pos, len(negatives), len(ambiguities)))
    write_report(summary, total, n_pos, negatives, ambiguities)
    write_test_report(per_query)
    logger.info("\n汇总报告: %s", REPORT_FILE)
    logger.info("测试用例报告: %s", TEST_REPORT_FILE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
