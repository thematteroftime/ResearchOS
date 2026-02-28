# tests/test_app_backend_api.py
"""
backend/app_backend.py 各 API 的测试：ensure_env、get_venue_formats、get_project_types、normalize_query、
intent_to_agent_ids、list_agent_ids、get_agent_task_config、memu_upload_files、memu_match_and_resolve、
memu_list_records、paper_ingest_pdf、parameter_recommendation、project_proposal_optimize、revise_paper 等。
每步打印并写入 tests/logs/test_app_backend_api_*.log
"""

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env", override=True)
except ImportError:
    pass

from tests.test_utils import DebugLogger, LOG_DIR, create_app_backend_for_test, get_docs_path


def test_app_backend_ensure_env():
    """测试 ensure_env 返回完整键。"""
    log = DebugLogger("test_app_ensure_env", subdir=str(LOG_DIR))
    app = create_app_backend_for_test()
    log.log_input("调用", "ensure_env()")
    out = app.ensure_env()
    log.log_output("ensure_env()", out)
    assert "anthropic_configured" in out and "memu_configured" in out
    log.close()


def test_app_backend_get_venue_formats_get_project_types():
    """测试 get_venue_formats、get_project_types。"""
    log = DebugLogger("test_app_venue_types", subdir=str(LOG_DIR))
    app = create_app_backend_for_test()
    log.log_input("get_venue_formats()", "")
    venues = app.get_venue_formats()
    log.log_output("get_venue_formats()", {"count": len(venues), "first": venues[0] if venues else None})
    log.log_input("get_project_types()", "")
    types = app.get_project_types()
    log.log_output("get_project_types()", {"count": len(types), "first": types[0] if types else None})
    assert len(venues) >= 1 and len(types) >= 1
    log.close()


def test_app_backend_normalize_query():
    """测试 normalize_query。"""
    log = DebugLogger("test_app_normalize", subdir=str(LOG_DIR))
    app = create_app_backend_for_test()
    log.log_input("raw_input", "量子计算")
    log.log_input("venue_id", "nature")
    log.log_input("project_type_id", "paper")
    out = app.normalize_query(raw_input="量子计算", venue_id="nature", project_type_id="paper", data_file_names=[])
    log.log_output("normalize_query(...)", out)
    assert "query" in out
    log.close()


def test_app_backend_intent_to_agent_ids():
    """测试 intent_to_agent_ids。"""
    log = DebugLogger("test_app_intent", subdir=str(LOG_DIR))
    app = create_app_backend_for_test()
    log.log_input("input_text", "复杂等离子体")
    ids = app.intent_to_agent_ids(input_text="复杂等离子体")
    log.log_output("intent_to_agent_ids(...)", ids)
    assert isinstance(ids, list)
    log.close()


def test_app_backend_list_agent_ids_get_agent_task_config():
    """测试 list_agent_ids、get_agent_task_config。"""
    log = DebugLogger("test_app_agent_config", subdir=str(LOG_DIR))
    app = create_app_backend_for_test()
    log.log_input("list_agent_ids()", "")
    ids = app.list_agent_ids()
    log.log_output("list_agent_ids()", ids)
    log.log_input("get_agent_task_config(physics_agent, paper_ingest)", "")
    cfg = app.get_agent_task_config("physics_agent", "paper_ingest")
    log.log_output("get_agent_task_config(...)", cfg)
    assert isinstance(cfg, dict)
    log.close()


