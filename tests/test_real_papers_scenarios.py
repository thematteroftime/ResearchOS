# tests/test_real_papers_scenarios.py
"""
真实论文场景测试：多篇 PDF + 四场景全流程。
- 默认使用五篇多领域论文（physics/biology/math/cs/chemistry）做交叉验证。
- 同一领域深度研究请使用：tests/test_quantum_physics_three_papers.py
  使用三篇量子物理论文（2511.00150v1.pdf, 2601.00062v1.pdf, 2601.00077v1.pdf）验证四场景。

运行：
  python tests/test_real_papers_scenarios.py
  或 pytest tests/test_real_papers_scenarios.py -v -s
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

from tests.test_utils import DebugLogger, LOG_DIR, get_docs_path


TEST_USER_ID = "real_papers_test_user"

# 真实论文与预期 agent 映射
REAL_PAPER_CASES: List[Dict[str, str]] = [
    {"filename": "2601.00062v1.pdf", "agent_id": "physics_agent"},
    {"filename": "2602.18909v1.pdf", "agent_id": "biology_agent"},
    {"filename": "2602.19924v1.pdf", "agent_id": "math_agent"},
    {"filename": "2602.20094v1.pdf", "agent_id": "cs_agent"},
    {"filename": "chemrxiv.15000329_v1.pdf", "agent_id": "chemistry_agent"},
]


def run_real_papers_scenarios(
    use_test_db: bool = True,
) -> Dict[str, Any]:
    """
    使用五篇真实论文按领域跑一遍四场景：
      - intent_to_agent_ids（打印预期/预测，摘要由 app.get_pdf_abstract_snippet 提取）
      - memu_upload_files(scene=paper) + paper_ingest_pdf（单 agent 入库 + memU 记忆 + DB）
      - memu_list_records + memu_get_download_info（检查分类与路径）
      - parameter_recommendation（基于入库 structured 与 user_params）
      - normalize_query 对比无记忆 vs 有记忆（打印差异）
      - memu_retrieve + memu_match_and_resolve（论文相关 query 检索）
    所有变量变化与关键中间结果均打印并写入 tests/logs/real_papers_scenarios_*.log。
    """
    ts = time.strftime("%Y%m%d_%H%M%S", time.localtime())
    log = DebugLogger("real_papers_scenarios", subdir=str(LOG_DIR))
    log._write(f"[INIT] 真实论文场景测试开始 | user_id={TEST_USER_ID} | ts={ts}")
    log._write("=" * 60)

    from backend.app_backend import AppBackend
    try:
        from tests.test_utils import get_test_db_and_storage
    except ImportError:
        def get_test_db_and_storage():
            from backend.config import MEMU_TEST_DB, MEMU_TEST_STORAGE
            MEMU_TEST_STORAGE.mkdir(parents=True, exist_ok=True)
            return MEMU_TEST_DB, MEMU_TEST_STORAGE

    # 使用统一测试 DB/存储
    if use_test_db:
        test_db, test_storage = get_test_db_and_storage()
    else:
        from backend.config import MEMU_DB, MEMU_STORAGE_DIR
        test_db, test_storage = MEMU_DB, MEMU_STORAGE_DIR

    app = AppBackend(
        memu_user_id=TEST_USER_ID,
        memu_agent_id="_default",
        memu_db_path=test_db,
        memu_storage_dir=test_storage,
    )

    summary: Dict[str, Any] = {
        "papers": {},
        "parameter_recommendation": {},
        "normalize_compare": {},
        "retrieve": {},
        "env_ok": False,
        "errors": [],
    }
    last_structured_for_param_rec: Optional[Dict[str, Any]] = None
    last_agent_id_for_param_rec: Optional[str] = None

    # Step 0: 环境检查
    env_status = app.ensure_env()
    log.log_output("ensure_env", env_status)
    summary["env_ok"] = bool(env_status.get("dashscope_configured") or env_status.get("memu_configured"))

    # Step 1: 逐篇论文入库 + memU/DB 检查
    for case in REAL_PAPER_CASES:
        fname = case["filename"]
        aid = case["agent_id"]
        paper_path = get_docs_path(fname)
        log.log_file_used(f"论文 {fname}", str(paper_path), paper_path.exists())
        paper_key = f"{fname}|{aid}"
        summary["papers"][paper_key] = {"exists": paper_path.exists(), "agent_id": aid}

        if not paper_path.exists():
            log.log_step("skip_paper", f"{fname} 不存在，跳过该论文场景")
            summary["errors"].append(f"{fname} not found")
            continue

        # 1.1 意图识别：通过 app_backend 提取摘要（整合 PyMuPDF，避免 read_text 乱码）
        abstract_hint = app.get_pdf_abstract_snippet(str(paper_path), max_chars=1000)
        log.log_step(
            "abstract_snippet",
            f"用于意图识别的摘要片段（{fname}）",
            data=abstract_hint[:500] if abstract_hint else f"(file_name: {paper_path.name})",
        )
        intent_ids = app.intent_to_agent_ids(
            input_text=abstract_hint or paper_path.name,
            file_path=str(paper_path),
            file_name=paper_path.name,
        )
        log.log_step(
            "intent_to_agent_ids",
            f"input_file={paper_path.name}",
            data={"expected_agent_id": aid, "predicted_agent_ids": intent_ids},
        )
        summary["papers"][paper_key]["intent_agent_ids"] = intent_ids

        # 1.2 上传原始 PDF（scene=paper）
        log.log_input("upload_file", str(paper_path))
        up = app.memu_upload_files(
            file_paths=[str(paper_path)],
            scene="paper",
            user_input="真实论文入库测试：原始 PDF",
            user_id=TEST_USER_ID,
            agent_id=aid,
            wait=False,
        )
        log.log_output("memu_upload_files", up)
        summary["papers"][paper_key]["upload"] = {"record_ids": up.get("record_ids"), "error": up.get("error")}

        # 1.3 调用 paper_ingest_pdf：显式指定 agent_ids，便于多领域测试
        log.log_step("paper_ingest_pdf", f"开始解析 {fname}", data={"agent_ids": [aid]})
        ingest = app.paper_ingest_pdf(
            file_path=str(paper_path),
            user_id=TEST_USER_ID,
            agent_ids=[aid],
            user_input="关注论文中的参数、现象与创新点",
        )
        log.log_output("paper_ingest_pdf", ingest)
        summary["papers"][paper_key]["paper_ingest"] = {
            "agent_ids": ingest.get("agent_ids"),
            "results_count": len(ingest.get("results", [])),
            "error": ingest.get("error"),
        }
        # 保存第一篇成功入库的 structured，供 Step 2 参数推荐使用
        if last_structured_for_param_rec is None and not ingest.get("error"):
            for r in ingest.get("results", []):
                if r.get("structured") and not r.get("error"):
                    last_structured_for_param_rec = r["structured"]
                    last_agent_id_for_param_rec = r.get("agent_id") or aid
                    break

        # 1.4 memU/DB 检查：列出 scene=paper 的记录，并解析下载路径
        recs = app.memu_list_records(user_id=TEST_USER_ID, agent_id=aid, scene="paper", limit=20)
        log.log_output(
            f"memu_list_records(scene=paper, agent={aid})",
            {"count": len(recs), "record_ids": [r.get("record_id") for r in recs]},
        )
        dl_info_list: List[Dict[str, Any]] = []
        for rec in recs[:3]:
            rid = rec.get("record_id")
            if not rid:
                continue
            info = app.memu_get_download_info(record_id=rid, user_id=TEST_USER_ID, agent_id=aid)
            log.log_output(f"memu_get_download_info(record_id={rid})", info)
            dl_info_list.append({"record_id": rid, "info_keys": list(info.keys()) if isinstance(info, dict) else []})
        summary["papers"][paper_key]["download_info_sample"] = dl_info_list

    # Step 2: 参数推荐场景（使用入库得到的 structured_paper）
    log.log_step("parameter_recommendation", "基于真实论文 structured 调用 app.parameter_recommendation")
    if last_structured_for_param_rec and last_agent_id_for_param_rec:
        user_params = {
            "expected_phenomena": "混沌、准周期、周期倍增及 Lyapunov 指数的分类作用",
            "Lyapunov_exponent": "最大李雅普诺夫指数，单位 1/s",
            "drive_frequency": "驱动频率，单位 Hz",
        }
        log.log_input("parameter_recommendation", {"user_params": user_params, "agent_id": last_agent_id_for_param_rec})
        param_rec = app.parameter_recommendation(
            structured_paper=last_structured_for_param_rec,
            user_params=user_params,
            user_id=TEST_USER_ID,
            agent_id=last_agent_id_for_param_rec,
        )
        log.log_output("parameter_recommendation", param_rec)
        summary["parameter_recommendation"] = {
            "agent_id_used": param_rec.get("agent_id_used"),
            "parameter_recommendations": param_rec.get("parameter_recommendations", {}),
            "force_field_recommendation": param_rec.get("force_field_recommendation", {}),
            "error": param_rec.get("error"),
        }
        # 无 error 时检查 parameter_recommendation 场景存储（summary.md、recommendations.json）
        if not param_rec.get("error"):
            pr_recs = app.memu_list_records(user_id=TEST_USER_ID, agent_id=last_agent_id_for_param_rec, scene="parameter_recommendation", limit=3)
            if pr_recs:
                pr_info = app.memu_get_download_info(record_id=pr_recs[0]["record_id"], user_id=TEST_USER_ID, agent_id=last_agent_id_for_param_rec)
                log.log_output("memu_get_download_info(parameter_recommendation)", {"summary_md_path": pr_info.get("summary_md_path"), "recommendations_json_path": pr_info.get("recommendations_json_path")})
    else:
        log.log_step("parameter_recommendation", "跳过：无有效 structured（论文未入库或入库失败）")
        summary["parameter_recommendation"] = {"skipped": True, "reason": "no_structured"}

    # Step 3: 写作场景中，比较无记忆 vs 使用 memU 记忆的 normalize_query
    log.log_step("normalize_query_compare", "比较有/无 memU 记忆时的 query 差异")
    # 选一篇物理论文 + 一篇化学论文的摘要风格 query
    physics_raw = (
        "A short note on classical vs quantum dynamics and the onset of chaos in a periodically driven macrospin "
        "system, focusing on Lyapunov exponents and bifurcation diagrams."
    )
    chemistry_raw = (
        "Nitric oxide delivery across the stratum corneum mediated by chitosan nanogels loaded with GSNO, "
        "with and without an external electric field."
    )

    for label, raw_q, aid in [
        ("physics", physics_raw, "physics_agent"),
        ("chemistry", chemistry_raw, "chemistry_agent"),
    ]:
        compare = app.compare_normalize_query_with_without_memory(
            raw_input=raw_q,
            venue_id="nature",
            project_type_id="paper",
            data_file_names=[],
            user_id=TEST_USER_ID,
            agent_id=aid,
        )
        log.log_step(
            f"normalize_query_{label}",
            "对比无记忆 vs 使用 memU 记忆的 query",
            data=compare,
        )
        summary["normalize_compare"][label] = compare

    # Step 4: 检索场景（基于真实论文构造的用户问题）
    log.log_step("retrieve_and_match", "基于真实论文构造 query 测试 memu_retrieve + memu_match_and_resolve")
    retrieve_queries = [
        "宏观自旋系统中 Lyapunov 指数 λ_max>0 的混沌区域对应哪些驱动参数？",
        "chitosan-GSNO 纳米胶在有/无电场时如何改变 stratum corneum 的 NO 通量？",
    ]
    retrieve_results: List[Dict[str, Any]] = []
    for q in retrieve_queries:
        log.log_input("retrieve_query", q)
        raw_ret = app.memu_retrieve(query=q, user_id=TEST_USER_ID, agent_id=None)
        match = app.memu_match_and_resolve(query=q, user_id=TEST_USER_ID, agent_id=None, limit=5)
        log.log_output(
            "memu_retrieve",
            {"keys": list(raw_ret.keys()) if isinstance(raw_ret, dict) else [], "error": raw_ret.get("error") if isinstance(raw_ret, dict) else None},
        )
        log.log_output(
            "memu_match_and_resolve",
            {"matched_record_ids": match.get("matched_record_ids"), "records_count": len(match.get("records", []))},
        )
        sample_records = []
        for rec in (match.get("records") or [])[:3]:
            sample_records.append(
                {
                    "record_id": rec.get("record_id"),
                    "scene": rec.get("scene"),
                    "storage_path": rec.get("storage_path"),
                }
            )
        retrieve_results.append(
            {
                "query": q,
                "matched_record_ids": match.get("matched_record_ids"),
                "records_sample": sample_records,
            }
        )
    summary["retrieve"]["queries"] = retrieve_results

    log._write("=" * 60)
    log.log_output("summary", summary)
    log._write("[DONE] 真实论文场景测试结束")
    log.close()
    return summary


def test_real_papers_scenarios():
    """pytest 入口：执行真实论文场景测试，做最小断言（其余细节通过日志人工检查）。"""
    summary = run_real_papers_scenarios(use_test_db=True)
    assert isinstance(summary, dict)
    assert "papers" in summary and "parameter_recommendation" in summary
    assert "normalize_compare" in summary and "retrieve" in summary


if __name__ == "__main__":
    run_real_papers_scenarios(use_test_db=True)
    print("\n真实论文场景测试完成。日志目录:", LOG_DIR)

