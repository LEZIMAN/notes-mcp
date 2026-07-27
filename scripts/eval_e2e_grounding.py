"""e2e 接地测试:测 outofkb query(漏过意图层)主模型能否基于检索拒答(反幻觉)。

为什么单独一个 e2e:
- eval_intent 测意图层(职责:挡明显领域外),outofkb(AI术语库无)不归它管(放行)。
- outofkb 漏过意图层后,靠「检索召回空/无关 → 主模型拒答」兜底——本测试验证这个兜底。
- 测的是 RAG 接地性:检索为空时,主模型诚实说「笔记里没有」,而非编造。

链路:outofkb query → 检索(Searcher)→ 主模型(带检索 context)→ 回答
期望:检索召回空/无关 → 主模型拒答「笔记里没有相关内容」
指标:
  - 拒答率:应拒答(outofkb)→ 主模型拒答的比例(越高越好)
  - 幻觉率:主模型编造的比例(红线,越低越好)

用法:python scripts/eval_e2e_grounding.py
输出:终端 + docs/04-测试/e2e接地_<日期>_v<版本>-<githash>.md
"""

import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

from notes_mcp import __version__ as PKG_VERSION
from notes_mcp.cli import _build_searcher
from notes_mcp.config import Config

EVAL_FILE = Path(__file__).resolve().parent.parent / "eval" / "queries.jsonl"
REPORT_DIR = Path(__file__).resolve().parent.parent / "docs" / "04-测试"

# 主模型 prompt:明确「无相关则说没有,不编造」——接地性关键指令
PROMPT_TEMPLATE = (
    "你是笔记知识助手。下面是检索到的笔记片段(可能为空或与问题无关)。严格基于片段回答:\n"
    "- 片段有相关内容 → 基于它回答;\n"
    "- 片段为空或与问题无关 → 直接说「笔记里没有相关内容」,不要编造。\n\n"
    "笔记片段:\n{context}\n\n用户问题:{query}"
)

# 拒答词初筛(未命中 = 幻觉疑例,需人工 review)
REFUSE_WORDS = ["笔记里没有", "没有相关", "未包含", "无相关内容", "笔记中没", "找不到", "不在笔记", "未涉及", "没有关于"]

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


def ollama_chat_url() -> str:
    base = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434/v1").rstrip("/")
    if base.endswith("/v1"):
        base = base[:-3]
    return base + "/api/chat"


def load_outofkb(path: Path) -> list[dict]:
    """读 outofkb query(type=negative, subtype=outofkb)。"""
    qs = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            q = json.loads(line)
            if q.get("type") == "negative" and q.get("subtype") == "outofkb":
                qs.append(q)
    return qs


def main_model(query: str, context: str, model: str) -> tuple[str, float]:
    """主模型生成:走 ollama 原生 /api/chat(接地判断不需 thinking,关掉提速)。"""
    url = ollama_chat_url()
    prompt = PROMPT_TEMPLATE.format(context=context, query=query)
    start = time.perf_counter()
    resp = httpx.post(
        url,
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "think": False,  # 接地判断(拒答 vs 编造)不需深度推理,关 thinking 提速
            "stream": False,
        },
        timeout=120.0,
    )
    resp.raise_for_status()
    elapsed = time.perf_counter() - start
    content = (resp.json().get("message") or {}).get("content", "") or ""
    return content.strip(), elapsed


def evaluate(queries: list[dict], searcher, model: str) -> list[dict]:
    rows: list[dict] = []
    n = len(queries)
    for i, q in enumerate(queries, 1):
        query = q["query"]
        # 1. 检索(看召回是否空/无关)
        hits = searcher.search(query, 5)
        if hits:
            context = "\n".join(f"- [{h.title}] {h.text[:120]}" for h in hits)
            top_score = hits[0].score
        else:
            context = "(无相关笔记)"
            top_score = None
        # 2. 主模型生成
        answer, elapsed = main_model(query, context, model)
        # 3. 判断拒答(词初筛)
        is_refuse = any(w in answer for w in REFUSE_WORDS)
        rows.append(
            {
                "query": query,
                "n_hits": len(hits),
                "top_score": top_score,
                "context_preview": context[:200],
                "answer": answer,
                "is_refuse": is_refuse,
                "elapsed": elapsed,
            }
        )
        logger.info(
            "[%d/%d] %-30s hits=%d score=%s → %s (%.1fs)",
            i,
            n,
            query[:30],
            len(hits),
            f"{top_score:.2f}" if top_score is not None else "-",
            "✅拒答" if is_refuse else "❌幻觉?",
            elapsed,
        )
    return rows