def test_app_backend_memu_upload_and_list_and_match():
    """测试 memu_upload_files（使用 docs/FH_data.csv）、memu_list_records、memu_match_and_resolve。"""
    log = DebugLogger("test_app_memu_upload_list_match", subdir=str(LOG_DIR))
    csv_path = get_docs_path("FH_data.csv")
    if not csv_path.exists():
        tmp = Path(tempfile.mkdtemp())
        (tmp / "d.csv").write_text("a,b\n1,2", encoding="utf-8")
        csv_path = tmp / "d.csv"
    log.log_file_used("上传文件", str(csv_path), csv_path.exists())
    app = create_app_backend_for_test(user_id="test_app_u", agent_id="physics_agent")
    log.log_input("file_paths", [str(csv_path)])
    log.log_input("scene", "data")
    log.log_input("user_input", "测试上传")
    up = app.memu_upload_files(file_paths=[str(csv_path)], scene="data", user_input="测试上传", user_id="test_app_u", agent_id="physics_agent", wait=False)
    log.log_output("memu_upload_files(...)", up)
    log.log_db_or_storage("上传后 record_ids", str(up.get("record_ids")))
    lst = app.memu_list_records(user_id="test_app_u", agent_id="physics_agent", limit=5)
    log.log_output("memu_list_records(...)", {"count": len(lst)})
    match = app.memu_match_and_resolve(query="数据", user_id="test_app_u", agent_id="physics_agent", limit=5)
    log.log_output("memu_match_and_resolve(...)", {"matched_record_ids": match.get("matched_record_ids"), "records_count": len(match.get("records", []))})
    log.close()


def test_app_backend_paper_ingest_pdf_invalid_path():
    """测试 paper_ingest_pdf 对不存在路径返回 error。"""
    log = DebugLogger("test_app_paper_ingest_invalid", subdir=str(LOG_DIR))
    app = create_app_backend_for_test()
    log.log_input("file_path", "/nonexistent.pdf")
    log.log_input("user_id", "test_u")
    out = app.paper_ingest_pdf(file_path="/nonexistent.pdf", user_id="test_u")
    log.log_output("paper_ingest_pdf(...)", out)
    assert out.get("error") == "文件不存在"
    log.close()


def test_app_backend_parameter_recommendation():
    """测试 parameter_recommendation 使用假 structured_paper；打印 agent_id_used；无 error 时验证存储（summary.md、recommendations.json）。"""
    log = DebugLogger("test_app_param_rec", subdir=str(LOG_DIR))
    app = create_app_backend_for_test(user_id="test_param_rec_u", agent_id="physics_agent")
    structured = {"metadata": {"title": "T"}, "observed_phenomena": "现象", "simulation_results_description": "模拟", "parameters": [], "force_fields": []}
    params = {"expected_phenomena": "链状结构", "kappa": "参数"}
    log.log_input("structured_paper", structured)
    log.log_input("user_params", params)
    out = app.parameter_recommendation(structured_paper=structured, user_params=params, user_id="test_param_rec_u")
    log.log_output("parameter_recommendation(...)", out)
    log.log_step("agent_id_used", out.get("agent_id_used", "N/A"))
    assert "parameter_recommendations" in out or "error" in out

    # 无 error 时检查 parameter_recommendation 场景的存储与 get_download_info
    if not out.get("error"):
        recs = app.memu_list_records(user_id="test_param_rec_u", agent_id="physics_agent", scene="parameter_recommendation", limit=5)
        log.log_output("memu_list_records(scene=parameter_recommendation)", {"count": len(recs)})
        if recs:
            rid = recs[0].get("record_id")
            info = app.memu_get_download_info(record_id=rid, user_id="test_param_rec_u", agent_id="physics_agent")
            log.log_output("memu_get_download_info(parameter_recommendation)", info)
            assert info.get("scene") == "parameter_recommendation"
            assert info.get("summary_md_path") or info.get("recommendations_json_path"), "应有 summary.md 或 recommendations.json 路径"
    log.close()


def test_app_backend_project_proposal_optimize():
    """测试 project_proposal_optimize 占位；意图识别决定 agent，可打印 agent_ids。"""
    log = DebugLogger("test_app_project_proposal", subdir=str(LOG_DIR))
    app = create_app_backend_for_test()
    log.log_input("user_idea", "复杂等离子体项目")
    out = app.project_proposal_optimize(user_idea="复杂等离子体项目", user_id=app.memu.user_id)
    log.log_output("project_proposal_optimize(...)", out)
    # 显式传 agent_ids 时可在调用前打印
    out2 = app.project_proposal_optimize(user_idea="机器学习算法优化", user_id=app.memu.user_id, agent_ids=["cs_agent"])
    log.log_output("project_proposal_optimize(agent_ids=[cs_agent])", out2)
    assert "status" in out
    log.close()


