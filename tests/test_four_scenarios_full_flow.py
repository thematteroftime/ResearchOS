# tests/test_four_scenarios_full_flow.py
"""
四场景全流程测试（final_project DESIGN_ARCHITECTURE 对应）：
  场景一：论文上传分析 — 输入 PDF+用户问题 → 输出 JSON+Markdown；skip_formula_verify=True 避免卡壳
  场景二：论文写作 — 输入 数据+用户输入 → 输出 PDF 供前端展示
  场景三：参数推荐 — 输入 期望现象+参数名含义单位 → 输出 数值区间[1,2]+原因+力场等
  场景四：记忆查询 — 用户问题 → retrieve + match_and_resolve → 可下载列表

使用 get_test_db_and_storage() 统一测试 DB（memu_test.db + memu_storage_test）。
运行：python tests/test_four_scenarios_full_flow.py 或 pytest tests/test_four_scenarios_full_flow.py -v -s
"""

import asyncio
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

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

# 测试用独立 DB/存储，避免污染默认库
TEST_USER_ID = "four_scenarios_test_user"
TEST_AGENT_ID = "physics_agent"


def _log_step(log: DebugLogger, step: str, name: str, detail: str = "", data: Any = None) -> None:
    log.log_step(f"{step} | {name}", detail, data=data)


def _load_user_questions_examples() -> List[str]:
    p = get_docs_path("user_questions_examples.txt")
    if not p.exists():
        return []
    lines = [ln.strip() for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip() and not ln.strip().startswith("#")]
    return lines