def metrics(rows: list[dict]) -> dict:
    n = len(rows)
    n_refuse = sum(r["is_refuse"] for r in rows)
    hallucinate = [r for r in rows if not r["is_refuse"]]
    return {
        "n": n,
        "n_refuse": n_refuse,
        "refuse_rate": n_refuse / n if n else 0.0,
        "n_hallucinate": len(hallucinate),
        "hallucinate_rate": len(hallucinate) / n if n else 0.0,
        "hallucinate": hallucinate,
        "avg_time": sum(r["elapsed"] for r in rows) / n if n else 0.0,
    }


def write_md_report(m, rows, model, version_display, date_str, path: Path) -> None:
    L: list[str] = []
    L.append("# e2e 接地测试报告")
    L.append("")
    L.append(f"> **测试日期**:{date_str}  ")
    L.append(f"> **版本**:{version_display}  ")
    L.append(f"> **模型**:{model} + think:false(主模型生成)  ")
    L.append(f"> **测试集**:eval/queries.jsonl 的 outofkb({m['n']} 条「AI术语库无」)  ")
    L.append("")
    L.append(
        "> **测什么**:outofkb query 漏过意图层后,主模型基于检索(空/无关)能否拒答。"
        "检索为空时主模型应说「笔记里没有」,而非编造——这是 RAG 接地性。"
    )
    L.append("")
    L.append("## 核心指标")
    L.append("")
    L.append("| 指标 | 值 | 说明 |")
    L.append("|---|---|---|")
    L.append(f"| 拒答率 | **{m['refuse_rate']:.1%}** | {m['n_refuse']}/{m['n']} — 越高越好 |")
    L.append(f"| 幻觉率 | **{m['hallucinate_rate']:.1%}** | {m['n_hallucinate']}/{m['n']} — 红线,越低越好 |")
    L.append(f"| 平均耗时 | {m['avg_time']:.1f}s/query | |")
    L.append("")
    L.append("## 逐条明细(每条标注测试日期 + 版本)")
    L.append("")
    L.append("| 编号 | 测试项 | 检索 hits | top score | 结果 | 测试日期 | 版本 |")
    L.append("|---|---|---|---|---|---|---|")
    for i, r in enumerate(rows, 1):
        verdict = "✅拒答" if r["is_refuse"] else "❌幻觉?"
        score = f"{r['top_score']:.2f}" if r["top_score"] is not None else "-"
        L.append(
            f"| T{i:03d} | {r['query']} | {r['n_hits']} | {score} | {verdict} | "
            f"{date_str} | {version_display} |"
        )
    L.append("")
    L.append("## 幻觉疑例(未拒答,需人工 review)")
    L.append("")
    if m["hallucinate"]:
        for r in m["hallucinate"]:
            L.append(f"### `{r['query']}`")
            L.append(f"- 检索:{r['n_hits']} hits,top score={r['top_score']}")
            L.append(f"- 主模型回答:")
            L.append("```")
            L.append(r["answer"][:500])
            L.append("```")
            L.append("")
    else:
        L.append("✅ 无幻觉疑例(全部正确拒答)")
    L.append("")
    L.append("## 说明")
    L.append("")
    L.append("- **拒答率**是核心:outofkb(库无)主模型应拒答,不编造。")
    L.append("- **幻觉疑例**用拒答词初筛,未命中需人工 review(可能误判)。")
    L.append("- think:false(快,初步);若幻觉率高,开 think 重测对比。")
    path.write_text("\n".join(L) + "\n", encoding="utf-8")


def main() -> int:
    logging.basicConfig(level=logging.INFO, stream=sys.stderr, format="%(message)s")
    load_dotenv()
    config = Config.from_env()
    config.validate()
    searcher, result = _build_searcher(config)
    logger.info("库就绪:%d 文件 / %d chunks", result.total_files, result.total_chunks)
    model = os.getenv("OLLAMA_MODEL", "qwen3:8b")
    version_display, version_file = get_version()
    date_str = time.strftime("%Y-%m-%d")
    queries = load_outofkb(EVAL_FILE)
    logger.info("加载 %d 条 outofkb query(主模型 %s,%s)\n", len(queries), model, ollama_chat_url())
    rows = evaluate(queries, searcher, model)
    m = metrics(rows)
    print(f"\ne2e 接地测试(outofkb {m['n']} 条)")
    print(f"  拒答率: {m['n_refuse']}/{m['n']} = {m['refuse_rate']:.1%}")
    print(f"  幻觉率: {m['n_hallucinate']}/{m['n']} = {m['hallucinate_rate']:.1%}  ← 红线")
    print(f"  平均耗时: {m['avg_time']:.1f}s/query")
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / f"e2e接地_{date_str}_{version_file}.md"
    write_md_report(m, rows, model, version_display, date_str, path)
    logger.info("测试报告: %s", path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
