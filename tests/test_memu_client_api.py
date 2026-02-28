# tests/test_memu_client_api.py
"""
backend/memu_client.py 各 API 的测试：upload_files、list_records、get_download_info、download_to_path、match_and_resolve、insert_record、delete_record、get_retrieve_config。
使用 tests/logs 与临时 DB/存储，每步打印并写入调试文件。
"""

import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env", override=True)
except ImportError:
    pass

from tests.test_utils import DebugLogger, LOG_DIR, get_docs_path


def test_memu_client_init_and_get_retrieve_config():
    """测试 MemUClient 初始化与 get_retrieve_config。"""
    log = DebugLogger("test_memu_init", subdir=str(LOG_DIR))
    tmp = Path(tempfile.mkdtemp())
    db_path = tmp / "memu_test.db"
    storage_dir = tmp / "storage"
    log.log_input("db_path", str(db_path))
    log.log_input("storage_dir", str(storage_dir))
    from backend.memu_client import MemUClient
    client = MemUClient(api_key="", user_id="test_u", agent_id="physics_agent", db_path=db_path, storage_dir=storage_dir)
    log.log_step("MemUClient 初始化", "ok, enabled=%s" % client.enabled)
    cfg = client.get_retrieve_config("physics_agent")
    log.log_output("get_retrieve_config(physics_agent)", cfg)
    assert isinstance(cfg, dict)
    log.close()


def test_memu_upload_files_and_list():
    """测试 upload_files（使用 docs 下 CSV）+ list_records；验证 scene/record_id 布局与 DB 写入。"""
    log = DebugLogger("test_memu_upload_list", subdir=str(LOG_DIR))
    tmp = Path(tempfile.mkdtemp())
    db_path = tmp / "memu_test.db"
    storage_dir = tmp / "storage"
    csv_path = get_docs_path("FH_data.csv")
    log.log_file_used("测试数据", str(csv_path), csv_path.exists())
    if not csv_path.exists():
        (tmp / "dummy.csv").write_text("a,b\n1,2", encoding="utf-8")
        csv_path = tmp / "dummy.csv"
    log.log_input("file_paths", [str(csv_path)])
    log.log_input("scene", "data")
    log.log_input("user_input", "测试数据上传")
    from backend.memu_client import MemUClient
    client = MemUClient(api_key="", user_id="test_u", agent_id="physics_agent", db_path=db_path, storage_dir=storage_dir)
    out = client.upload_files(file_paths=[str(csv_path)], scene="data", user_input="测试数据上传", user_id="test_u", agent_id="physics_agent", wait=False)
    log.log_output("upload_files(...)", out)
    log.log_db_or_storage("upload 后", "record_ids=%s" % out.get("record_ids"))
    assert out.get("record_ids")
    rec = out.get("records", [{}])[0]
    log.log_step("original_path 应为相对路径 data/<record_id>", rec.get("original_path"))
    assert rec.get("original_path", "").startswith("data/")
    lst = client.list_records(user_id="test_u", agent_id="physics_agent", limit=10)
    log.log_output("list_records(...)", {"count": len(lst), "first_record_id": lst[0].get("record_id") if lst else None})
    log.close()


def test_memu_get_download_info_and_download_to_path():
    """测试 get_download_info、download_to_path。"""
    log = DebugLogger("test_memu_download", subdir=str(LOG_DIR))
    tmp = Path(tempfile.mkdtemp())
    db_path = tmp / "memu_test.db"
    storage_dir = tmp / "storage"
    f = tmp / "f.txt"
    f.write_text("test content", encoding="utf-8")
    from backend.memu_client import MemUClient
    client = MemUClient(api_key="", user_id="test_u", agent_id="physics_agent", db_path=db_path, storage_dir=storage_dir)
    up = client.upload_files(file_paths=[str(f)], scene="other", user_id="test_u", agent_id="physics_agent", wait=False)
    rid = up["record_ids"][0]
    log.log_input("record_id", rid)
    info = client.get_download_info(record_id=rid, user_id="test_u", agent_id="physics_agent")
    log.log_output("get_download_info(...)", info)
    assert info and "resolved_storage_folder" in info
    dest = tmp / "downloads"
    out = client.download_to_path(record_id=rid, dest_dir=dest, user_id="test_u", agent_id="physics_agent")
    log.log_output("download_to_path(...)", out)
    assert not out.get("error")
    log.log_file_used("下载目标", out.get("saved_path", ""), Path(out.get("saved_path", "")).exists() if out.get("saved_path") else False)
    log.close()


