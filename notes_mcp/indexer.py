"""Indexer:增量建库编排器(扫目录 → diff → 切块 → embed → Chroma+BM25+SQLite)。

设计要点(见 docs/设计文档.md §3.1/§4):
  · Chroma 是单一真相(chunk 文本 + 向量 + metadata);BM25/SQLite 从它派生
  · 增量四态:新增 / 修改 / 删除 / touch(mtime 变但 hash 没变 → 跳过)
  · BM25 全量重建(从 Chroma 所有 document),持久化到 bm25_dir,启动 load
  · embed 失败 → 抛 IndexerError 整体崩(ollama 挂了就让 server 起不来)
  · 单文件读/切失败 → skip + 记 errors,不搞垮全库

内部 key 统一用 str(path.resolve())——SQLite 天然存 str,避免 Path/str 混用。
"""

import hashlib
import json
import logging
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import bm25s
import jieba

from notes_mcp.chunker import Chunk, chunk_markdown

logger = logging.getLogger(__name__)

# 扫描时排除的目录名(避免索引依赖/缓存/构建产物)
_EXCLUDE_DIRS = {
    "venv",
    ".venv",
    "env",
    "node_modules",
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "data",
    "dist",
}


@dataclass
class FileState:
    """SQLite 里一个文件的已知状态(上次成功建库时记录)。"""

    mtime: float
    hash: str


@dataclass
class BuildResult:
    """一次 build 的统计结果(server 启动时 log 给用户看)。"""

    added: int = 0  # 新增文件数
    modified: int = 0  # 内容修改文件数
    deleted: int = 0  # 删除文件数
    skipped: int = 0  # touch 跳过数(mtime 变 hash 没变)
    unchanged: int = 0  # 完全未变数
    total_files: int = 0  # 当前库总文件数
    total_chunks: int = 0  # 当前库总 chunk 数
    errors: list[str] = field(default_factory=list)  # 跳过的文件 + 原因


class IndexerError(Exception):
    """建库致命错误(如 embed 失败 = ollama 挂了)。server 应中止启动。"""


class _FileSkipError(Exception):
    """单文件可跳过的错误(读/切失败),build 记入 errors 继续。"""


