"""OllamaEmbedder:调 ollama 做文本嵌入(设计文档 §5.2 · 开发规范 §3)。

接口:
  .embed(text) → list[float]   把文本变成向量
  .dim → int                   向量维度(如 bge-m3 = 1024)
  .name → str                  嵌入器名(参与 Chroma collection 命名)

依赖:openai 包走 ollama 的 OpenAI 兼容 /v1 端点。
"""

import openai


class OllamaEmbedder:
    """用 ollama 提供 embedding 服务。

    用法:
        emb = OllamaEmbedder(base_url="http://127.0.0.1:11434/v1", model="bge-m3")
        vec = emb.embed("检索增强生成")  # → list[float],长度 dim
    """

    def __init__(
        self,
        base_url: str,
        model: str = "bge-m3",
        dim: int = 1024,
        api_key: str = "ollama",
    ) -> None:
        # 延迟 openai 客户端创建,以便依赖注入后再调
        self._client = openai.OpenAI(base_url=base_url, api_key=api_key)
        self._model = model
        self._dim = dim
        self._name = model

    # —— 公共属性 ————————————————————————————————

    @property
    def dim(self) -> int:
        """向量维度(如 bge-m3 = 1024)。"""
        return self._dim

    @property
    def name(self) -> str:
        """嵌入器名(用作 Chroma collection 命名后缀,如 notes_bge-m3_1024)。"""
        return self._name

    # —— 核心方法 ————————————————————————————————

    def embed(self, text: str) -> list[float]:
        """把单段文本变成 dim 维向量(调 ollama /v1/embeddings)。

        若 ollama 未启动或模型未 pull,openai SDK 抛异常,
        由调用方(server/indexer)捕获处理。
        """
        response = self._client.embeddings.create(
            model=self._model,
            input=[text],
        )
        return response.data[0].embedding
