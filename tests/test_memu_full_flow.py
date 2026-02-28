# tests/test_memu_full_flow.py
"""
memU 业务全流程测试（与 https://memu.pro/docs 一致）：

  第一步：上传多种格式文件到 memU，每条记录具备三要素——文件内容描述、索引 ID、存储路径。
  第二步：根据用户输入从 memU 匹配描述，得到相关度较高的文件索引 ID。
  第三步：用 ID 从 DB 取资源路径（或 URL）。
  第四步：将可下载列表交付用户，用户选择后下载到指定路径。

运行（在 merge_project 根目录）:
  python tests/test_memu_full_flow.py
  或
  python -m pytest tests/test_memu_full_flow.py -v -s
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env", override=True)
except ImportError:
    pass

REPO_ROOT = ROOT.parent
RESOURCES_DIR = REPO_ROOT / "memU_code" / "examples" / "resources"
TEST_DB_PATH = ROOT / "database" / "memu_records_test.db"
TEST_STORAGE_DIR = ROOT / "database" / "memu_storage_test"
TEST_DOWNLOADS_DIR = ROOT / "database" / "test_downloads"


def _ensure_resources() -> list:
    candidates = [
        RESOURCES_DIR / "docs" / "doc1.txt",
        RESOURCES_DIR / "docs" / "doc2.txt",
        RESOURCES_DIR / "conversations" / "conv1.json",
    ]
    found = [str(p) for p in candidates if p.exists()]
    if not found:
        fallback = ROOT / "data"
        fallback.mkdir(parents=True, exist_ok=True)
        placeholder = fallback / "memu_test_placeholder.txt"
        if not placeholder.exists():
            placeholder.write_text("MemU full flow test placeholder.", encoding="utf-8")
        found = [str(placeholder)]
    return found


def run_full_flow():
    """
    四步业务流：
    1. 上传 → 描述 + 索引 ID + 存储路径 写入 memU 与 DB
    2. 用户输入 → memU 匹配描述 → 得到相关文件 ID
    3. 用 ID 从 DB 取路径
    4. 交付：返回可下载列表，用户选择后 download_to_path 到指定路径
    """
    from backend.memu_client import MemUClient
    from backend.config import DB_DIR

    DB_DIR.mkdir(parents=True, exist_ok=True)
    TEST_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    TEST_DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)

    client = MemUClient(
        user_id="test_user_a",
        agent_id="agent_1",
        db_path=TEST_DB_PATH,
        storage_dir=TEST_STORAGE_DIR,
    )

    file_paths = _ensure_resources()
    print("========== 第一步：上传多种格式文件 ==========")
    print("  每个文件写入：文件内容描述（供 memU 匹配）、索引 ID（record_id）、存储路径（original_path）")
    print("  文件列表:", file_paths)
    out_upload = client.upload_files(file_paths=file_paths, user_input="测试描述", wait=True)
    record_ids = out_upload.get("record_ids") or []
    records = out_upload.get("records") or []
    print("  上传结果: record_ids=%s" % record_ids)
    for r in records:
        print("    - record_id=%s | file_name=%s | storage_path=%s | description_len=%s" % (
            r.get("record_id"), r.get("file_name"),
            (r.get("original_path") or "")[:50] + "..." if len(r.get("original_path") or "") > 50 else r.get("original_path"),
            len(r.get("description") or ""),
        ))

    print("\n========== 第二步：用户输入 → memU 匹配描述 → 得到相关文件索引 ID ==========")
    user_query = "document"
    out_match = client.match_and_resolve(query=user_query, limit=10)
    matched_ids = out_match.get("matched_record_ids") or []
    records_with_paths = out_match.get("records") or []
    print("  用户输入: %s" % user_query)
    print("  memU 匹配得到的索引 ID: %s" % matched_ids)
    print("  cloud.error: %s" % out_match.get("error"))

    print("\n========== 第三步：用 ID 从 DB 取资源路径 ==========")
    print("  可交付列表（含 record_id, description 摘要, storage_path, file_name）:")
    for rec in records_with_paths:
        print("    - record_id=%s | file_name=%s | storage_path=%s" % (
            rec.get("record_id"), rec.get("file_name"),
            (rec.get("storage_path") or "")[:60] + "..." if len(rec.get("storage_path") or "") > 60 else rec.get("storage_path"),
        ))

    print("\n========== 第四步：交付用户 → 用户选择后下载到指定路径 ==========")
    if records_with_paths:
        chosen = records_with_paths[0]
        rid = chosen.get("record_id")
        out_dl = client.download_to_path(record_id=rid, dest_dir=TEST_DOWNLOADS_DIR)
        if out_dl.get("error"):
            print("  下载失败: %s" % out_dl.get("error"))
        else:
            print("  用户选择 record_id=%s，已下载到: %s" % (rid, out_dl.get("saved_path")))
    else:
        print("  无匹配记录，跳过下载。")

    print("\n========== 可选：删除与 OpenRouter 增强 ==========")
    if record_ids:
        client.delete_record(record_id=record_ids[-1], remove_from_storage=True)
        print("  已删除一条记录及存储文件。")
    if os.getenv("OPENROUTER_API_KEY"):
        out_or = client.match_and_resolve(query="memory", limit=5, use_openrouter_query_rewrite=True)
        print("  OpenRouter 改写后 effective_query: %s" % out_or.get("effective_query"))

    print("\n[DONE] 测试 DB: %s  存储: %s  下载: %s" % (TEST_DB_PATH, TEST_STORAGE_DIR, TEST_DOWNLOADS_DIR))
    return record_ids


def test_memu_full_flow_integration():
    """Pytest：四步业务流 + 断言。"""
    from backend.memu_client import MemUClient
    run_full_flow()
    list_a = MemUClient(user_id="test_user_a", agent_id="agent_1", db_path=TEST_DB_PATH, storage_dir=TEST_STORAGE_DIR).list_records(limit=50)
    assert isinstance(list_a, list), "list_records 应返回 list"


if __name__ == "__main__":
    run_full_flow()