class Indexer:
    """增量建库编排器。依赖注入 embedder/collection,便于测试用 fake。

    用法:
        indexer = Indexer(embedder, collection, sqlite_path, bm25_dir)
        indexer.load()                                    # 启动时尝试恢复 BM25
        result = indexer.build(notes_dirs, 300, 50)       # 增量建库
        # 之后 Searcher 用 indexer.collection / .bm25 / .bm25_id_map
    """

    def __init__(
        self,
        embedder,
        collection,
        sqlite_path: Path,
        bm25_dir: Path,
    ) -> None:
        self._embedder = embedder
        self._collection = collection
        self._sqlite_path = Path(sqlite_path)
        self._bm25_dir = Path(bm25_dir)
        self._bm25: Any = None  # bm25s.BM25 | None(无 stub,用 Any)
        self._id_map: list[str] = []  # BM25 行号 i ↔ chunk_id
        self._init_sqlite()

    # —— 给 Searcher 用的属性 ————————————————————————

    @property
    def collection(self):
        """Chroma collection(语义检索用)。"""
        return self._collection

    @property
    def bm25(self) -> Any:
        """BM25 检索器(关键词检索用),未建库时为 None。"""
        return self._bm25

    @property
    def bm25_id_map(self) -> list[str]:
        """BM25 行号 → chunk_id 的映射(RRF 融合的 id 对齐命门)。"""
        return self._id_map

    # —— SQLite 初始化 ————————————————————————————

    def _init_sqlite(self) -> None:
        """建 files 状态表(设计文档 §4.2)。"""
        self._sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self._sqlite_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS files (
                    path TEXT PRIMARY KEY,
                    mtime REAL,
                    hash TEXT,
                    indexed INTEGER DEFAULT 1
                )
                """
            )

    # —— load:启动时从磁盘恢复 BM25 ————————————————————

    def load(self) -> bool:
        """从 bm25_dir 加载持久化的 BM25 + id_map。返回是否加载成功。

        失败(目录不存在/损坏)不抛异常,返回 False,留给 build 时重建。
        """
        index_dir = self._bm25_dir / "index"
        id_map_file = self._bm25_dir / "id_map.json"
        if not index_dir.exists() or not id_map_file.exists():
            return False
        try:
            self._bm25 = bm25s.BM25.load(str(index_dir), load_corpus=False)
            self._id_map = json.loads(id_map_file.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001 — 加载失败原因多样,统一降级
            logger.warning("BM25 加载失败(%s),将在 build 时重建", e)
            self._bm25 = None
            self._id_map = []
            return False
        logger.info("BM25 已从 %s 恢复(%d chunks)", self._bm25_dir, len(self._id_map))
        return True

    # —— build:增量建库主流程 ———————————————————————

    def build(
        self,
        notes_dirs: list[Path],
        chunk_size: int = 300,
        overlap: int = 50,
    ) -> BuildResult:
        """增量建库:扫 → diff → Chroma 增量 → BM25 重建 → SQLite 同步。

        embed 失败抛 IndexerError(整体崩);单文件读/切失败 skip。
        """
        result = BuildResult()
        disk = self._scan(notes_dirs)  # {path_str: mtime}
        db = self._load_db()  # {path_str: FileState}
        added, modified, deleted, touched, unchanged = self._diff(disk, db)

        # 新增 + 修改:切块 → embed → upsert(embed 失败整体崩)
        for path in added:
            if self._try_index(Path(path), disk[path], notes_dirs, chunk_size, overlap, result):
                result.added += 1
        for path in modified:
            self._delete_file_chunks(Path(path))  # 先删旧 chunk
            if self._try_index(Path(path), disk[path], notes_dirs, chunk_size, overlap, result):
                result.modified += 1

        # 删除
        for path in deleted:
            self._delete_file_chunks(Path(path))
            result.deleted += 1

        result.skipped = len(touched)
        result.unchanged = len(unchanged)

        # BM25:有变化或首次未加载 → 全量重建 + 持久化
        if added or modified or deleted or self._bm25 is None:
            self._rebuild_bm25()

        # SQLite 同步状态
        self._sync_sqlite(added, modified, deleted, touched, disk)

        result.total_files = len(self._load_db())
        result.total_chunks = self._collection.count()
        return result

    def _try_index(
        self,
        path: Path,
        mtime: float,
        notes_dirs: list[Path],
        chunk_size: int,
        overlap: int,
        result: BuildResult,
    ) -> bool:
        """索引单文件。成功返回 True;读/切失败 skip(记 errors)返回 False。

        embed 失败抛 IndexerError(不在此捕获,向上传播让 build 中止)。
        """
        try:
            self._index_file(path, mtime, notes_dirs, chunk_size, overlap)
            return True
        except _FileSkipError as e:
            result.errors.append(f"{path}: {e}")
            return False

    def _index_file(
        self,
        path: Path,
        mtime: float,
        notes_dirs: list[Path],
        chunk_size: int,
        overlap: int,
    ) -> None:
        """读文件 → 切块 → embed → Chroma upsert。"""
        try:
            content = path.read_text(encoding="utf-8")
        except Exception as e:  # noqa: BLE001 — 编码/权限等
            raise _FileSkipError(f"读取失败: {e}") from e

        root = self._find_root(path, notes_dirs)
        chunks = chunk_markdown(content, path, root, mtime, chunk_size=chunk_size, overlap=overlap)
        if not chunks:
            raise _FileSkipError("空文件")

        # embed(失败不捕获 → IndexerError 整体崩)
        try:
            vectors = [self._embedder.embed(c.text) for c in chunks]
        except Exception as e:  # noqa: BLE001 — ollama 挂/网络断
            raise IndexerError(f"embed 失败({path}),疑似 ollama 未启动或模型未拉: {e}") from e

        self._collection.upsert(
            ids=[c.id for c in chunks],
            documents=[c.text for c in chunks],
            embeddings=vectors,
            metadatas=[self._chunk_meta(c) for c in chunks],
        )

    # —— Chroma 增量操作 ————————————————————————————

    def _delete_file_chunks(self, path: Path) -> None:
        """删某文件的所有 chunk(按 metadata.source 过滤)。"""
        self._collection.delete(where={"source": str(path)})

    @staticmethod
    def _chunk_meta(c: Chunk) -> dict:
        """构造 Chroma metadata(设计文档 §4.1 溯源字段)。"""
        return {
            "source": str(c.source),
            "title": c.title,
            "chunk_index": c.chunk_index,
            "mtime": c.mtime,
            "root": str(c.root),
        }

    # —— BM25 重建 + 持久化 ———————————————————————————

    def _rebuild_bm25(self) -> None:
        """从 Chroma 所有 document 全量重建 BM25 + 持久化。

        bm25s 无增量 API,故每次有变化都全量重建(chunk 级,id 对齐)。
        """
        all_data = self._collection.get(include=["documents"])
        ids = all_data["ids"]
        docs = all_data["documents"]
        self._id_map = list(ids)  # BM25 行号 i ↔ ids[i]

        tokenized = [list(jieba.cut(doc)) for doc in docs]  # 中文分词
        bm = bm25s.BM25()
        bm.index(tokenized)
        self._bm25 = bm
        self._save_bm25()
        logger.info("BM25 已重建并持久化(%d chunks)", len(self._id_map))

    def _save_bm25(self) -> None:
        """持久化 BM25 矩阵 + id_map 到 bm25_dir。"""
        self._bm25_dir.mkdir(parents=True, exist_ok=True)
        self._bm25.save(str(self._bm25_dir / "index"))  # bm25s 0.3+:实例方法
        (self._bm25_dir / "id_map.json").write_text(
            json.dumps(self._id_map, ensure_ascii=False), encoding="utf-8"
        )

    # —— 扫描 / diff / SQLite 同步 ——————————————————————

    def _scan(self, notes_dirs: list[Path]) -> dict[str, float]:
        """遍历 notes_dirs,收集所有 .md 的 {path_str: mtime}。排除依赖/缓存目录。"""
        result: dict[str, float] = {}
        for root in notes_dirs:
            root = Path(root).resolve()
            if not root.exists():
                continue
            for path in root.rglob("*.md"):
                if any(part in _EXCLUDE_DIRS for part in path.parts):
                    continue
                result[str(path.resolve())] = path.stat().st_mtime
        return result

    @staticmethod
    def _find_root(path: Path, notes_dirs: list[Path]) -> Path:
        """找 path 属于哪个 notes_dir(多目录溯源)。找不到回退到父目录。"""
        path = Path(path).resolve()
        for root in notes_dirs:
            root_resolved = Path(root).resolve()
            try:
                path.relative_to(root_resolved)
                return root_resolved
            except ValueError:
                continue
        return path.parent

    def _load_db(self) -> dict[str, FileState]:
        """读 SQLite files 表 → {path_str: FileState}。"""
        if not self._sqlite_path.exists():
            return {}
        with sqlite3.connect(self._sqlite_path) as conn:
            rows = conn.execute("SELECT path, mtime, hash FROM files").fetchall()
        return {row[0]: FileState(mtime=row[1], hash=row[2]) for row in rows}

    def _diff(
        self,
        disk: dict[str, float],
        db: dict[str, FileState],
    ) -> tuple[set[str], set[str], set[str], set[str], set[str]]:
        """对比磁盘与 SQLite,返回 (added, modified, deleted, touched, unchanged)。

        touched = mtime 变了但内容(hash)没变 → 跳过(省 embed)。
        """
        disk_paths = set(disk)
        db_paths = set(db)

        added = disk_paths - db_paths
        deleted = db_paths - disk_paths
        common = disk_paths & db_paths

        modified: set[str] = set()
        touched: set[str] = set()
        unchanged: set[str] = set()

        for path in common:
            state = db[path]
            if disk[path] == state.mtime:
                unchanged.add(path)
            elif self._content_hash(Path(path)) == state.hash:
                touched.add(path)  # mtime 变,内容没变
            else:
                modified.add(path)

        return added, modified, deleted, touched, unchanged

    @staticmethod
    def _content_hash(path: Path) -> str:
        """算文件内容 md5(diff 判定 touch vs modified 用)。"""
        content = Path(path).read_bytes()
        return hashlib.md5(content).hexdigest()

    def _sync_sqlite(
        self,
        added: set[str],
        modified: set[str],
        deleted: set[str],
        touched: set[str],
        disk: dict[str, float],
    ) -> None:
        """把本次变化同步进 SQLite files 表。"""
        with sqlite3.connect(self._sqlite_path) as conn:
            for path in deleted:
                conn.execute("DELETE FROM files WHERE path = ?", (path,))
            for path in added | modified | touched:
                try:
                    h = self._content_hash(Path(path))
                except OSError:
                    continue  # 读失败的不入库,下次重试
                conn.execute(
                    "INSERT OR REPLACE INTO files (path, mtime, hash, indexed) VALUES (?, ?, ?, 1)",
                    (path, disk.get(path, 0.0), h),
                )
            conn.commit()
