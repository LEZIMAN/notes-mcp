"""agent 单测:build_servers / build_llm 配置构造(纯函数,不依赖真实 server/LLM)。

agent 主流程(amain / chat)依赖真实 LLM + 多 server,标 @pytest.mark.integration。
"""

import sys

import agent
from notes_mcp.config import Config

# —— build_servers(stdio / http)————————————————————————————


def test_build_servers_stdio(tmp_path):
    """stdio 模式:notes-mcp 是 command/args/cwd 子进程配置。"""
    servers = agent.build_servers("stdio", tmp_path)
    assert {"notes-mcp", "filesystem"} <= servers.keys()
    assert "fetch" not in servers  # 官方 server-fetch 已下架,暂不连
    notes = servers["notes-mcp"]
    assert notes["transport"] == "stdio"
    assert notes["command"] == sys.executable
    assert "-m" in notes["args"]
    assert "notes_mcp" in notes["args"]
    assert notes["cwd"] == str(agent.PROJECT_ROOT)


def test_build_servers_http(tmp_path):
    """http 模式:notes-mcp 是 url + streamable-http。"""
    servers = agent.build_servers("http", tmp_path)
    notes = servers["notes-mcp"]
    assert notes["transport"] == "streamable-http"
    assert "8765" in notes["url"]


def test_filesystem_always_npx(tmp_path):
    """filesystem 固定 npx(stdio),不受 transport 影响。"""
    for transport in ("stdio", "http"):
        servers = agent.build_servers(transport, tmp_path)
        s = servers["filesystem"]
        assert s["command"] == "npx"
        assert s["transport"] == "stdio"
        assert "-y" in s["args"]


def test_filesystem_scoped_to_notes_dir(tmp_path):
    """filesystem 的可访问目录 = notes_dir(防越权读到别处)。"""
    servers = agent.build_servers("stdio", tmp_path)
    assert str(tmp_path) in servers["filesystem"]["args"]


def test_notes_http_url_constant():
    """http 模式的 URL 是项目约定的 notes-mcp 端点。"""
    assert agent.NOTES_SERVER_HTTP_URL.endswith("/mcp")


# —— build_llm ————————————————————————————————————————————


def test_build_llm_uses_config(tmp_path):
    """build_llm 从 config 取 ollama 配置(model/base_url)。"""
    config = Config.from_env(env_file=tmp_path / "noenv")
    llm = agent.build_llm(config)
    model = str(getattr(llm, "model", "") or getattr(llm, "model_name", ""))
    assert "qwen3" in model
