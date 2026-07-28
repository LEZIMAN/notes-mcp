"""QuestionDecomposer:对比类 query 分解成子查询(Step 2 核心)。

decomposer 做的是 bge 单轮做不了的事:对比类 query(对比 A 和 B)单轮检索只能找
一个语义中心,decomposer 拆成 [A, B, A-vs-B] 多步检索覆盖两者。

验证(qwen3:8b):对比类分解好,但单一问题(否定/深问)过度分解成近义重复 →
三重防护防过度分解:
  ① 检测对比词(对比/区别/关系/vs/和…哪个)才分解,其余原样返回
  ② prompt 强化「单一问题不分解,禁止同义拆分」
  ③ 子查询去重(完全重复过滤)

用法:
    d = QuestionDecomposer(base_url, "qwen3:8b")
    d.decompose("对比 Transformer 和 RNN")  # → ["Transformer 是什么", "RNN 是什么", "...区别"]
    d.decompose("什么是 RAG")               # → ["什么是 RAG"](无对比词,原样)
"""

import logging
import re

import httpx

from notes_mcp.agentic.prompts import PROMPT_DECOMPOSE

logger = logging.getLogger(__name__)

# 对比词检测:命中才分解(防护①:避免单一问题过度分解)
# 覆盖:对比/区别/差异/关系/vs/比较/和...哪个/和...优劣
_COMPARATIVE_PATTERNS = re.compile(
    r"对比|比较|区别|差异|vs|VS|关系|和.{0,12}(哪个|优劣|区别|差异|好)|与.{0,12}(哪个|区别|差异)"
)


class QuestionDecomposer:
    """查询分解器。依赖注入 base_url + model,便于测试传 fake。"""

    def __init__(self, ollama_base_url: str, model: str) -> None:
        self.model = model
        base = ollama_base_url.rstrip("/")
        if base.endswith("/v1"):
            base = base[:-3]
        self.url = base + "/api/chat"

    def decompose(self, query: str) -> list[str]:
        """分解 query 成子查询。非对比类原样返回 [query]。

        三重防护:① 无对比词→不分 ② prompt 强化 ③ 去重。
        """
        # 防护①:无对比词 → 原样(避免单一问题过度分解)
        if not _COMPARATIVE_PATTERNS.search(query):
            return [query]

        try:
            resp = httpx.post(
                self.url,
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": PROMPT_DECOMPOSE.format(query=query)}],
                    "think": False,
                    "stream": False,
                },
                timeout=30.0,
            )
            resp.raise_for_status()
            content = (resp.json().get("message") or {}).get("content", "").strip()
            subs = [s.strip().strip("\"'""''") for s in content.splitlines() if s.strip()]

            # 防护③:去重(完全重复过滤;近义靠 prompt②防)
            seen: set[str] = set()
            unique: list[str] = []
            for s in subs:
                if s and s not in seen:
                    seen.add(s)
                    unique.append(s)

            # 分解异常(空/仅 1 条=没拆开)→ 原样
            if len(unique) <= 1:
                return [query]
            logger.info("decompose: %s → %s", query, unique)
            return unique
        except Exception as e:
            logger.warning("decompose 失败,原样: %s", e)
            return [query]
