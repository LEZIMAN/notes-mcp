"""Reranker:cross-encoder 精排(bge-reranker-v2-m3)。

bi-encoder(嵌入)快但粗:query/doc 分别编码再算距离,丢失交互信息,
导致"distance 近但语义无关"的硬凑(见 docs/检索eval报告.md 负例)。
cross-encoder 准但慢:(query,doc) 拼一起送模型,捕获交互,精准打分。

链路:语义粗召回 top-N → reranker 精排 top-k。
不依赖 ollama(不支持 reranker 模型类型),用 FlagEmbedding 本地跑。
首次调用自动从 HuggingFace 下载模型(~2.2GB,缓存到 HF cache)。
"""

import logging

from FlagEmbedding import FlagReranker

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
        logger.info("加载 reranker:%s(fp16=%s)", model_name, use_fp16)
        self._model = FlagReranker(model_name, use_fp16=use_fp16)
        self._name = model_name

    @property
    def name(self) -> str:
        return self._name

    def rerank(self, query: str, documents: list[str]) -> list[float]:
        """对 (query, documents) 打分,返回归一化分数([0,1],越大越相关)。

        返回顺序与 documents 一齐。空输入返回空。
        """
        if not documents:
            return []
        pairs = [[query, doc] for doc in documents]
        scores = self._model.compute_score(pairs, normalize=True)
        # compute_score 单条返回 float,多条 list;统一成 list[float]
        if isinstance(scores, (int, float)):
            return [float(scores)]
        return [float(s) for s in scores]
