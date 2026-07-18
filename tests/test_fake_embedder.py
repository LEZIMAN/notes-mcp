"""FakeEmbedder 单测。

测纯逻辑,毫秒级,不依赖 ollama/Chroma/任何未实现模块——
让 pytest 在零业务代码阶段就有真测试可跑、能绿。
单行为单测、命名表意、断言具体(开发规范 §5.4)。
"""


def test_embed_is_deterministic(fake_embedder):
    """同文本两次 embed 必须完全相同(测试可重复的前提)。"""
    first = fake_embedder.embed("检索增强生成")
    second = fake_embedder.embed("检索增强生成")
    assert first == second, "同文本应得同向量,否则测试不可重复"


def test_embed_returns_correct_dim(fake_embedder):
    """embed 返回的向量长度必须等于 dim。"""
    assert fake_embedder.dim == 8
    vec = fake_embedder.embed("任意文本")
    assert len(vec) == 8, f"期望向量长度 8, 实际 {len(vec)}"


def test_different_texts_get_different_vectors(fake_embedder):
    """不同文本应得不同向量(否则 hash 退化,失去区分度)。"""
    assert fake_embedder.embed("RAG") != fake_embedder.embed("ReAct")


def test_dim_is_configurable(make_embedder):
    """dim 可配置,向量长度随 dim 变(将来要测 1024 维时用)。"""
    emb = make_embedder(dim=16)
    assert emb.dim == 16
    assert len(emb.embed("x")) == 16, "dim=16 时向量应为 16 维"


def test_name_property(make_embedder):
    """name 属性可设(将来参与 Chroma collection 命名)。"""
    emb = make_embedder(name="bge-m3")
    assert emb.name == "bge-m3"
