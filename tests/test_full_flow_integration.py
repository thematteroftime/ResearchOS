# tests/test_full_flow_integration.py
"""
全流程集成测试 + 前端调用场景测试。
- 汇总运行各模块测试，并将整体数据流动打印与写入 tests/logs/full_flow_*.log
- 前端场景：写入的记录先打印再上传；下发的记录也打印
- 一键运行：run_all_tests()
"""

import sys
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
try:
    from tests.test_utils import get_test_db_and_storage
except ImportError:
    def get_test_db_and_storage():
        from backend.config import MEMU_TEST_DB, MEMU_TEST_STORAGE
        MEMU_TEST_STORAGE.mkdir(parents=True, exist_ok=True)
        return MEMU_TEST_DB, MEMU_TEST_STORAGE


def run_all_module_tests():
    """按顺序运行各模块测试，并写入汇总日志。"""
    ts = time.strftime("%Y%m%d_%H%M%S", time.localtime())
    log_path = LOG_DIR / f"full_flow_{ts}.log"
    log_file = open(log_path, "w", encoding="utf-8")

    def write(msg: str) -> None:
        log_file.write(msg + "\n")
        log_file.flush()
        print(msg)

    write("=" * 60)
    write("[全流程集成测试] 开始 run_all_module_tests")
    write("=" * 60)

    modules = [
        ("test_config", ["test_project_paths", "test_get_env", "test_venue_formats_and_project_types"]),
        ("test_agent_config", ["test_load_scenarios", "test_get_task_config", "test_get_prompt", "test_get_memorize_override_config", "test_intent_to_agent_ids", "test_get_parameter_recommendation_system_prompt", "test_cs_agent_prompts", "test_list_agent_ids"]),
        ("test_memu_client_api", ["test_memu_client_init_and_get_retrieve_config", "test_memu_upload_files_and_list", "test_memu_get_download_info_and_download_to_path", "test_memu_match_and_resolve", "test_memu_retrieve_by_agent_id", "test_memu_insert_record_and_delete"]),
        ("test_memu_oss_client_unit", ["test_oss_client_no_key_disabled", "test_oss_memorize_returns_error_when_disabled", "test_oss_retrieve_returns_error_when_disabled", "test_create_memu_client_oss_fallback_to_cloud"]),
        ("test_paper_ingest", ["test_extract_paper_structure_non_pdf", "test_paper_ingest_pdf_no_pdf_file", "test_paper_ingest_pdf_with_txt_skips_extraction", "test_paper_ingest_pdf_intent_driven_agent_ids"]),
        ("test_pdf_extract", ["test_extract_raw_with_pymupdf_no_file", "test_extract_raw_with_pymupdf_non_pdf", "test_extract_raw_with_pymupdf_real_pdf", "test_verify_formulas_with_llm_empty"]),
        ("test_parameter_recommendation", ["test_get_memory_context_for_agents", "test_run_parameter_recommendation", "test_run_parameter_recommendation_default_agent", "test_get_memory_context_multi_agent"]),
        ("test_scientific_writer_client", ["test_scientific_writer_ensure_env", "test_scientific_writer_normalize_query", "test_scientific_writer_list_jobs", "test_scientific_writer_get_job_status"]),
        ("test_app_backend_api", [
            "test_app_backend_ensure_env", "test_app_backend_get_venue_formats_get_project_types", "test_app_backend_normalize_query", "test_app_backend_memu_retrieve",
            "test_app_backend_intent_to_agent_ids", "test_app_backend_list_agent_ids_get_agent_task_config", "test_app_backend_memu_upload_and_list_and_match",
            "test_app_backend_paper_ingest_pdf_invalid_path", "test_app_backend_parameter_recommendation", "test_app_backend_project_proposal_optimize", "test_app_backend_revise_paper",
        ]),
    ]

    for mod_name, funcs in modules:
        write(f"\n--- 模块 {mod_name} ---")
        mod = __import__(f"tests.{mod_name}", fromlist=funcs)
        for fn in funcs:
            try:
                write(f"  运行 {fn} ...")
                getattr(mod, fn)()
                write(f"  [OK] {fn}")
            except Exception as e:
                write(f"  [FAIL] {fn}: {e}")
                import traceback
                write(traceback.format_exc())

    write("\n" + "=" * 60)
    write("[全流程集成测试] run_all_module_tests 结束")
    write("=" * 60)
    log_file.close()
    print(f"\n汇总日志已写入: {log_path}")


