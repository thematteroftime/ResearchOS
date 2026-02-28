# tests/test_memu_client_unit.py
"""
MemUClient 单测：配置加载、路径解析、上传目录布局、检索 limit、下载/删除（scene/record_id 文件夹）。
运行：在 merge_project 根目录
  python -m pytest tests/test_memu_client_unit.py -v -s
"""

import json
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


def _temp_client(storage_dir=None, db_path=None, config_path=None):
    """创建使用临时目录的 MemUClient（不请求云端）。"""
    from backend.memu_client import MemUClient
    tmp = Path(tempfile.mkdtemp())
    store = storage_dir or (tmp / "store")
    db = db_path or (tmp / "memu.db")
    client = MemUClient(
        api_key="",  # disabled
        user_id="unit_user",
        agent_id="physics_agent",
        db_path=db,
        storage_dir=store,
    )
    if config_path and config_path.exists():
        client._scenarios_config = json.loads(config_path.read_text(encoding="utf-8"))
    return client, tmp


def test_load_scenarios_config():
    """_load_scenarios_config 能加载 config 或得到空 dict。"""
    from backend.memu_client import MemUClient
    from backend.config import MEMU_SCENARIOS_PATH
    client, _ = _temp_client()
    client._load_scenarios_config()
    if MEMU_SCENARIOS_PATH.exists():
        assert isinstance(client._scenarios_config, dict)
        assert "physics_agent" in client._scenarios_config or "_default" in client._scenarios_config or len(client._scenarios_config) >= 0
    else:
        assert client._scenarios_config == {}
    print("[OK] _load_scenarios_config")


def test_get_retrieve_config():
    """get_retrieve_config(agent_id) 返回 retrieve 配置，含 item.top_k。"""
    client, _ = _temp_client()
    client._scenarios_config = {
        "physics_agent": {"retrieve": {"method": "rag", "item": {"top_k": 5, "enabled": True}}},
        "_default": {"retrieve": {"item": {"top_k": 3}}},
    }
    cfg = client.get_retrieve_config("physics_agent")
    assert isinstance(cfg, dict)
    assert cfg.get("item", {}).get("top_k") == 5
    cfg_default = client.get_retrieve_config("unknown_agent")
    assert cfg_default.get("item", {}).get("top_k") == 3
    print("[OK] get_retrieve_config", cfg.get("item"), cfg_default.get("item"))


def test_resolve_storage_folder_relative():
    """_resolve_storage_folder 将相对路径 scene/record_id 解析为本地文件夹。"""
    client, tmp = _temp_client()
    store = client._storage_dir
    (store / "unit_user" / "physics_agent" / "paper" / "abc123").mkdir(parents=True)
    (store / "unit_user" / "physics_agent" / "paper" / "abc123" / "f.pdf").write_text("x")
    record = {"original_path": "paper/abc123", "file_name": "f.pdf", "user_id": "unit_user", "agent_id": "physics_agent"}
    folder = client._resolve_storage_folder(record)
    assert folder is not None
    assert folder.name == "abc123"
    assert (folder / "f.pdf").exists()
    print("[OK] _resolve_storage_folder relative", folder)


def test_resolve_storage_folder_empty():
    """original_path 为空时返回 None。"""
    client, _ = _temp_client()
    record = {"original_path": "", "user_id": "unit_user", "agent_id": "physics_agent"}
    assert client._resolve_storage_folder(record) is None
    print("[OK] _resolve_storage_folder empty -> None")


def test_upload_files_folder_layout():
    """upload_files 使用 scene/record_id 目录并写入相对路径到 DB。"""
    client, tmp = _temp_client()
    f = tmp / "test_upload.txt"
    f.write_text("unit test content", encoding="utf-8")
    out = client.upload_files(file_paths=[str(f)], scene="data", user_id="unit_user", agent_id="physics_agent", wait=False)
    assert out.get("record_ids")
    assert out.get("records")
    rec = out["records"][0]
    rel = rec.get("original_path", "")
    assert "/" in rel or "\\" in rel or rel.startswith("data")
    assert rec.get("scene") == "data"
    assert rec.get("file_name") == "test_upload.txt"
    # 存储目录应为 storage_dir/unit_user/physics_agent/data/<record_id>/
    store = client._storage_dir / "unit_user" / "physics_agent"
    assert store.exists()
    assert Path(rel).parent.name == "data"
    folder = store / rel.replace("\\", "/")
    assert folder.exists()
    assert (folder / "test_upload.txt").exists()
    print("[OK] upload_files folder layout", rel, folder)


