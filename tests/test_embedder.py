"""OllamaEmbedder 单测:接口契约确认。

用 mock 绕开 ollama 依赖,纯逻辑,毫秒级。
真实 ollama 集成测用 @pytest.mark.needs_ollama(待 ollama 环境就绪后补)。
"""

from unittest.mock import MagicMock, patch

from notes_mcp.embedder import OllamaEmbedder


def test_dim_and_name_match_constructor_args():
    """dim 和 name 应等于构造参数。"""
    emb = OllamaEmbedder("http://x:11434/v1", model="my-model", dim=512)
    assert emb.dim == 512
    assert emb.name == "my-model"


def test_default_model_is_bge_m3():
    """默认 model='bge-m3',dim=1024。"""
    emb = OllamaEmbedder("http://x:11434/v1")
    assert emb.name == "bge-m3"
    assert emb.dim == 1024


@patch("notes_mcp.embedder.openai.OpenAI")
def test_embed_calls_openai_and_returns_vector(mock_openai):
    """embed() 调 openai embeddings.create,返回确定性 list[float]。"""
    mock_data = MagicMock()
    mock_data.embedding = [0.1, 0.2, 0.3]
    mock_response = MagicMock()
    mock_response.data = [mock_data]
    mock_client = MagicMock()
    mock_client.embeddings.create.return_value = mock_response
    mock_openai.return_value = mock_client

    emb = OllamaEmbedder("http://x:11434/v1", model="bge-m3", dim=3)
    vec = emb.embed("测试文本")

    assert vec == [0.1, 0.2, 0.3]
    assert len(vec) == emb.dim
    mock_client.embeddings.create.assert_called_once_with(model="bge-m3", input=["测试文本"])


@patch("notes_mcp.embedder.openai.OpenAI")
def test_embed_passes_correct_model(mock_openai):
    """构造时的 model 传给 embeddings.create——不同模型不同维度。"""
    mock_data = MagicMock()
    mock_data.embedding = [0.0]
    mock_client = MagicMock()
    mock_client.embeddings.create.return_value = MagicMock(data=[mock_data])
    mock_openai.return_value = mock_client

    emb = OllamaEmbedder("http://x:11434/v1", model="custom-model", dim=1)
    emb.embed("x")

    mock_client.embeddings.create.assert_called_once_with(model="custom-model", input=["x"])


@patch("notes_mcp.embedder.openai.OpenAI")
def test_embed_batch_returns_vectors_in_order(mock_openai):
    """embed_batch 返回与输入同序的向量列表,input 传数组。"""
    d1, d2, d3 = MagicMock(), MagicMock(), MagicMock()
    d1.embedding = [0.1]
    d2.embedding = [0.2]
    d3.embedding = [0.3]
    resp = MagicMock()
    resp.data = [d1, d2, d3]
    client = MagicMock()
    client.embeddings.create.return_value = resp
    mock_openai.return_value = client

    emb = OllamaEmbedder("http://x:11434/v1", dim=1)
    vecs = emb.embed_batch(["a", "b", "c"])
    assert vecs == [[0.1], [0.2], [0.3]]
    client.embeddings.create.assert_called_once_with(model="bge-m3", input=["a", "b", "c"])


def test_embed_batch_empty_returns_empty(fake_embedder):
    """空输入返回空列表。"""
    assert fake_embedder.embed_batch([]) == []
