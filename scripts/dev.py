"""scripts/dev.py —— notes-mcp 开发命令统一入口。

为什么有它:server + 后端 + 前端是多服务,index/test/lint 这堆命令散在各处、
记不住。这里用 argparse 收成一个入口(Windows 友好、零第三方依赖,不用 make):

    python scripts/dev.py lint            # ruff 静态检查
    python scripts/dev.py format          # ruff 格式化(自动改)
    python scripts/dev.py type            # mypy 类型检查(notes_mcp)
    python scripts/dev.py test            # pytest 单元 + 集成
    python scripts/dev.py coverage        # pytest + 覆盖率
    python scripts/dev.py check-sync      # 校验核心依赖/配置齐全(防文档漂移)
    python scripts/dev.py install-hooks   # 装 pre-commit git 钩子
    python scripts/dev.py serve --transport stdio   # 跑 server(cli 实现后)
    python scripts/dev.py index           # 建库(cli 实现后)

设计:所有子命令用 subprocess 调对应工具,用 sys.executable 确保走当前
解释器(不必先激活 venv)。退出码透传,便于接 CI。
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

# 项目根目录:本文件在 scripts/ 下,父目录即项目根
ROOT = Path(__file__).resolve().parent.parent

# 设计文档点名的核心依赖/配置键——丢了就是「文档与文件漂移」(check-sync 守它们)
REQUIRED_DEPS = {
    "fastmcp",
    "langchain-mcp-adapters",
    "langgraph",
    "langchain-openai",
    "chromadb",
    "bm25s",
    "jieba",
    "openai",
    "python-dotenv",
    "fastapi",
    "uvicorn",
    "httpx",
}
REQUIRED_ENV_KEYS = {
    "NOTES_DIR",
    "OLLAMA_BASE_URL",
    "OLLAMA_MODEL",
    "OLLAMA_API_KEY",
    "EMBED_MODEL",
    "TOP_K",
    "CHUNK_SIZE",
    "OVERLAP",
    "CHROMA_PATH",
    "SQLITE_PATH",
    "MCP_HTTP_HOST",
    "MCP_HTTP_PORT",
    "WEB_BACKEND_HOST",
    "WEB_BACKEND_PORT",
    "FRONTEND_ORIGIN",
    "LOG_LEVEL",
}


def _run(cmd: list[str]) -> int:
    """在项目根目录跑一条命令,继承当前环境。打印命令、透传退出码。"""
    print(f"$ {' '.join(cmd)}", flush=True)
    return subprocess.run(cmd, cwd=ROOT, check=False).returncode


def _py(*args: str) -> list[str]:
    """构造 [当前解释器, *args],确保用 venv 的 python(不必激活)。"""
    return [sys.executable, *args]


# —— 各子命令实现 ————————————————————————————————————————————


def cmd_lint(_args: argparse.Namespace) -> int:
    """ruff 静态检查(配置在 pyproject.toml [tool.ruff])。"""
    return _run(_py("-m", "ruff", "check", "."))


def cmd_format(_args: argparse.Namespace) -> int:
    """ruff 格式化,自动改写。"""
    return _run(_py("-m", "ruff", "format", "."))


def cmd_type(_args: argparse.Namespace) -> int:
    """mypy 类型检查(只检 notes_mcp;tests/scripts/web 已 exclude)。"""
    return _run(_py("-m", "mypy", "notes_mcp"))


def cmd_test(extra_args: list[str]) -> int:
    """pytest 单元 + 集成测试(用 fake embedder,不依赖 ollama)。

    extra_args 原样透传给 pytest(如 -x / -k 名称 / tests/test_x.py)。
    """
    return _run(_py("-m", "pytest", *extra_args))


def cmd_coverage(_args: argparse.Namespace) -> int:
    """pytest + 覆盖率报告(终端,带未覆盖行号)。"""
    return _run(_py("-m", "pytest", "--cov=notes_mcp", "--cov-report=term-missing"))


def cmd_install_hooks(_args: argparse.Namespace) -> int:
    """装 pre-commit git 钩子(之后每次 git commit 自动 lint + type)。"""
    return _run(_py("-m", "pre_commit", "install"))


def cmd_serve(args: argparse.Namespace) -> int:
    """跑 notes-mcp server(依赖 cli.py;未实现时给友好提示)。"""
    if not (ROOT / "notes_mcp" / "cli.py").exists():
        print(
            "⚠️ notes_mcp/cli.py 尚未实现(接续点:config → embedder → ... → cli)。",
            file=sys.stderr,
        )
        return 1
    return _run(_py("-m", "notes_mcp", "serve", "--transport", args.transport))


def cmd_index(_args: argparse.Namespace) -> int:
    """建库:扫笔记 → 切块 → Chroma + BM25(依赖 cli.py)。"""
    if not (ROOT / "notes_mcp" / "cli.py").exists():
        print(
            "⚠️ notes_mcp/cli.py 尚未实现(接续点:config → embedder → indexer → cli)。",
            file=sys.stderr,
        )
        return 1
    return _run(_py("-m", "notes_mcp", "index"))


def cmd_check_sync(_args: argparse.Namespace) -> int:
    """校验核心依赖/配置键齐全——防「改了文件忘了同步文档」的漂移复发。

    守两份白名单(见模块顶部):核心依赖必须在 requirements.txt,
    核心环境变量键必须在 .env.example。缺了就报错。
    """
    errors: list[str] = []

    # 1. requirements.txt 核心依赖
    req_text = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    deps: set[str] = set()
    for raw in req_text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("-r"):
            continue
        match = re.match(r"^([A-Za-z0-9_.\-]+)", line)  # 取到版本符/ [extra] 前
        if match:
            deps.add(match.group(1).lower())
    missing_deps = REQUIRED_DEPS - deps
    if missing_deps:
        errors.append(f"requirements.txt 缺核心依赖: {sorted(missing_deps)}")

    # 2. .env.example 核心键
    env_file = ROOT / ".env.example"
    if not env_file.exists():
        errors.append(".env.example 不存在(README 的 cp .env.example .env 会失败)")
    else:
        env_text = env_file.read_text(encoding="utf-8")
        keys = set(re.findall(r"^([A-Z][A-Z0-9_]*)=", env_text, re.MULTILINE))
        missing_keys = REQUIRED_ENV_KEYS - keys
        if missing_keys:
            errors.append(f".env.example 缺核心键: {sorted(missing_keys)}")

    if errors:
        print("❌ check-sync 失败(疑似文档与文件漂移):", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        print("提示:同步 docs/配置.md §4/§5 与对应文件(单一信息源)。", file=sys.stderr)
        return 1

    print("✅ check-sync 通过:核心依赖与配置键齐全,无漂移。")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """构造 argparse,子命令 → 处理函数。"""
    parser = argparse.ArgumentParser(
        prog="python scripts/dev.py",
        description="notes-mcp 开发命令统一入口(Windows 友好,零第三方依赖)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # 无额外参数的子命令:批量注册(避免每行 add_parser + set_defaults 过长)
    simple_cmds = [
        ("lint", cmd_lint, "ruff 静态检查"),
        ("format", cmd_format, "ruff 格式化(自动改)"),
        ("type", cmd_type, "mypy 类型检查(notes_mcp)"),
        ("coverage", cmd_coverage, "pytest + 覆盖率报告"),
        ("check-sync", cmd_check_sync, "校验核心依赖/配置齐全(防漂移)"),
        ("install-hooks", cmd_install_hooks, "装 pre-commit git 钩子"),
        ("index", cmd_index, "建库(cli 实现后)"),
    ]
    for name, func, help_text in simple_cmds:
        sub.add_parser(name, help=help_text).set_defaults(func=func)

    # test 子命令:参数原样透传给 pytest,在 main 里特判(不走 argparse)
    sub.add_parser("test", help="pytest 单元+集成(透传 -x/-k/路径 给 pytest)")

    p_serve = sub.add_parser("serve", help="跑 notes-mcp server")
    p_serve.add_argument("--transport", choices=["stdio", "http"], default="stdio")
    p_serve.set_defaults(func=cmd_serve)

    return parser


def main() -> int:
    """解析参数并分发到对应子命令,返回其退出码。"""
    argv = sys.argv[1:]
    # test 子命令特判:argparse 对透传的 `-` 开头参数(-q/-x/-k)有局限,
    # 直接把 test 之后的参数原样交给 pytest,体验最自然。
    if argv and argv[0] == "test":
        return cmd_test(argv[1:])

    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