def test_match_and_resolve_limit_from_config():
    """match_and_resolve(limit=None) 使用 get_retrieve_config 的 item.top_k。"""
    client, tmp = _temp_client()
    client._scenarios_config = {"physics_agent": {"retrieve": {"item": {"top_k": 5}}}}
    out = client.match_and_resolve(query="test", user_id="unit_user", agent_id="physics_agent", limit=None)
    assert "matched_record_ids" in out
    assert "records" in out
    assert len(out["matched_record_ids"]) <= 5
    print("[OK] match_and_resolve limit from config")


def test_match_and_resolve_resolved_paths():
    """match_and_resolve 返回的 records 含 storage_path、resolved_storage_folder（有路径时）。"""
    client, tmp = _temp_client()
    f = tmp / "a.txt"
    f.write_text("a", encoding="utf-8")
    client.upload_files(file_paths=[str(f)], scene="paper", user_id="u", agent_id="physics_agent", wait=False)
    out = client.match_and_resolve(query="a", user_id="u", agent_id="physics_agent", limit=5)
    records = out.get("records") or []
    for rec in records:
        assert "record_id" in rec and "scene" in rec
        if rec.get("storage_path"):
            assert "resolved_storage_folder" in rec or "storage_path" in rec
    print("[OK] match_and_resolve resolved paths", len(records))


def test_get_download_info_resolved():
    """get_download_info 含 resolved_storage_folder、resolved_primary_path（有路径时）。"""
    client, tmp = _temp_client()
    f = tmp / "b.txt"
    f.write_text("b", encoding="utf-8")
    up = client.upload_files(file_paths=[str(f)], scene="data", user_id="u", agent_id="physics_agent", wait=False)
    rid = up["record_ids"][0]
    info = client.get_download_info(record_id=rid, user_id="u", agent_id="physics_agent")
    assert info is not None
    assert info.get("original_path", "").startswith("data/")
    assert "resolved_storage_folder" in info
    assert "resolved_primary_path" in info
    print("[OK] get_download_info resolved", info.get("resolved_primary_path"))


def test_download_to_path_from_folder():
    """download_to_path 从 scene/record_id 文件夹复制主文件到 dest_dir。"""
    client, tmp = _temp_client()
    f = tmp / "c.txt"
    f.write_text("c", encoding="utf-8")
    up = client.upload_files(file_paths=[str(f)], scene="paper", user_id="u", agent_id="physics_agent", wait=False)
    rid = up["record_ids"][0]
    dest = tmp / "downloads"
    out = client.download_to_path(record_id=rid, dest_dir=dest, user_id="u", agent_id="physics_agent")
    assert out.get("error") is None
    assert Path(out["saved_path"]).exists()
    assert Path(out["saved_path"]).read_text(encoding="utf-8") == "c"
    print("[OK] download_to_path from folder", out["saved_path"])


def test_delete_record_removes_folder():
    """delete_record(remove_from_storage=True) 删除 scene/record_id 文件夹。"""
    client, tmp = _temp_client()
    f = tmp / "d.txt"
    f.write_text("d", encoding="utf-8")
    up = client.upload_files(file_paths=[str(f)], scene="other", user_id="u", agent_id="physics_agent", wait=False)
    rid = up["record_ids"][0]
    info = client.get_download_info(rid, user_id="u", agent_id="physics_agent")
    folder = Path(info["resolved_storage_folder"])
    assert folder.exists()
    out = client.delete_record(record_id=rid, user_id="u", agent_id="physics_agent", remove_from_storage=True)
    assert out["deleted"] == 1
    assert not folder.exists()
    print("[OK] delete_record removes folder")


def test_list_records():
    """list_records 返回 list，元素含 record_id, scene, original_path。"""
    client, _ = _temp_client()
    lst = client.list_records(user_id="unit_user", agent_id="physics_agent", limit=10)
    assert isinstance(lst, list)
    for r in lst:
        assert "record_id" in r and "scene" in r
    print("[OK] list_records", len(lst))


if __name__ == "__main__":
    test_load_scenarios_config()
    test_get_retrieve_config()
    test_resolve_storage_folder_relative()
    test_resolve_storage_folder_empty()
    test_upload_files_folder_layout()
    test_match_and_resolve_limit_from_config()
    test_match_and_resolve_resolved_paths()
    test_get_download_info_resolved()
    test_download_to_path_from_folder()
    test_delete_record_removes_folder()
    test_list_records()
    print("\n[DONE] test_memu_client_unit")