def test_app_backend_memu_retrieve():
    """测试 memu_retrieve（retrieve 接口）；打印所用 agent_id。"""
    log = DebugLogger("test_app_memu_retrieve", subdir=str(LOG_DIR))
    app = create_app_backend_for_test()
    for aid in ("physics_agent", "cs_agent", "_default"):
        out = app.memu_retrieve(query="test query", user_id=app.memu.user_id, agent_id=aid)
        log.log_step("memu_retrieve(agent_id=%s)" % aid, "keys=%s" % (list(out.keys()) if isinstance(out, dict) else type(out)))
        log.log_output("memu_retrieve(agent_id=%s)" % aid, out if isinstance(out, dict) and out.get("error") else {"has_error": out.get("error") if isinstance(out, dict) else None})
    log.close()


def test_app_backend_revise_paper():
    """测试 revise_paper 占位。"""
    log = DebugLogger("test_app_revise", subdir=str(LOG_DIR))
    app = create_app_backend_for_test()
    log.log_input("existing_tex_path", "/path/to.tex")
    log.log_input("instruction", "修改摘要")
    out = app.revise_paper(existing_tex_path="/path/to.tex", instruction="修改摘要")
    log.log_output("revise_paper(...)", out)
    assert out.get("status") == "not_implemented"
    log.close()


def test_app_backend_writing_event_storage():
    """测试 register_writing_event 在提供 output_directory 时复制 PDF、SUMMARY.md、PEER_REVIEW.md 到 memU 存储。"""
    log = DebugLogger("test_app_writing_event_storage", subdir=str(LOG_DIR))
    app = create_app_backend_for_test(user_id="test_writing_u", agent_id="physics_agent")
    with tempfile.TemporaryDirectory() as tmp:
        job_dir = Path(tmp)
        (job_dir / "final").mkdir()
        (job_dir / "final" / "dummy.pdf").write_bytes(b"%PDF-1.4 dummy")
        (job_dir / "SUMMARY.md").write_text("# Summary\nTest.", encoding="utf-8")
        (job_dir / "PEER_REVIEW.md").write_text("# Peer Review\nTest.", encoding="utf-8")
        out = app.memu_register_writing_event(
            job_id="test_job_1",
            query="Create a Nature paper on X",
            data_files=[],
            output_pdf=str(job_dir / "final" / "dummy.pdf"),
            output_directory=str(job_dir),
            user_id="test_writing_u",
            agent_id="physics_agent",
        )
    log.log_output("memu_register_writing_event", out)
    assert not out.get("error") or out.get("record_id")
    rid = out.get("record_id")
    if rid:
        info = app.memu_get_download_info(record_id=rid, user_id="test_writing_u", agent_id="physics_agent")
        log.log_output("memu_get_download_info(writing_event)", info)
        assert info.get("scene") == "writing_event"
        assert info.get("resolved_storage_folder"), "应有 resolved_storage_folder"
        assert info.get("summary_md_path") or info.get("peer_review_md_path") or info.get("resolved_primary_path")
    log.close()


def test_memu_build_storage_path():
    """测试统一存储路径规范 build_storage_path。"""
    from backend.memu_client import build_storage_path
    p = build_storage_path(Path("/storage"), "u1", "a1", "paper", "r123")
    assert "u1" in str(p) and "a1" in str(p) and "paper" in str(p) and "r123" in str(p)
    assert p.name == "r123"
    assert p.parent.name == "paper"


if __name__ == "__main__":
    test_app_backend_ensure_env()
    test_app_backend_get_venue_formats_get_project_types()
    test_app_backend_normalize_query()
    test_app_backend_memu_retrieve()
    test_app_backend_intent_to_agent_ids()
    test_app_backend_list_agent_ids_get_agent_task_config()
    test_app_backend_memu_upload_and_list_and_match()
    test_app_backend_paper_ingest_pdf_invalid_path()
    test_app_backend_parameter_recommendation()
    test_app_backend_project_proposal_optimize()
    test_app_backend_revise_paper()
    test_app_backend_writing_event_storage()
    test_memu_build_storage_path()
    print("test_app_backend_api.py done.")