def run_four_scenarios_sequential(
    use_test_db: bool = True,
    pdf_path_override: Optional[str] = None,
    skip_writing_generation: bool = True,
) -> Dict[str, Any]:
    """
    按顺序执行四场景，每步验证并写日志。
    - use_test_db: 使用独立测试 DB/存储（推荐 True）
    - pdf_path_override: 若指定则用该路径做论文入库，否则在 docs 下查找 sample_*.pdf
    - skip_writing_generation: 不真正调用 generate_paper（仅规范化 query + list_jobs），避免长时间/费用
    """
    ts = time.strftime("%Y%m%d_%H%M%S", time.localtime())
    log = DebugLogger("four_scenarios", subdir=str(LOG_DIR))
    log._write(f"[全流程] 四场景测试开始 | user_id={TEST_USER_ID} | ts={ts}")
    log._write("=" * 60)

    from backend.app_backend import AppBackend

    # 使用统一测试 DB/存储
    if use_test_db:
        test_db, test_storage = get_test_db_and_storage()
    else:
        from backend.config import MEMU_DB, MEMU_STORAGE_DIR
        test_db, test_storage = MEMU_DB, MEMU_STORAGE_DIR

    app = AppBackend(
        memu_user_id=TEST_USER_ID,
        memu_agent_id=TEST_AGENT_ID,
        memu_db_path=test_db,
        memu_storage_dir=test_storage,
    )

    summary: Dict[str, Any] = {"scenario1": {}, "scenario2": {}, "scenario3": {}, "scenario4": {}, "env_ok": False, "errors": []}

    # ---------- Step 0: 环境与配置校验 ----------
    _log_step(log, "Step0", "ensure_env", "检查环境变量与写作/memU/论文提取配置")
    env_status = app.ensure_env()
    log.log_output("ensure_env", env_status)
    summary["env_ok"] = env_status.get("anthropic_configured", False) or env_status.get("message") == "OK"
    agent_ids = app.list_agent_ids()
    log.log_output("list_agent_ids", agent_ids)
    assert isinstance(agent_ids, list), "list_agent_ids 应返回 list"
    _log_step(log, "Step0", "get_agent_task_config(physics_agent, paper_ingest)", "", data=app.get_agent_task_config("physics_agent", "paper_ingest"))

    # ---------- Step 1: 意图识别（多 agent 验证）----------
    _log_step(log, "Step1", "意图识别", "对多条用户问题/文件名调用 intent_to_agent_ids")
    questions = _load_user_questions_examples()
    if not questions:
        questions = ["等离子体链状结构", "反应动力学参数", "细胞迁移", "机器学习超参数", "偏微分方程稳定性", "FH_data.csv"]
    intent_results: List[Dict[str, Any]] = []
    for q in questions[:8]:
        ids = app.intent_to_agent_ids(input_text=q, file_name=q if "." in q else None)
        intent_results.append({"input": q[:80], "agent_ids": ids})
        log.log_step("intent", f"input={q[:60]}... -> agent_ids={ids}")
    log.log_output("intent_results", intent_results)
    summary["scenario1"]["intent_results"] = intent_results
    summary["scenario1"]["intent_count"] = len(intent_results)

    # ---------- Step 2: 场景一 — 上传 + 论文入库（可选 PDF）----------
    _log_step(log, "Step2", "场景一", "数据上传 + 若有 PDF 则论文提取 + 记忆 + DB")
    csv_path = get_docs_path("FH_data.csv")
    txt_path = get_docs_path("prompt.txt")
    file_paths = []
    if csv_path.exists():
        file_paths.append(str(csv_path))
    if txt_path.exists():
        file_paths.append(str(txt_path))
    if not file_paths:
        import tempfile
        t = Path(tempfile.mkdtemp())
        f = t / "dummy.csv"
        f.write_text("a,b\n1,2", encoding="utf-8")
        file_paths = [str(f)]
    log.log_input("上传文件", file_paths)
    up = app.memu_upload_files(
        file_paths=file_paths,
        scene="data",
        user_input="全流程测试：数据与说明",
        user_id=TEST_USER_ID,
        agent_id=TEST_AGENT_ID,
        wait=False,
    )
    log.log_output("memu_upload_files", up)
    summary["scenario1"]["upload"] = {"record_ids": up.get("record_ids"), "error": up.get("error")}
    assert up.get("record_ids") or up.get("error") is not None, "上传应返回 record_ids 或 error"

    pdf_to_ingest = pdf_path_override
    if not pdf_to_ingest:
        for name in ["2601.00062v1.pdf", "sample_physics.pdf", "sample_chemistry.pdf", "sample.pdf"]:
            cand = get_docs_path(name)
            if cand.exists():
                pdf_to_ingest = str(cand)
                break
    if pdf_to_ingest:
        _log_step(log, "Step2", "paper_ingest_pdf", f"file_path={pdf_to_ingest}")
        ingest = app.paper_ingest_pdf(
            file_path=pdf_to_ingest,
            user_id=TEST_USER_ID,
            agent_ids=None,
            user_input="关注参数与创新点",
        )
        log.log_output("paper_ingest_pdf", ingest)
        summary["scenario1"]["paper_ingest"] = {"agent_ids": ingest.get("agent_ids"), "results_count": len(ingest.get("results", [])), "error": ingest.get("error")}

        # 2.1 场景一完整管线：调用 AppBackend.paper_analysis_scenario（PDF + 用户疑问，三线程 + 文献扩展）
        user_q = "这篇论文中宏观自旋系统出现混沌、准周期和周期行为的条件分别是什么？我特别关心与 Lyapunov 指数 λ_max 和驱动参数的关系。"
        log.log_input("场景一输入_file_path", pdf_to_ingest, "场景一输入")
        log.log_input("场景一输入_user_question", user_q, "场景一输入")
        _log_step(log, "Step2A", "paper_analysis_scenario", "使用 AppBackend.paper_analysis_scenario 运行三线程 + 文献扩展")
        analysis = app.paper_analysis_scenario(
            file_path=pdf_to_ingest,
            user_question=user_q,
            user_id=TEST_USER_ID,
            agent_ids=None,
            log_step=lambda step, msg, data=None: log.log_step(f"paper_analysis|{step}", msg, data),
            skip_formula_verify=True,
        )
        markdown_summary = analysis.get("markdown_summary") or ""
        if markdown_summary:
            md_path = log.save_markdown("paper_analysis_scenario", markdown_summary)
            log.log_step("场景一输出", f"Markdown 已保存至 {md_path}", data={"markdown_len": len(markdown_summary)})
        log.log_output("场景一输出_keys", list(analysis.keys()))
        summary["scenario1"]["paper_analysis"] = {
            "agent_ids": analysis.get("agent_ids"),
            "has_markdown_summary": bool(markdown_summary),
        }
    else:
        _log_step(log, "Step2", "paper_ingest_pdf", "未找到 docs 下 PDF，跳过真实提取；验证错误路径")
        no_file = app.paper_ingest_pdf(file_path="/nonexistent.pdf", user_id=TEST_USER_ID, agent_ids=["physics_agent"])
        log.log_output("paper_ingest_pdf(无效路径)", no_file)
        assert no_file.get("error") == "文件不存在"
        summary["scenario1"]["paper_ingest"] = "skipped_no_pdf"

    # ---------- Step 3: 场景三 — 参数推荐 ----------
    _log_step(log, "Step3", "场景三", "参数推荐：期待现象 + 待模拟参数，验证记忆与 API")
    log.log_input("场景三输入_structured_paper(keys)", ["metadata", "observed_phenomena", "simulation_results_description", "methodology", "keywords", "parameters"])
    log.log_input("场景三输入_user_params", {"expected_phenomena": "链状结构形成", "kappa": "屏蔽参数，单位 1"})
    minimal_paper = {
        "metadata": {"title": "Test paper for param rec", "journal": "J", "year": "2024", "innovation": "test"},
        "observed_phenomena": "链状结构形成",
        "simulation_results_description": "MD 模拟",
        "methodology": "Yukawa 势",
        "keywords": ["plasma", "dust"],
        "parameters": [{"name": "kappa", "symbol": "κ", "value": "2", "unit": "1", "meaning": "screening"}],
    }
    user_params = {"expected_phenomena": "链状结构形成", "kappa": "屏蔽参数，单位 1"}
    log.log_input("structured_paper(keys)", list(minimal_paper.keys()))
    log.log_input("user_params", user_params)
    param_out = app.parameter_recommendation(
        structured_paper=minimal_paper,
        user_params=user_params,
        user_id=TEST_USER_ID,
        agent_id=TEST_AGENT_ID,
    )
    log.log_output("场景三输出", param_out)
    summary["scenario3"] = {"parameter_recommendations": param_out.get("parameter_recommendations"), "error": param_out.get("error"), "agent_id_used": param_out.get("agent_id_used")}
    assert "parameter_recommendations" in param_out or "error" in param_out, "参数推荐应返回 parameter_recommendations 或 error"

    # ---------- Step 4: 场景二 — 写作（规范化 query + 可选 list_jobs）----------
    _log_step(log, "Step4", "场景二", "短 query 规范化 + 记忆增强；可选 list_jobs（不真正生成 PDF）")
    short_query = "A short note on dust particle chain formation in complex plasma."
    norm = app.normalize_query(
        raw_input=short_query,
        venue_id="nature",
        project_type_id="paper",
        data_file_names=[],
        user_id=TEST_USER_ID,
        agent_id=TEST_AGENT_ID,
    )
    log.log_output("normalize_query", norm)
    summary["scenario2"]["normalize_query"] = {"query_len": len(norm.get("query", "")), "source": norm.get("source"), "error": norm.get("error")}
    jobs = app.list_jobs(limit=5)
    log.log_output("list_jobs", jobs)
    summary["scenario2"]["list_jobs_count"] = len(jobs) if isinstance(jobs, list) else 0
    job_status = app.get_job_status("test-nonexistent-id")
    log.log_output("get_job_status(test-nonexistent-id)", job_status)

    # ---------- Step 5: 场景四 — 记忆与源文件查询 ----------
    _log_step(log, "Step5", "场景四", "用户问题 → memU retrieve + match_and_resolve → 可下载列表")
    query = "数据 或 等离子 或 FH_data"
    raw_retrieve = app.memu_retrieve(query=query, user_id=TEST_USER_ID, agent_id=TEST_AGENT_ID)
    log.log_output("memu_retrieve(原始检索)", {"keys": list(raw_retrieve.keys()) if isinstance(raw_retrieve, dict) else type(raw_retrieve).__name__, "error": raw_retrieve.get("error") if isinstance(raw_retrieve, dict) else None})
    match = app.memu_match_and_resolve(
        query=query,
        user_id=TEST_USER_ID,
        agent_id=TEST_AGENT_ID,
        limit=5,
    )
    log.log_output("memu_match_and_resolve", {"matched_record_ids": match.get("matched_record_ids"), "records_count": len(match.get("records", []))})
    for r in (match.get("records") or [])[:5]:
        log.log_step("record", f"record_id={r.get('record_id')} scene={r.get('scene')} storage_path={r.get('storage_path')}")
    summary["scenario4"] = {"matched_record_ids": match.get("matched_record_ids"), "records_count": len(match.get("records", []))}
    list_rec = app.memu_list_records(user_id=TEST_USER_ID, agent_id=TEST_AGENT_ID, limit=10)
    log.log_output("memu_list_records", {"count": len(list_rec), "sample_record_ids": [x.get("record_id") for x in list_rec[:3]]})

    log._write("=" * 60)
    log._write("[全流程] 四场景测试结束")
    log._write(f"[输出目录] Markdown 等输出文件: {LOG_DIR / 'outputs'}")
    log.log_output("summary", summary)
    log.close()
    return summary


def test_four_scenarios_run():
    """Pytest 入口：执行四场景并做最小断言。"""
    summary = run_four_scenarios_sequential(use_test_db=True, skip_writing_generation=True)
    assert "scenario1" in summary and "scenario3" in summary and "scenario4" in summary
    assert summary.get("scenario1", {}).get("intent_count", 0) >= 1
    assert "parameter_recommendations" in summary.get("scenario3", {}) or "error" in summary.get("scenario3", {})


if __name__ == "__main__":
    summary = run_four_scenarios_sequential(use_test_db=True, skip_writing_generation=True)
    print("\n四场景全流程测试完成。")
    print("日志目录:", LOG_DIR)
    print("Markdown 输出目录:", LOG_DIR / "outputs")
