"""QueryRewriter:用 qwen3:8b 改写 query(口语化→正式/补关键词),Step 1 核心。

复用 eval_intent.py 的 ollama 原生 /api/chat + think:false 范式:
- 走原生 /api/chat(不是 OpenAI /v1),精确传 think:false(踩坑 #25:关 thinking,0.6s vs 14.5s)
- 跨 Provider 一致(不依赖主模型),本地免费

失败安全:改写失败/异常时,回退原 query(不阻塞检索,降级为普通 search)。

用法:
    rewriter = QueryRewriter("http://127.0.0.1:11434/v1", "qwen3:8b")
    rewritten = rewriter.rewrite("咋搞 RAG")  # → "如何实现 RAG 检索增强生成"
"""

import logging

import httpx

from notes_mcp.agentic.prompts import PROMPT_REWRITE

logger = logging.getLogger(__name__)


class QueryRewriter:
    """查询改写器。依赖注入 base_url + model,便于测试传 fake。

    base_url 是 OpenAI 兼容端点(/v1 结尾),内部推导为 ollama 原生 /api/chat。
    """

    def __init__(self, ollama_base_url: str, model: str) -> None:
        self.model = model
        # OpenAI /v1 → ollama 原生 /api/chat(同 eval_intent.ollama_chat_url 推导)
        base = ollama_base_url.rstrip("/")
        if base.endswith("/v1"):
            base = base[:-3]
        self.url = base + "/api/chat"

    def rewrite(self, query: str) -> str:
        """改写 query。失败/异常/输出异常时回退原 query(不阻塞检索)。

        返回改写后 query;若改写可能伤检索(空/过长/原样),适当回退。
        """
        try:
            resp = httpx.post(
                self.url,
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": PROMPT_REWRITE.format(query=query)}],
                    "think": False,  # 踩坑 #25:关 thinking 加速
                    "stream": False,
                },
                timeout=30.0,
            )
            resp.raise_for_status()
            rewritten = (resp.json().get("message") or {}).get("content", "").strip()
            # 模型可能加解释/引号:取第一行 + 去引号
            rewritten = rewritten.splitlines()[0].strip().strip("\"'""''")
            # 空 / 过长(模型啰嗦失控)→ 回退原 query(避免伤检索)
            if not rewritten or len(rewritten) > max(50, 3 * len(query)):
                logger.info("rewrite 输出异常(空/过长),回退原 query:%r", rewritten[:60])
                return query
            logger.info("rewrite: %s → %s", query, rewritten)
            return rewritten
        except Exception as e:
            logger.warning("rewrite 失败,回退原 query: %s", e)
            return query
