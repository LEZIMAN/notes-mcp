"""Reranker:cross-encoder 精排(bge-reranker-v2-m3)。

bi-encoder(嵌入)快但粗:query/doc 分别编码再算距离,丢失交互信息,
导致"distance 近但语义无关"的硬凑(见 docs/04-测试/检索eval_2026-07-26.md 负例)。
cross-encoder 准但慢:(query,doc) 拼一起送模型,捕获交互,精准打分。

链路:语义粗召回 top-N → reranker 精排 top-k。
不依赖 ollama(不支持 reranker 模型类型),用 FlagEmbedding 本地跑。
首次调用自动从 HuggingFace 下载模型(~2.2GB,缓存到 HF cache)。
"""

import os

# reranker 模型已本地缓存:离线模式避免 huggingface_hub 联网查 model_info 超时(踩坑 #27)
# HF_HUB_OFFLINE 让 huggingface_hub 直接用本地缓存,不联网
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

import logging

logger = logging.getLogger(__name__)


class Reranker:
    """cross-encoder 精排器。依赖注入 model_name,便于测试/替换。

    用法:
        reranker = Reranker()
        scores = reranker.rerank(query, [doc1, doc2])  # 越大越相关
    """

    def __init__(
        self,
        model_name: str = "BAAI/bge-reranker-v2-m3",
        use_fp16: bool = True,
    ) -> None:
        self._model_name = model_name
        self._use_fp16 = use_fp16
        self._model = None  # 懒加载:首次 rerank 才加载,避免阻塞 server 启动(坑#20 MCP 超时)
        self._name = model_name

    def _ensure_loaded(self) -> None:
        """首次调用时加载模型。

        延迟 import FlagEmbedding(触发 torch 加载 ~5-10s),
        避免阻塞 notes-mcp 启动 → MCP initialize 超时(坑#20)。
        """
        if self._model is None:
            from FlagEmbedding import FlagReranker  # noqa: PLC0415 — 延迟 import

            logger.info("懒加载 reranker:%s(fp16=%s)", self._model_name, self._use_fp16)
            self._model = FlagReranker(self._model_name, use_fp16=self._use_fp16)

    @property
    def name(self) -> str:
        return self._name

    def rerank(self, query: str, documents: list[str]) -> list[float]:
        """对 (query, documents) 打分,返回归一化分数([0,1],越大越相关)。

        返回顺序与 documents 一齐。空输入返回空。
        """
        if not documents:
            return []
        self._ensure_loaded()
        pairs = [[query, doc] for doc in documents]
        scores = self._model.compute_score(pairs, normalize=True)
        # compute_score 单条返回 float,多条 list;统一成 list[float]
        if isinstance(scores, (int, float)):
            return [float(scores)]
        return [float(s) for s in scores]