def test_memu_match_and_resolve():
    """测试 match_and_resolve：limit 来自 config，返回 records 含 resolved_storage_folder。"""
    log = DebugLogger("test_memu_match", subdir=str(LOG_DIR))
    tmp = Path(tempfile.mkdtemp())
    db_path = tmp / "memu_test.db"
    storage_dir = tmp / "storage"
    f = tmp / "g.txt"
    f.write_text("physics content", encoding="utf-8")
    from backend.memu_client import MemUClient
    client = MemUClient(api_key="", user_id="test_u", agent_id="physics_agent", db_path=db_path, storage_dir=storage_dir)
    client.upload_files(file_paths=[str(f)], scene="paper", user_id="test_u", agent_id="physics_agent", wait=False)
    log.log_input("query", "physics")
    log.log_input("limit", None)
    out = client.match_and_resolve(query="physics", user_id="test_u", agent_id="physics_agent", limit=None)
    log.log_output("match_and_resolve(...)", {"matched_record_ids": out.get("matched_record_ids"), "records_count": len(out.get("records", []))})
    for r in out.get("records", [])[:2]:
        log.log_step("record", r.get("record_id") + " | " + str(r.get("resolved_storage_folder", ""))[:80])
    log.close()


def test_memu_retrieve_by_agent_id():
    """测试 retrieve 按 agent_id 调用；打印每次调用的 agent_id。"""
    log = DebugLogger("test_memu_retrieve", subdir=str(LOG_DIR))
    tmp = Path(tempfile.mkdtemp())
    from backend.memu_client import MemUClient
    client = MemUClient(api_key="", user_id="test_u", agent_id="_default", db_path=tmp / "m.db", storage_dir=tmp / "s")
    for aid in ("physics_agent", "cs_agent", "_default"):
        out = client.retrieve(query="test query", user_id="test_u", agent_id=aid)
        log.log_step("retrieve(agent_id=%s)" % aid, "keys=%s" % (list(out.keys()) if isinstance(out, dict) else type(out)))
        log.log_output("retrieve(agent_id=%s)" % aid, {"error": out.get("error") if isinstance(out, dict) else None})
    log.close()


def test_memu_insert_record_and_delete():
    """测试 insert_record、delete_record(remove_from_storage=True)。"""
    log = DebugLogger("test_memu_insert_delete", subdir=str(LOG_DIR))
    tmp = Path(tempfile.mkdtemp())
    db_path = tmp / "memu_test.db"
    storage_dir = tmp / "storage"
    (storage_dir / "test_u" / "physics_agent" / "data" / "rid999").mkdir(parents=True)
    (storage_dir / "test_u" / "physics_agent" / "data" / "rid999" / "f.txt").write_text("x", encoding="utf-8")
    from backend.memu_client import MemUClient
    client = MemUClient(api_key="", user_id="test_u", agent_id="physics_agent", db_path=db_path, storage_dir=storage_dir)
    record = {
        "record_id": "rid999", "task_id": "", "scene": "data", "original_path": "data/rid999", "file_name": "f.txt",
        "simplified_path": "", "description": "test", "user_input": "", "user_id": "test_u", "agent_id": "physics_agent",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
    }
    log.log_input("insert_record(record)", record)
    client.insert_record(record)
    log.log_db_or_storage("insert_record", "ok")
    lst = client.list_records(user_id="test_u", agent_id="physics_agent")
    log.log_output("list_records 含 rid999", any(r.get("record_id") == "rid999" for r in lst))
    out = client.delete_record(record_id="rid999", user_id="test_u", agent_id="physics_agent", remove_from_storage=True)
    log.log_output("delete_record(...)", out)
    assert out.get("deleted") == 1
    log.close()


if __name__ == "__main__":
    test_memu_client_init_and_get_retrieve_config()
    test_memu_upload_files_and_list()
    test_memu_get_download_info_and_download_to_path()
    test_memu_match_and_resolve()
    test_memu_retrieve_by_agent_id()
    test_memu_insert_record_and_delete()
    print("test_memu_client_api.py done.")