def test_frontend_scenario_upload_then_download():
    """
    前端调用场景：先构造要写入的记录/数据并打印 -> 上传 -> 再查询/下发并打印。
    使用 docs 下 CSV 与 TXT 作为测试数据。
    """
    log = DebugLogger("frontend_scenario_upload_download", subdir=str(LOG_DIR))
    from backend.app_backend import AppBackend
    from backend.config import DB_DIR

    log.log_step("场景", "1) 准备数据并打印 2) 上传 3) 查询/下发并打印")
    csv_path = get_docs_path("FH_data.csv")
    txt_path = get_docs_path("prompt.txt")
    if not csv_path.exists():
        import tempfile
        t = Path(tempfile.mkdtemp())
        csv_path = t / "d.csv"
        csv_path.write_text("a,b\n1,2", encoding="utf-8")
    log.log_file_used("待上传文件1", str(csv_path), csv_path.exists())
    log.log_input("待上传数据说明", "FH_data.csv 或占位 CSV")
    if txt_path.exists():
        log.log_file_used("待上传文件2", str(txt_path), True)
        log.log_input("待上传数据说明2", "prompt.txt 前200字")
        log.log_step("prompt.txt 内容预览", txt_path.read_text(encoding="utf-8")[:200])

    test_db, test_storage = get_test_db_and_storage()
    app = AppBackend(
        memu_user_id="frontend_user",
        memu_agent_id="physics_agent",
        memu_db_path=test_db,
        memu_storage_dir=test_storage,
    )

    file_paths = [str(csv_path)]
    if txt_path.exists():
        file_paths.append(str(txt_path))
    log.log_step("上传前打印", "即将上传: %s" % file_paths)
    up = app.memu_upload_files(file_paths=file_paths, scene="data", user_input="前端场景测试", user_id="frontend_user", agent_id="physics_agent", wait=False)
    log.log_output("上传结果(写入记录)", up)
    log.log_db_or_storage("DB 写入", "record_ids=%s" % up.get("record_ids"))

    log.log_step("下发前", "用户问题: 数据 或 等离子")
    match = app.memu_match_and_resolve(query="数据", user_id="frontend_user", agent_id="physics_agent", limit=5)
    log.log_output("下发/匹配结果", {"matched_record_ids": match.get("matched_record_ids"), "records_count": len(match.get("records", []))})
    for r in match.get("records", [])[:3]:
        log.log_step("下发的记录", "record_id=%s scene=%s storage_path=%s" % (r.get("record_id"), r.get("scene"), r.get("storage_path")))
    log.close()


def run_four_scenarios_test():
    """运行四场景全流程测试（final_project 四场景：论文分析/写作/参数推荐/记忆查询）。"""
    from tests.test_four_scenarios_full_flow import run_four_scenarios_sequential
    run_four_scenarios_sequential(use_test_db=True, skip_writing_generation=True)
    print("\n四场景全流程测试完成。日志目录: %s" % LOG_DIR)


def run_single_paper_full_flow_test():
    """运行单论文全流程验证（2601.00062v1.pdf 反推用户参数，四场景全流程）。"""
    from tests.test_single_paper_full_flow import run_single_paper_full_flow
    run_single_paper_full_flow(use_test_db=True, skip_writing_generation=True)
    print("\n单论文全流程验证完成。日志目录: %s" % LOG_DIR)


def run_real_papers_scenarios_test():
    """运行基于五篇真实论文的场景测试：按领域入库 + memU/DB 检查 + 写作 query + 检索。"""
    from tests.test_real_papers_scenarios import run_real_papers_scenarios
    run_real_papers_scenarios(use_test_db=True)
    print("\n真实论文场景测试完成。日志目录: %s" % LOG_DIR)


def run_all_tests():
    """一键运行：先全模块测试，再前端场景测试，四场景、单论文、真实论文全流程。"""
    print("开始一键全量测试...")
    run_all_module_tests()
    print("\n开始前端场景测试...")
    test_frontend_scenario_upload_then_download()
    print("\n开始四场景全流程测试...")
    run_four_scenarios_test()
    print("\n开始单论文全流程验证（2601.00062v1.pdf）...")
    run_single_paper_full_flow_test()
    print("\n开始真实论文场景测试...")
    run_real_papers_scenarios_test()
    print("\n一键测试完成。日志目录: %s" % LOG_DIR)


if __name__ == "__main__":
    run_all_tests()
