# tests/test_utils.py
"""
测试用：所有参量初始化、步骤、输出 均 打印 + 写入调试文件，便于 bug 排查。
导出：DebugLogger, LOG_DIR, get_docs_path, get_test_db_and_storage, create_app_backend_for_test
"""

import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

# 测试日志目录
ROOT = Path(__file__).resolve().parent.parent
TESTS_DIR = Path(__file__).resolve().parent
LOG_DIR = TESTS_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)


def _safe_repr(obj: Any, max_len: int = 2000) -> str:
    """可读且截断的 repr，便于写入日志。"""
    if obj is None:
        return "None"
    if isinstance(obj, (str, int, float, bool)):
        s = str(obj)
        return s[:max_len] + "..." if len(s) > max_len else s
    if isinstance(obj, (list, tuple)):
        try:
            s = json.dumps(obj, ensure_ascii=False, indent=0)[:max_len]
            return s + "..." if len(str(obj)) > max_len else json.dumps(obj, ensure_ascii=False)
        except Exception:
            return str(obj)[:max_len]
    if isinstance(obj, dict):
        try:
            s = json.dumps(obj, ensure_ascii=False, indent=2)[:max_len]
            return s + "..." if len(s) >= max_len else s
        except Exception:
            return str(obj)[:max_len]
    return str(obj)[:max_len]


class DebugLogger:
    """
    每一步：打印 + 写入同一日志文件。
    用于：传入参数、使用的文件、使用的数据、使用的 prompt、中间过程、最后输出。
    """

    def __init__(self, log_name: str = "debug", subdir: Optional[str] = None):
        self.log_name = log_name
        self.subdir = Path(subdir) if subdir else LOG_DIR
        self.subdir.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S", time.localtime())
        self.log_path = self.subdir / f"{log_name}_{ts}.log"
        self._file = open(self.log_path, "w", encoding="utf-8")
        self._write(f"[INIT] 日志文件: {self.log_path}")
        self._write("=" * 60)

    def _write(self, line: str) -> None:
        self._file.write(line + "\n")
        self._file.flush()
        print(line)

    def log_input(self, name: str, value: Any, comment: str = "传入参数") -> None:
        """记录传入参数：先打印再写入。"""
        msg = f"[{comment}] {name} = {_safe_repr(value)}"
        self._write(msg)

    def log_step(self, step_name: str, message: str = "", data: Any = None) -> None:
        """记录中间步骤：步骤名、说明、可选数据。"""
        self._write(f"[STEP] {step_name} | {message}")
        if data is not None:
            self._write(f"  data: {_safe_repr(data)}")

    def log_prompt(self, name: str, content: str, max_chars: int = 500) -> None:
        """记录使用的 prompt：名称 + 内容（可截断）。"""
        self._write(f"[PROMPT] {name} | 长度={len(content)}")
        self._write(f"  内容(前{max_chars}字): {content[:max_chars]}{'...' if len(content) > max_chars else ''}")

    def log_file_used(self, label: str, path: str, exists: bool = False) -> None:
        """记录使用的文件路径。"""
        self._write(f"[文件] {label}: {path} | exists={exists}")

    def log_output(self, name: str, value: Any, comment: str = "返回/输出") -> None:
        """记录返回或输出。"""
        self._write(f"[{comment}] {name} = {_safe_repr(value)}")

    def log_db_or_storage(self, action: str, detail: str) -> None:
        """记录数据库或存储操作。"""
        self._write(f"[DB/STORAGE] {action} | {detail}")

    def save_markdown(self, name: str, content: str) -> Path:
        """将 Markdown 内容保存到 outputs 子目录，并记录路径。"""
        out_dir = self.subdir / "outputs"
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S", time.localtime())
        safe_name = name.replace(" ", "_").replace("/", "_")[:50]
        md_path = out_dir / f"{safe_name}_{ts}.md"
        md_path.write_text(content, encoding="utf-8")
        self._write(f"[输出文件] Markdown 已保存: {md_path}")
        return md_path

    def log_io(self, step: str, inputs: Dict[str, Any], outputs: Any) -> None:
        """记录步骤的输入与输出（便于核对正确性）。"""
        self._write(f"[输入] {step}")
        for k, v in inputs.items():
            self._write(f"  {k}: {_safe_repr(v)}")
        self._write(f"[输出] {step}")
        self._write(f"  {_safe_repr(outputs)}")

    def close(self) -> None:
        self._write("=" * 60)
        self._file.close()

    def __enter__(self) -> "DebugLogger":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


def get_docs_path(*parts: str) -> Path:
    """merge_project/docs 下文件路径。"""
    return ROOT / "docs" / Path(*parts)


def get_test_db_and_storage():
    """统一测试 DB 与存储路径，减少 database 目录混乱。所有场景测试应使用此函数。"""
    from backend.config import MEMU_TEST_DB, MEMU_TEST_STORAGE
    MEMU_TEST_STORAGE.mkdir(parents=True, exist_ok=True)
    return MEMU_TEST_DB, MEMU_TEST_STORAGE


def create_app_backend_for_test(user_id: str = "test_u", agent_id: str = "physics_agent"):
    """创建使用统一测试 DB 的 AppBackend，供测试复用。"""
    from backend.app_backend import AppBackend
    test_db, test_storage = get_test_db_and_storage()
    return AppBackend(
        memu_user_id=user_id,
        memu_agent_id=agent_id,
        memu_db_path=test_db,
        memu_storage_dir=test_storage,
    )
