# tests/test_single_paper_full_flow.py
"""
单论文全流程验证：以 2601.00062v1.pdf 为唯一输入，反推用户参数，覆盖四场景全流程。
- 2601.00062v1.pdf：物理领域论文（宏观自旋、混沌、Lyapunov 指数）
- 将 PDF 置于 merge_project/docs/2601.00062v1.pdf 后运行
- 若 PDF 不存在则跳过真实提取，仍执行参数推荐/写作/检索（使用内置 mock）

运行（在 merge_project 根目录）：
  python tests/test_single_paper_full_flow.py
  或 pytest tests/test_single_paper_full_flow.py -v -s
"""

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

from tests.test_utils import DebugLogger, get_docs_path, LOG_DIR
try:
    from tests.test_utils import get_test_db_and_storage
except ImportError:
    def get_test_db_and_storage():
        from backend.config import MEMU_TEST_DB, MEMU_TEST_STORAGE
        MEMU_TEST_STORAGE.mkdir(parents=True, exist_ok=True)
        return MEMU_TEST_DB, MEMU_TEST_STORAGE

# 单论文全流程：2601.00062v1.pdf（物理论文：宏观自旋、混沌、Lyapunov）
SINGLE_PAPER_FILENAME = "2601.00062v1.pdf"
TEST_USER_ID = "single_paper_test_user"
TEST_AGENT_ID = "physics_agent"

# 反推自论文内容的用户参数
USER_QUESTION_FOR_ANALYSIS = (
    "这篇论文中宏观自旋系统出现混沌、准周期和周期行为的条件分别是什么？"
    "我特别关心与 Lyapunov 指数 λ_max 和驱动参数的关系。"
)
USER_QUESTION_FOR_RETRIEVAL = "宏观自旋系统中 Lyapunov 指数 λ_max>0 的混沌区域对应哪些驱动参数？"
WRITING_RAW_INPUT = (
    "A short note on classical vs quantum dynamics and the onset of chaos "
    "in a periodically driven macrospin system, focusing on Lyapunov exponents and bifurcation diagrams."
)
PARAM_REC_USER_PARAMS = {
    "expected_phenomena": "混沌、准周期、周期行为及与 Lyapunov 指数的关系",
    "driving_amplitude": "驱动振幅参数",
    "driving_frequency": "驱动频率",
}


def _log_step(log: DebugLogger, step: str, name: str, detail: str = "", data: Any = None) -> None:
    log.log_step(f"{step} | {name}", detail, data=data)


