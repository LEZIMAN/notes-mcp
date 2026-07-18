"""Config 单测:from_env 读配置 / validate 校验。

纯逻辑,毫秒级,不依赖 .env 文件 / ollama / Chroma。
"""

from pathlib import Path

import pytest

from notes_mcp.config import Config, ConfigError

# —— 辅助 ————————————————————————————————————————————————


def _make_cfg(**overrides) -> Config:
    """造 Config 实例(测试用),只设关心的字段,其余给合法默认。"""
    defaults = dict(
        notes_dirs=[Path("/tmp")],
        ollama_base_url="http://127.0.0.1:11434/v1",
        ollama_model="qwen3:8b",
        ollama_api_key="ollama",
        embed_model="bge-m3",
        top_k=5,
        chunk_size=300,
        overlap=50,
        chroma_path=Path("data/chroma"),
        sqlite_path=Path("data/index_state.db"),
        mcp_http_host="0.0.0.0",
        mcp_http_port=8765,
        web_backend_host="0.0.0.0",
        web_backend_port=8000,
        frontend_origin="http://localhost:5173",
        log_level="INFO",
    )
    defaults.update(overrides)
    return Config(**defaults)


# —— from_env 测试 ———————————————————————————————————————


def test_from_env_without_dotenv_uses_defaults(monkeypatch):
    """无 .env 文件、无环境变量时,fallback 到 _DEFAULTS。"""
    # 清除可能干扰的环境变量
    for key in ["NOTES_DIR", "TOP_K", "CHUNK_SIZE"]:
        monkeypatch.delenv(key, raising=False)

    cfg = Config.from_env(env_file=Path("nosuchfile_nope"))
    assert cfg.top_k == 5
    assert cfg.chunk_size == 300
    assert cfg.overlap == 50
    assert cfg.ollama_base_url == "http://127.0.0.1:11434/v1"
    assert cfg.ollama_model == "qwen3:8b"
    assert cfg.embed_model == "bge-m3"
    assert cfg.notes_dirs == []  # NOTES_DIR 未设


def test_from_env_notes_dirs_semicolon_split(monkeypatch, tmp_path):
    """NOTES_DIR 分号分隔 → 解析为 list[Path]。"""
    d1 = tmp_path / "笔记1"
    d2 = tmp_path / "笔记2"
    d1.mkdir()
    d2.mkdir()
    monkeypatch.setenv("NOTES_DIR", f"{d1};{d2}")

    cfg = Config.from_env(env_file=Path("nosuchfile"))
    assert cfg.notes_dirs == [d1, d2]


def test_from_env_with_spaces_in_dirs(monkeypatch, tmp_path):
    """NOTES_DIR 值含空格时去空白。"""
    d = tmp_path / "笔记"
    d.mkdir()
    monkeypatch.setenv("NOTES_DIR", f" {d} ; ")

    cfg = Config.from_env(env_file=Path("nosuchfile"))
    assert cfg.notes_dirs == [d]


def test_from_env_overrides_default(monkeypatch):
    """环境变量覆盖 _DEFAULTS。"""
    monkeypatch.setenv("TOP_K", "10")
    monkeypatch.setenv("CHUNK_SIZE", "500")
    monkeypatch.setenv("MCP_HTTP_PORT", "9999")

    cfg = Config.from_env(env_file=Path("nosuchfile"))
    assert cfg.top_k == 10
    assert cfg.chunk_size == 500
    assert cfg.mcp_http_port == 9999


def test_from_env_empty_notes_dir(monkeypatch):
    """NOTES_DIR 为空字符串 → notes_dirs 为空列表(校验阶段报)。"""
    monkeypatch.setenv("NOTES_DIR", "")
    cfg = Config.from_env(env_file=Path("nosuchfile"))
    assert cfg.notes_dirs == []


# —— validate 测试 ——————————————————————————————————————


def test_validate_ok(tmp_path):
    """合法配置应静默通过。"""
    d = tmp_path / "notes"
    d.mkdir()
    cfg = _make_cfg(notes_dirs=[d])
    cfg.validate()  # 不抛异常就是过


def test_validate_notes_dirs_empty():
    """notes_dirs 为空时抛 ConfigError,提及 NOTES_DIR。"""
    cfg = _make_cfg(notes_dirs=[])
    with pytest.raises(ConfigError, match="NOTES_DIR"):
        cfg.validate()


def test_validate_note_dir_not_found(tmp_path):
    """笔记目录不存在时抛异常。"""
    missing = tmp_path / "ghost_dir"
    cfg = _make_cfg(notes_dirs=[missing])
    with pytest.raises(ConfigError, match="笔记目录不存在"):
        cfg.validate()


def test_validate_top_k_zero():
    """TOP_K < 1 时抛 ConfigError。"""
    cfg = _make_cfg(top_k=0)
    with pytest.raises(ConfigError, match="TOP_K"):
        cfg.validate()


def test_validate_chunk_size_too_small():
    """CHUNK_SIZE < 50 时抛异常。"""
    cfg = _make_cfg(chunk_size=30)
    with pytest.raises(ConfigError, match="CHUNK_SIZE"):
        cfg.validate()


def test_validate_overlap_not_less_than_chunk_size():
    """OVERLAP >= CHUNK_SIZE 时抛异常。"""
    cfg = _make_cfg(chunk_size=300, overlap=300)
    with pytest.raises(ConfigError, match="OVERLAP"):
        cfg.validate()


# —— ConfigError 测试 ———————————————————————————————————


def test_config_error_contains_all_errors():
    """ConfigError 应列出所有校验失败项。"""
    cfg = _make_cfg(notes_dirs=[], top_k=0, overlap=500, chunk_size=200)
    with pytest.raises(ConfigError) as exc:
        cfg.validate()
    msg = str(exc.value)
    assert "NOTES_DIR" in msg
    assert "TOP_K" in msg
    assert "OVERLAP" in msg
