"""cli 单测:参数解析 + 配置错误处理 + 建库流程(注入 fake embedder)。

不启真实 server/mcp.run(那会阻塞),只测 main() 的分发与错误路径。
建库流程用 monkeypatch 把 OllamaEmbedder 换成 FakeEmbedder、Collection 换内存版。
"""

import chromadb
import pytest

from notes_mcp import cli
from notes_mcp.config import Config
from tests.conftest import FakeEmbedder

# —— 参数解析 ————————————————————————————————————————————


def test_serve_subcommand_parses():
    args = cli._build_parser().parse_args(["serve", "--transport", "http", "--port", "9999"])
    assert args.command == "serve"
    assert args.transport == "http"
    assert args.port == 9999


def test_serve_default_transport_is_stdio():
    args = cli._build_parser().parse_args(["serve"])
    assert args.transport == "stdio"


def test_index_subcommand_parses():
    args = cli._build_parser().parse_args(["index"])
    assert args.command == "index"


def test_query_subcommand_parses_top_k():
    args = cli._build_parser().parse_args(["query", "RAG", "--top-k", "3"])
    assert args.command == "query"
    assert args.query == "RAG"
    assert args.top_k == 3


def test_no_subcommand_errors(capsys):
    """无子命令 → argparse 报错(退出码 2)。"""
    with pytest.raises(SystemExit) as exc:
        cli._build_parser().parse_args([])
    assert exc.value.code == 2


# —— 配置错误处理 ————————————————————————————————————————


def test_main_config_error_returns_2(monkeypatch, capsys, tmp_path):
    """NOTES_DIR 未设/目录不存在 → 退出码 2 + 提示。"""
    monkeypatch.delenv("NOTES_DIR", raising=False)
    monkeypatch.setattr("notes_mcp.config._find_env", lambda: None)  # 不读项目根 .env
    monkeypatch.setenv("CHROMA_PATH", str(tmp_path / "chroma"))
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "state.db"))

    rc = cli.main(["index"])
    assert rc == 2
    err = capsys.readouterr().err
    assert "配置错误" in err or "NOTES_DIR" in err


# —— 建库流程(注入 fake,不依赖 ollama)——————————————————————


@pytest.fixture
def patched_cli(monkeypatch, tmp_path):
    """把 cli 的 OllamaEmbedder / Collection 换成内存 fake 版。"""
    notes = tmp_path / "notes"
    notes.mkdir()
    (notes / "RAG.md").write_text("# RAG\n检索增强生成。", encoding="utf-8")
    (notes / "Embedding.md").write_text("# Embedding\n文本变向量。", encoding="utf-8")

    monkeypatch.setenv("NOTES_DIR", str(notes))
    monkeypatch.setenv("CHROMA_PATH", str(tmp_path / "chroma"))
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "state.db"))

    embedder = FakeEmbedder(dim=8)

    def fake_embedder(*a, **kw):
        return embedder

    collection = chromadb.EphemeralClient().get_or_create_collection(f"cli_{tmp_path.name}")

    def fake_get_collection(config):
        return collection

    monkeypatch.setattr(cli, "OllamaEmbedder", fake_embedder)
    monkeypatch.setattr(cli, "_get_collection", fake_get_collection)
    return notes, collection


def test_index_command_builds_library(patched_cli, capsys):
    """index 命令建库 → collection 有 chunk。"""
    notes, collection = patched_cli
    rc = cli.main(["index"])
    assert rc == 0
    assert collection.count() > 0


def test_query_command_prints_results(patched_cli, capsys):
    """query 命令 print 检索结果(含标题)。"""
    notes, collection = patched_cli
    rc = cli.main(["query", "RAG", "--top-k", "3"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "RAG" in out


def test_build_searcher_returns_searcher(patched_cli):
    """_build_searcher 造的 Searcher 能检索。"""
    notes, collection = patched_cli
    config = Config.from_env()
    searcher, result = cli._build_searcher(config)
    from notes_mcp.search import Searcher

    assert isinstance(searcher, Searcher)
    assert result.total_files == 2
    hits = searcher.search("RAG", top_k=3)
    assert len(hits) > 0


# —— embed 失败处理 ———————————————————————————————————————


def test_build_index_embed_failure_exits_3(monkeypatch, tmp_path):
    """embed 失败(ollama 挂)→ SystemExit(3) + 提示起 ollama。"""
    notes = tmp_path / "notes"
    notes.mkdir()
    (notes / "x.md").write_text("# X\n内容。", encoding="utf-8")
    monkeypatch.setenv("NOTES_DIR", str(notes))
    monkeypatch.setenv("CHROMA_PATH", str(tmp_path / "chroma"))
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "state.db"))

    class BrokenEmbedder:
        dim = 8
        name = "broken"

        def embed(self, text):
            raise ConnectionError("ollama 挂了")

    collection = chromadb.EphemeralClient().get_or_create_collection(f"broken_{tmp_path.name}")
    monkeypatch.setattr(cli, "OllamaEmbedder", lambda *a, **kw: BrokenEmbedder())
    monkeypatch.setattr(cli, "_get_collection", lambda config: collection)

    with pytest.raises(SystemExit) as exc:
        cli._build_index(Config.from_env())
    assert exc.value.code == 3
