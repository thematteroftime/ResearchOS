# tests/test_memu_oss_client_unit.py
"""
MemU OSS 客户端单测：无 LLM key 时禁用；memorize/retrieve 返回 error。
运行：在 merge_project 根目录
  python -m pytest tests/test_memu_oss_client_unit.py -v -s
"""

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env", override=True)
except ImportError:
    pass


def test_oss_client_no_key_disabled():
    """无 LLM API key 时 MemUOSSClient 应 _oss_enabled=False，enabled=False。"""
    from backend.memu_oss_client import MemUOSSClient
    tmp = Path(tempfile.mkdtemp())
    client = MemUOSSClient(
        user_id="unit_user",
        agent_id="physics_agent",
        db_path=tmp / "rec.db",
        storage_dir=tmp / "store",
        llm_api_key="",
    )
    assert getattr(client, "_oss_enabled", False) is False
    assert client.enabled is False
    print("[OK] OSS client no key -> disabled")


def test_oss_memorize_returns_error_when_disabled():
    """OSS 禁用时 memorize 返回含 error 的 dict。"""
    from backend.memu_oss_client import MemUOSSClient
    tmp = Path(tempfile.mkdtemp())
    client = MemUOSSClient(
        user_id="u",
        agent_id="physics_agent",
        db_path=tmp / "rec.db",
        storage_dir=tmp / "store",
        llm_api_key="",
    )
    out = client.memorize(conversation=[{"role": "user", "content": "test"}])
    assert out.get("error") == "memu_oss_disabled"
    print("[OK] memorize when disabled -> error", out.get("error"))


def test_oss_retrieve_returns_error_when_disabled():
    """OSS 禁用时 retrieve 返回含 error 的 dict。"""
    from backend.memu_oss_client import MemUOSSClient
    tmp = Path(tempfile.mkdtemp())
    client = MemUOSSClient(
        user_id="u",
        agent_id="physics_agent",
        db_path=tmp / "rec.db",
        storage_dir=tmp / "store",
        llm_api_key="",
    )
    out = client.retrieve(query="test")
    assert out.get("error") == "memu_oss_disabled"
    print("[OK] retrieve when disabled -> error", out.get("error"))


def test_create_memu_client_oss_fallback_to_cloud():
    """MEMU_BACKEND=oss 且无 LLM key 时 create_memu_client 回退为 MemUClient。"""
    from backend.memu_client import MemUClient, create_memu_client
    prev = os.environ.pop("MEMU_BACKEND", None)
    try:
        os.environ["MEMU_BACKEND"] = "oss"
        tmp = Path(tempfile.mkdtemp())
        client = create_memu_client(
            backend="oss",
            user_id="u",
            agent_id="physics_agent",
            db_path=tmp / "rec.db",
            storage_dir=tmp / "store",
        )
        # 无 key 时 OSS 不可用，应回退为 MemUClient
        assert type(client).__name__ == "MemUClient"
    finally:
        if prev is not None:
            os.environ["MEMU_BACKEND"] = prev
        else:
            os.environ.pop("MEMU_BACKEND", None)
    print("[OK] create_memu_client oss no key -> MemUClient fallback")


if __name__ == "__main__":
    test_oss_client_no_key_disabled()
    test_oss_memorize_returns_error_when_disabled()
    test_oss_retrieve_returns_error_when_disabled()
    test_create_memu_client_oss_fallback_to_cloud()
    print("\n[DONE] test_memu_oss_client_unit")
