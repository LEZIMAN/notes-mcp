"""分析 cosine distance 分布,为 score 阈值找分界。

正例:首个命中 chunk 的 distance(应小,真相关)。
负例:top-1 distance(应大,硬凑——若与正例分离,阈值可行)。
歧义:top-1 distance(参考)。

用法:python scripts/analyze_distance.py
"""

import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval_retrieval import EVAL_FILE, load_queries  # noqa: E402

from notes_mcp.cli import _build_searcher  # noqa: E402
from notes_mcp.config import Config  # noqa: E402


def is_relevant(source: str, relevant_files: list[str]) -> bool:
    return any(rf in source for rf in relevant_files)


def first_hit_distance(hits, relevant_files: list[str]) -> float | None:
    """首个相关 chunk 的 distance(score=-distance)。"""
    for h in hits:
        if is_relevant(str(h.source), relevant_files):
            return -h.score
    return None


def percentile(sorted_list: list[float], p: float) -> float | None:
    if not sorted_list:
        return None
    return sorted_list[min(int(p * len(sorted_list)), len(sorted_list) - 1)]


def stats(name: str, ds: list[float]) -> None:
    if not ds:
        print(f"  {name}: (无)")
        return
    ds_sorted = sorted(ds)
    print(
        f"  {name} (n={len(ds)}): "
        f"min={ds_sorted[0]:.3f} p50={percentile(ds_sorted, 0.5):.3f} "
        f"p90={percentile(ds_sorted, 0.9):.3f} max={ds_sorted[-1]:.3f} "
        f"mean={statistics.mean(ds):.3f}"
    )


def main() -> int:
    config = Config.from_env()
    config.validate()
    searcher, _result = _build_searcher(config)
    queries = load_queries(EVAL_FILE)

    pos_dists, neg_dists, amb_dists = [], [], []
    for q in queries:
        hits = searcher.search(q["query"], 10)
        if not hits:
            continue
        top1 = -hits[0].score
        qtype = q.get("type", "positive")
        if qtype == "negative":
            neg_dists.append(top1)
        elif qtype == "ambiguous":
            amb_dists.append(top1)
        else:
            d = first_hit_distance(hits, q.get("relevant_files", []))
            if d is not None:
                pos_dists.append(d)

    print("\ncosine distance 分布(越小越相关):")
    stats("正例(命中 chunk)", pos_dists)
    stats("负例(top-1,硬凑)", neg_dists)
    stats("歧义(top-1)", amb_dists)

    # 建议阈值
    if pos_dists and neg_dists:
        pos_p90 = percentile(sorted(pos_dists), 0.9)
        neg_min = min(neg_dists)
        print("\n建议阈值分析:")
        print(f"  正例 p90 = {pos_p90:.3f} (90% 命中 chunk 的 distance 上限)")
        print(f"  负例 min = {neg_min:.3f} (最不硬凑的负例 top-1)")
        if pos_p90 < neg_min:
            thr = (pos_p90 + neg_min) / 2
            print(f"  → 两类分离! 建议 distance 阈值 = {thr:.3f}")
            print(f"    (distance > {thr:.3f} 的结果丢弃)")
        else:
            print("  → 两类重叠,固定阈值难分,需 rerank 或动态阈值。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
