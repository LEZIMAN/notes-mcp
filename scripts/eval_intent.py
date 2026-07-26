"""意图过滤 eval:量化 qwen3:8b + think:false 的 normal/irrelevant 分类效果。

为什么单独一个 eval:
- 检索 eval(检索eval报告.md)只测"相关 query 能否召回",测不了"无关 query 该不该回答"。
- 意图过滤层(IntentFilter)挡无关省云端 token,但它准不准?误拦截(把真问题拒答)
  比漏拦截(浪费 token)致命得多——本 eval 就是量化这个 trade-off。

职责边界(关键):意图层只判「领域相关性」,不判「库内是否有」。所以 negative 分两类:
  - oftopic(明显领域外:红烧肉/天气)→ 期望拦截(意图层职责)
  - outofkb(AI术语但库无:PPO/GNN)→ 期望放行(交全流程兜底:检索空→主模型拒答)
  把 outofkb 算意图层漏拦截是边界划错——它该由端到端接地测试验证(见 e2e-grounding-test memory)。

数据集:eval/queries.jsonl(复用检索 eval 同一份):
  - positive(知识库问题)→ 期望放行
  - ambiguous(术语堆砌)→ 期望放行(归 normal,主模型兜底)
  - negative.offtopic(明显领域外)→ 期望拦截
  - negative.outofkb(AI术语库无)→ 期望放行(交全流程)

复刻 web/backend IntentFilter.java 的 prompt + 调用:
- 走 ollama 原生 /api/chat(不是 /v1 OpenAI 兼容端点),精确传 think:false
  (踩坑 #25:/v1 协议无 think 字段;原生 API 才能关 thinking,0.6s vs 14.5s)
- prompt 逐字复制 IntentFilter.java(单一信息源:改 prompt 必须同步两处)

核心指标:
  - 准确率(总体)
  - 误拦截率 FPR:positive/ambiguous/outofkb 错判 irrelevant(致命:拒答真问题)
  - 漏拦截率 FNR:offtopic 错判 normal(浪费 token)

用法:python scripts/eval_intent.py
输出:终端 + docs/04-测试/意图过滤eval_<日期>_v<版本>-<githash>.md
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

EVAL_FILE = Path(__file__).resolve().parent.parent / "eval" / "queries.jsonl"
REPORT_DIR = Path(__file__).resolve().parent.parent / "docs" / "04-测试"

# 复刻 web/backend IntentFilter.java 的 PROMPT(逐字一致,单一信息源)。
# 改这里必须同步改 IntentFilter.java,否则评估的不是生产行为。
PROMPT = (
    "知识库是AI/编程/机器学习/LLM/Agent 的学习笔记。判断用户查询意图,只输出一个英文词:"
    "normal(只要涉及 AI/编程/机器学习/大模型/算法/计算机 的概念、术语、名词、问题——"
    "哪怕简短或几个词并列——都算正常对话) "
    "irrelevant(明确只问日常生活领域:菜谱做法/天气/体育赛事/股市行情/娱乐八卦/医疗咨询等)。"
    "查询:"
)

logger = logging.getLogger(__name__)


def expected_block(qtype: str, subtype: str = "") -> bool:
    """type+subtype → 是否期望拦截(按意图层职责边界)。

    positive/ambiguous → 放行;
    negative.offtopic(明显领域外)→ 拦截(意图层职责);
    negative.outofkb(AI术语库无)→ 放行(交全流程,意图层不管"库有没有")。
    """
    if qtype == "negative":
        return subtype == "offtopic"
    return False


def type_label(qtype: str, subtype: str = "") -> str:
    """报告用的类型标签(含期望,一目了然)。"""
    if qtype == "negative":
        return "无关-领域外(应拦)" if subtype == "offtopic" else "无关-AI术语库无(交全流程)"
    return {"positive": "正例(应放行)", "ambiguous": "歧义(应放行)"}.get(qtype, qtype)


def load_queries(path: Path) -> list[dict]:
    queries = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                queries.append(json.loads(line))
    return queries


def ollama_chat_url() -> str:
    """OLLAMA_BASE_URL 是 OpenAI 兼容(/v1 结尾)。
    意图 eval 走 ollama 原生 /api/chat,精确传 think:false
    (与 Spring AI OllamaChatModel 同路径)。
    """
    base = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434/v1").rstrip("/")
    if base.endswith("/v1"):  # 去掉 /v1 得到 ollama 根地址
        base = base[:-3]
    return base + "/api/chat"


def classify(query: str, model: str) -> tuple[bool, str, float]:
    """复刻 IntentFilter.isIrrelevant:走 ollama 原生 API,think=false。
    返回 (is_irrelevant, raw_output, elapsed_s)。
    """
    url = ollama_chat_url()
    start = time.perf_counter()
    resp = httpx.post(
        url,
        json={
            "model": model,
            "messages": [{"role": "user", "content": PROMPT + query}],
            "think": False,  # 踩坑 #25:必须 API 层关 thinking
            "stream": False,
        },
        timeout=60.0,
    )
    resp.raise_for_status()
    data = resp.json()
    content = (data.get("message") or {}).get("content", "") or ""
    elapsed = time.perf_counter() - start
    # 复刻 IntentFilter:输出含 "irrelevant" 即判拦截
    is_irr = "irrelevant" in content.strip().lower()
    return is_irr, content.strip(), elapsed


def evaluate(queries: list[dict], model: str) -> list[dict]:
    """逐条分类,返回明细行。"""
    rows: list[dict] = []
    n = len(queries)
    for i, q in enumerate(queries, 1):
        qtype = q.get("type", "positive")
        subtype = q.get("subtype", "")
        expect_block = expected_block(qtype, subtype)
        actual_block, raw, elapsed = classify(q["query"], model)
        correct = actual_block == expect_block
        if not correct:
            err = "误拦截(拒答真问题)" if (actual_block and not expect_block) else "漏拦截(浪费token)"
        else:
            err = ""
        rows.append(
            {
                "query": q["query"],
                "type": qtype,
                "subtype": subtype,
                "label": type_label(qtype, subtype),
                "expect_block": expect_block,
                "actual_block": actual_block,
                "raw": raw,
                "elapsed": elapsed,
                "correct": correct,
                "err": err,
            }
        )
        logger.info(
            "[%d/%d] %-32s → %-4s (%.1fs) %s",
            i,
            n,
            q["query"][:32],
            "拦截" if actual_block else "放行",
            elapsed,
            "✅" if correct else "❌ " + err,
        )
    return rows


def metrics(rows: list[dict]) -> dict:
    """汇总指标。误拦截=期望放行却拦截;漏拦截=期望拦截却放行。"""
    n = len(rows)
    n_correct = sum(r["correct"] for r in rows)
    should_pass = [r for r in rows if not r["expect_block"]]  # positive + ambiguous + outofkb
    should_block = [r for r in rows if r["expect_block"]]  # negative.offtopic
    fp = [r for r in should_pass if r["actual_block"]]  # 误拦截(致命)
    fn = [r for r in should_block if not r["actual_block"]]  # 漏拦截(浪费)

    by_type: dict[str, dict] = {}
    for r in rows:
        lab = r["label"]
        by_type.setdefault(lab, {"n": 0, "correct": 0})
        by_type[lab]["n"] += 1
        by_type[lab]["correct"] += 1 if r["correct"] else 0

    return {
        "n": n,
        "n_correct": n_correct,
        "accuracy": n_correct / n if n else 0.0,
        "n_should_pass": len(should_pass),
        "n_fp": len(fp),
        "fpr": len(fp) / len(should_pass) if should_pass else 0.0,
        "fp": fp,
        "n_should_block": len(should_block),
        "n_fn": len(fn),
        "fnr": len(fn) / len(should_block) if should_block else 0.0,
        "fn": fn,
        "avg_time": sum(r["elapsed"] for r in rows) / n if n else 0.0,
        "by_type": by_type,
    }


def render_terminal(m: dict) -> str:
    lines = [
        "\n意图过滤 Eval(qwen3:8b + think:false,复刻 IntentFilter;按职责边界)",
        "",
        f"  总体准确率: {m['n_correct']}/{m['n']} = {m['accuracy']:.1%}",
        f"  误拦截率 FPR: {m['n_fp']}/{m['n_should_pass']} = {m['fpr']:.1%}"
        f"  ← 致命(把真问题拒答),越低越好",
        f"  漏拦截率 FNR: {m['n_fn']}/{m['n_should_block']} = {m['fnr']:.1%}"
        f"  ← 浪费 token(仅 oftopic 计)",
        f"  平均耗时: {m['avg_time']:.1f}s/query",
    ]
    return "\n".join(lines)


def get_version() -> tuple[str, str]:
    """语义版本(__version__)+ git short hash,双重追溯。
    返回 (展示串, 文件名串)。
    """
    try:
        git_hash = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=Path(__file__).resolve().parent.parent,
            stderr=subprocess.DEVNULL,
        ).decode().strip()
    except Exception:
        git_hash = "nogit"
    return f"v{PKG_VERSION} ({git_hash})", f"v{PKG_VERSION}-{git_hash}"


def write_md_report(m, rows, model, version_display, date_str, path: Path) -> None:
    """生成 md 测试报告:元信息 + 核心指标 + 分类型 + 逐条明细(每条带日期/版本) + 错例。
    md 纯文本,git 可 diff 追溯历次 eval。
    """
    bt = m["by_type"]
    L: list[str] = []
    L.append("# 意图过滤测试报告")
    L.append("")
    L.append(f"> **测试日期**:{date_str}  ")
    L.append(f"> **版本**:{version_display}  ")
    L.append(f"> **模型**:{model} + think:false(ollama 原生 /api/chat)  ")
    # 数据集按 subtype 细分
    n_off = bt.get("无关-领域外(应拦)", {"n": 0})["n"]
    n_ookb = bt.get("无关-AI术语库无(交全流程)", {"n": 0})["n"]
    L.append(
        f"> **数据集**:`eval/queries.jsonl` — 正例 {bt.get('正例(应放行)', {'n':0})['n']} / "
        f"歧义 {bt.get('歧义(应放行)', {'n':0})['n']} / "
        f"无关-领域外 {n_off} / 无关-AI术语库无 {n_ookb}"
    )
    L.append("")
    L.append(
        "> **职责边界**:意图层只判领域相关性。「明显领域外」(offtopic)它拦;「AI术语但库无」"
        "(outofkb)它放行,交全流程兜底(检索空→主模型拒答,见 e2e-grounding-test)。"
    )
    L.append("")

    # —— 核心指标 ——
    L.append("## 核心指标")
    L.append("")
    L.append("| 指标 | 值 | 说明 |")
    L.append("|---|---|---|")
    L.append(f"| 总体准确率 | **{m['accuracy']:.1%}** | {m['n_correct']}/{m['n']} |")
    L.append(
        f"| 误拦截率 FPR | **{m['fpr']:.1%}** | {m['n_fp']}/{m['n_should_pass']}"
        " — 致命(拒答真问题) |"
    )
    L.append(
        f"| 漏拦截率 FNR | **{m['fnr']:.1%}** | {m['n_fn']}/{m['n_should_block']}"
        " — 仅 oftopic 计(outofkb 交全流程) |"
    )
    L.append(f"| 平均耗时 | {m['avg_time']:.1f}s/query | |")
    L.append("")

    # —— 分类型准确率 ——
    L.append("## 分类型准确率")
    L.append("")
    L.append("| 类型 | n | 正确 | 准确率 |")
    L.append("|---|---|---|---|")
    # 固定顺序
    order = ["正例(应放行)", "歧义(应放行)", "无关-领域外(应拦)", "无关-AI术语库无(交全流程)"]
    for lab in order:
        c = bt.get(lab)
        if not c:
            continue
        acc = c["correct"] / c["n"] if c["n"] else 0.0
        L.append(f"| {lab} | {c['n']} | {c['correct']} | {acc:.1%} |")
    L.append("")

    # —— 逐条测试明细(每条标注测试日期 + 版本)——
    L.append("## 逐条测试明细(每条标注测试日期 + 版本)")
    L.append("")
    L.append("| 编号 | 测试项 | 类型 | 期望 | 实际 | 结果 | 测试日期 | 版本 |")
    L.append("|---|---|---|---|---|---|---|---|")
    for i, r in enumerate(rows, 1):
        verdict = "✅" if r["correct"] else f"❌{r['err']}"
        L.append(
            f"| T{i:03d} | {r['query']} | {r['label']} | "
            f"{'拦截' if r['expect_block'] else '放行'} | "
            f"{'拦截' if r['actual_block'] else '放行'} | {verdict} | "
            f"{date_str} | {version_display} |"
        )
    L.append("")

    # —— 错例聚焦 ——
    L.append("## 错例聚焦")
    L.append("")
    L.append("### 误拦截(致命:拒答了真实知识问题)")
    L.append("")
    if m["fp"]:
        for r in m["fp"]:
            L.append(f"- `{r['query']}` → 模型输出:`{r['raw'][:50]}`")
    else:
        L.append("✅ 无误拦截(全部真问题正确放行)")
    L.append("")
    L.append("### 漏拦截(浪费 token:offtopic 被放行)")
    L.append("")
    if m["fn"]:
        for r in m["fn"]:
            L.append(f"- `{r['query']}` → 模型输出:`{r['raw'][:50]}`")
    else:
        L.append("✅ 无漏拦截(全部 oftopic 正确拦截)")
    L.append("")
    L.append(
        "> 注:outofkb(AI术语库无)放行**不算漏拦截**——它是设计预期,交全流程兜底。"
    )
    L.append("")

    # —— 说明 ——
    L.append("## 说明")
    L.append("")
    L.append("- **误拦截(FPR)是核心红线**:意图过滤为省钱,但拒答真问题牺牲体验,FPR 须接近 0。")
    L.append(
        "- **漏拦截(FNR)只计 oftopic**:outofkb(AI术语库无)意图层放行是设计——"
        "「库有没有」靠检索+主模型接地判断,交端到端测试验证(见 e2e-grounding-test)。"
    )
    L.append(
        "- **歧义(ambiguous)归放行**:术语堆砌交主模型兜底"
        "(见 [意图过滤模型选型](../02-设计/选型/意图过滤模型选型_2026-07-26_v0.1.md))。"
    )

    path.write_text("\n".join(L) + "\n", encoding="utf-8")


def main() -> int:
    logging.basicConfig(level=logging.INFO, stream=sys.stderr, format="%(message)s")
    load_dotenv()
    model = os.getenv("OLLAMA_MODEL", "qwen3:8b")  # 与 IntentFilter.java 默认一致
    version_display, version_file = get_version()
    date_str = time.strftime("%Y-%m-%d")

    queries = load_queries(EVAL_FILE)
    logger.info("加载 %d 条 query(模型 %s,%s)\n", len(queries), model, ollama_chat_url())
    rows = evaluate(queries, model)
    m = metrics(rows)
    print(render_terminal(m))

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / f"意图过滤eval_{date_str}_{version_file}.md"
    write_md_report(m, rows, model, version_display, date_str, path)
    logger.info("测试报告(md): %s", path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