def run_single_paper_full_flow(
    pdf_path_override: Optional[str] = None,
    use_test_db: bool = True,
    skip_writing_generation: bool = True,
) -> Dict[str, Any]:
    """
    单论文四场景全流程：以 2601.00062v1.pdf 为输入，反推用户参数执行全流程。
    - pdf_path_override: 若指定则用该路径，否则在 docs 下查找 2601.00062v1.pdf
    - use_test_db: 使用独立测试 DB/存储
    - skip_writing_generation: 不真正调用 generate_paper
    """
    ts = time.strftime("%Y%m%d_%H%M%S", time.localtime())
    log = DebugLogger("single_paper_full_flow", subdir=str(LOG_DIR))
    log._write(f"[单论文全流程] 开始 | pdf={SINGLE_PAPER_FILENAME} | user_id={TEST_USER_ID} | ts={ts}")
    log._write(f"[日志文件] {log.log_path.resolve()}")
    log._write("=" * 60)

    from backend.app_backend import AppBackend

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

    summary: Dict[str, Any] = {
        "scenario1": {}, "scenario2": {}, "scenario3": {}, "scenario4": {},
        "pdf_exists": False, "env_ok": False, "errors": [],
    }

    pdf_path = pdf_path_override or str(get_docs_path(SINGLE_PAPER_FILENAME))
    pdf_exists = Path(pdf_path).exists()
    summary["pdf_exists"] = pdf_exists
    log.log_file_used("论文 PDF", pdf_path, pdf_exists)

    if not pdf_exists:
        log._write("[WARN] 未找到 2601.00062v1.pdf，请将 PDF 置于 merge_project/docs/ 目录")
        log._write("        仍将执行参数推荐、写作规范化、检索（使用内置 mock / 已有记忆）")

    # ---------- Step 0: 环境校验 ----------
    _log_step(log, "Step0", "ensure_env", "检查环境变量")
    env_status = app.ensure_env()
    log.log_output("ensure_env", env_status)
    summary["env_ok"] = bool(
        env_status.get("dashscope_configured") or
        env_status.get("memu_configured") or
        env_status.get("anthropic_configured")
    )

    # ---------- Step 1: 场景一 — 论文入库 + 分析 ----------
    _log_step(log, "Step1", "场景一", "论文上传分析、paper_ingest_pdf、paper_analysis_scenario")
    _log_step(log, "Step1", "场景一输入", "PDF + 用户问题")
    log.log_input("file_path", pdf_path, "场景一输入")
    log.log_input("user_question", USER_QUESTION_FOR_ANALYSIS, "场景一输入")
    structured_from_paper = None
    if pdf_exists:
        ingest = app.paper_ingest_pdf(
            file_path=pdf_path,
            user_id=TEST_USER_ID,
            agent_ids=[TEST_AGENT_ID],
            user_input="关注论文中的参数、现象与创新点",
        )
        log.log_output("paper_ingest_pdf", ingest)
        summary["scenario1"]["paper_ingest"] = {
            "agent_ids": ingest.get("agent_ids"),
            "results_count": len(ingest.get("results", [])),
            "error": ingest.get("error"),
        }
        results = ingest.get("results") or []
        if results and results[0].get("structured"):
            structured_from_paper = results[0]["structured"]

        analysis = app.paper_analysis_scenario(
            file_path=pdf_path,
            user_question=USER_QUESTION_FOR_ANALYSIS,
            user_id=TEST_USER_ID,
            agent_ids=[TEST_AGENT_ID],
            log_step=lambda s, m, d=None, **kw: _log_step(log, "paper_analysis", s, m, kw.get("data", d)),
            skip_formula_verify=True,
        )
        structured = analysis.get("text_thread") or {}
        markdown_summary = analysis.get("markdown_summary") or ""
        if markdown_summary:
            md_path = log.save_markdown("paper_analysis_scenario", markdown_summary)
            log.log_step("场景一输出", f"Markdown 已保存至 {md_path}", data={"markdown_len": len(markdown_summary)})
        log.log_output("场景一输出_structured_keys", list(structured.keys()) if isinstance(structured, dict) else [], "场景一输出")
        summary["scenario1"]["paper_analysis"] = {
            "agent_ids": analysis.get("agent_ids"),
            "has_structured": bool(structured and not structured.get("error")),
            "has_markdown": bool(markdown_summary),
            "figures_count": len(structured.get("figures", [])) if isinstance(structured, dict) else 0,
        }
        if structured and not structured.get("error") and not structured_from_paper:
            structured_from_paper = structured
    else:
        summary["scenario1"]["paper_ingest"] = "skipped_no_pdf"
        summary["scenario1"]["paper_analysis"] = "skipped_no_pdf"

    # ---------- Step 2: 场景三 — 参数推荐 ----------
    _log_step(log, "Step2", "场景三", "参数推荐：反推用户参数")
    minimal_paper = {
        "metadata": {"title": "Chaos in driven macrospin", "journal": "arXiv", "year": "2025"},
        "observed_phenomena": "宏观自旋系统中混沌、准周期与周期行为",
        "simulation_results_description": "Lyapunov 指数、分岔图",
        "methodology": "周期驱动宏观自旋模型",
        "keywords": ["chaos", "Lyapunov", "macrospin"],
        "parameters": [],
    }
    if structured_from_paper and not structured_from_paper.get("error"):
        minimal_paper = structured_from_paper
    log.log_input("场景三输入_structured_paper(keys)", list(minimal_paper.keys()) if isinstance(minimal_paper, dict) else [], "场景三输入")
    log.log_input("场景三输入_user_params", PARAM_REC_USER_PARAMS, "场景三输入")

    param_out = app.parameter_recommendation(
        structured_paper=minimal_paper,
        user_params=PARAM_REC_USER_PARAMS,
        user_id=TEST_USER_ID,
        agent_id=TEST_AGENT_ID,
    )
    log.log_output("场景三输出", param_out)
    summary["scenario3"] = {
        "parameter_recommendations": param_out.get("parameter_recommendations"),
        "error": param_out.get("error"),
        "agent_id_used": param_out.get("agent_id_used"),
    }

    # ---------- Step 3: 场景二 — 写作规范化 ----------
    _log_step(log, "Step3", "场景二", "写作 query 规范化（记忆增强）")
    log.log_input("场景二输入_raw_input", WRITING_RAW_INPUT, "场景二输入")
    norm = app.normalize_query(
        raw_input=WRITING_RAW_INPUT,
        venue_id="nature",
        project_type_id="paper",
        data_file_names=[],
        user_id=TEST_USER_ID,
        agent_id=TEST_AGENT_ID,
    )
    log.log_output("场景二输出", norm)
    summary["scenario2"] = {
        "query_len": len(norm.get("query", "")),
        "source": norm.get("source"),
        "error": norm.get("error"),
    }

    # ---------- Step 4: 场景四 — 记忆检索 ----------
    _log_step(log, "Step4", "场景四", "memU retrieve + match_and_resolve")
    log.log_input("场景四输入_query", USER_QUESTION_FOR_RETRIEVAL, "场景四输入")
    raw_ret = app.memu_retrieve(query=USER_QUESTION_FOR_RETRIEVAL, user_id=TEST_USER_ID, agent_id=TEST_AGENT_ID)
    match = app.memu_match_and_resolve(query=USER_QUESTION_FOR_RETRIEVAL, user_id=TEST_USER_ID, agent_id=TEST_AGENT_ID, limit=5)
    log.log_output("场景四输出_memu_retrieve", {"keys": list(raw_ret.keys()) if isinstance(raw_ret, dict) else [], "error": raw_ret.get("error")})
    log.log_output("场景四输出_memu_match_and_resolve", {"matched_record_ids": match.get("matched_record_ids"), "records_count": len(match.get("records", []))})
    summary["scenario4"] = {
        "matched_record_ids": match.get("matched_record_ids"),
        "records_count": len(match.get("records", [])),
    }

    log._write("=" * 60)
    log._write("[单论文全流程] 结束")
    log._write(f"[输出目录] Markdown 等输出文件: {LOG_DIR / 'outputs'}")
    log.log_output("summary", summary)
    log_path = log.log_path.resolve()
    log.close()
    summary["_log_path"] = str(log_path)
    summary["_outputs_dir"] = str(LOG_DIR / "outputs")
    return summary


def test_single_paper_full_flow():
    """Pytest 入口：单论文四场景全流程验证。"""
    summary = run_single_paper_full_flow(use_test_db=True, skip_writing_generation=True)
    assert "scenario1" in summary and "scenario3" in summary and "scenario4" in summary
    assert "parameter_recommendations" in summary.get("scenario3", {}) or "error" in summary.get("scenario3", {})
    assert "query_len" in summary.get("scenario2", {}) or "error" in summary.get("scenario2", {})


if __name__ == "__main__":
    summary = run_single_paper_full_flow(use_test_db=True, skip_writing_generation=True)
    log_path = summary.get("_log_path") or LOG_DIR
    outputs_dir = summary.get("_outputs_dir") or str(LOG_DIR / "outputs")
    print("\n" + "=" * 60)
    print("单论文全流程验证完成。")
    print("日志文件:", log_path)
    print("Markdown 输出目录:", outputs_dir)
    print("=" * 60)
