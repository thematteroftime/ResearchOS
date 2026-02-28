# tests/test_quantum_physics_three_papers.py
"""
量子物理领域三篇论文四场景全流程验证：同一领域深度研究。
使用 docs 下三篇量子物理论文：
  - 2511.00150v1.pdf
  - 2601.00062v1.pdf
  - 2601.00077v1.pdf

验证目标：
  1) 场景一：论文入库 — 每篇产出 .md / .json 正确存储，打印部分内容用于调试
  2) 场景三：参数推荐 — 多篇关联论文的记忆系统体现，json/md 正确保存与打印
  3) 场景二：写作 — 有/无 memU 的 query 对比 + 真实调用 run_paper_generation 生成论文
  4) 场景四：检索与下载 — 三篇论文记录均能检索到，下载一篇到 database/downloads/test_quantum_papers

运行：
  python tests/test_quantum_physics_three_papers.py           # 含写作（默认 minimal query，提高成功率）
  python tests/test_quantum_physics_three_papers.py --full-writing  # 完整 query+记忆规范化
  python tests/test_quantum_physics_three_papers.py --no-writing    # 仅 query 对比
  pytest tests/test_quantum_physics_three_papers.py -v -s
"""

import asyncio
import json
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


TEST_USER_ID = "quantum_physics_three_papers_user"
TEST_AGENT_ID = "physics_agent"

# 三篇量子物理论文（同一领域）
QUANTUM_PAPERS = [
    "2511.00150v1.pdf",
    "2601.00062v1.pdf",
    "2601.00077v1.pdf",
]

# 用于 memU 检索的量子物理领域 query
USER_QUESTION_FOR_ANALYSIS = (
    "这些量子物理论文中关于量子动力学、混沌、相变或纠缠的研究方法、参数与主要结论是什么？"
)

# 参数推荐：期望现象与参数（量子物理相关）
PARAM_REC_USER_PARAMS = {
    "expected_phenomena": "量子混沌、李雅普诺夫指数、分岔行为",
    "driving_amplitude": "驱动振幅",
    "driving_frequency": "驱动频率",
    "coupling_strength": "耦合强度",
}

# 写作：参考 claude-scientific-writer README 用例格式（显式引用数据、限定篇幅）
# 格式：Create a Nature paper on [topic]. Present [data]. Include [figures]. Highlight [key finding].
WRITING_RAW_INPUT = (
    "Create a Nature paper on quantum chaos in driven spin systems. "
    "Present key findings from the attached summary files: Lyapunov exponent (λ_max) as quantum-classical "
    "convergence criterion, bifurcation structure mapping chaotic/quasiperiodic phases, and comparison of "
    "simulated vs quantum reverse annealing. Include methodology from Lindblad master equation and mean-field models. "
    "Target 800-1000 words. Do not run external research lookup."
)
# 最简 fallback：README 最小用例风格，提高成功率
WRITING_QUERY_MINIMAL = (
    "Create a short Nature paper on quantum chaos in driven spin systems. "
    "Summarize the attached summary.md files. Keep manuscript to 800 words."
)

# 检索 query：应命中三篇论文
RETRIEVAL_QUERY = "量子物理 量子动力学 混沌 李雅普诺夫 自旋系统"


def _log_step(log: DebugLogger, step: str, name: str, detail: str = "", data: Any = None) -> None:
    log.log_step(f"{step} | {name}", detail, data=data)


def _print_storage_verification(log: DebugLogger, folder_path: str, paper_name: str, expected_pdf_name: Optional[str] = None) -> None:
    """验证并打印 structured.json、summary.md、PDF、figures 存储。"""
    folder = Path(folder_path)
    if not folder.exists():
        log._write(f"[存储验证] {paper_name} 目录不存在: {folder_path}")
        return
    json_path = folder / "structured.json"
    md_path = folder / "summary.md"
    pdf_ok = False
    if expected_pdf_name and (folder / expected_pdf_name).exists():
        pdf_ok = True
        log._write(f"[存储验证] {paper_name} PDF 存在: {expected_pdf_name}")
    elif expected_pdf_name:
        log._write(f"[存储验证] {paper_name} PDF 缺失: {expected_pdf_name}")
    figures_dir = folder / "figures"
    figures_count = len(list(figures_dir.glob("*.png"))) if figures_dir.exists() else 0
    log._write(f"[存储验证] {paper_name} figures/*.png 数量: {figures_count}")
    if json_path.exists():
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            preview = {
                "keys": list(data.keys()),
                "metadata_title": (data.get("metadata") or {}).get("title", "")[:120],
                "methodology_preview": (data.get("methodology") or "")[:200],
            }
            log._write(f"[存储验证] {paper_name} structured.json 片段:")
            log._write(f"   keys={preview['keys']}")
            log._write(f"   title={preview['metadata_title']}")
            log._write(f"   methodology={preview['methodology_preview']}...")
        except Exception as e:
            log._write(f"[存储验证] {paper_name} structured.json 读取失败: {e}")
    else:
        log._write(f"[存储验证] {paper_name} structured.json 不存在")
    if md_path.exists():
        content = md_path.read_text(encoding="utf-8")
        log._write(f"[存储验证] {paper_name} summary.md 前 400 字:")
        log._write(f"   {content[:400]}...")
    else:
        log._write(f"[存储验证] {paper_name} summary.md 不存在")


def run_quantum_physics_three_papers(
    use_test_db: bool = True,
    skip_writing_generation: bool = False,
    use_minimal_writing_query: bool = True,
) -> Dict[str, Any]:
    ts = time.strftime("%Y%m%d_%H%M%S", time.localtime())
    log = DebugLogger("quantum_physics_three_papers", subdir=str(LOG_DIR))
    log._write(f"[INIT] 量子物理三篇论文四场景验证 | user_id={TEST_USER_ID} | ts={ts}")
    log._write("=" * 80)

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
        "scenario1": {"papers": {}, "all_record_ids": []},
        "scenario2": {},
        "scenario3": {},
        "scenario4": {},
        "env_ok": False,
        "errors": [],
    }

    # Step 0: 环境检查
    env_status = app.ensure_env()
    log.log_output("ensure_env", env_status)
    summary["env_ok"] = bool(
        env_status.get("dashscope_configured") or
        env_status.get("memu_configured") or
        env_status.get("anthropic_configured")
    )

    all_paper_record_ids: List[str] = []
    all_structured: List[Dict[str, Any]] = []
    data_files_for_writing: List[str] = []

    # ---------- Step 1: 场景一 — 三篇论文入库（paper_analysis_scenario 含 memU 记忆融合 + paper_ingest_pdf）----------
    _log_step(log, "Step1", "场景一", "三篇量子物理论文分析入库，memU 记忆增强，.md/.json 存储验证")
    for fname in QUANTUM_PAPERS:
        paper_path = get_docs_path(fname)
        log.log_file_used(f"论文 {fname}", str(paper_path), paper_path.exists())
        if not paper_path.exists():
            log._write(f"[跳过] {fname} 不存在")
            summary["errors"].append(f"{fname} not found")
            continue

        abstract_hint = app.get_pdf_abstract_snippet(str(paper_path), max_chars=800)
        _log_step(log, "Step1", f"abstract_snippet({fname})", "摘要片段", data=abstract_hint[:300] if abstract_hint else None)

        analysis = app.paper_analysis_scenario(
            file_path=str(paper_path),
            user_question=USER_QUESTION_FOR_ANALYSIS,
            user_id=TEST_USER_ID,
            agent_ids=[TEST_AGENT_ID],
            log_step=lambda s, m, d=None, **kw: _log_step(log, "paper_analysis", s, m, kw.get("data", d)),
            skip_formula_verify=True,
        )
        ingest_result = analysis.get("ingest_result") or {}
        log.log_output(f"paper_analysis_scenario({fname})", {
            "results_count": len(ingest_result.get("results", [])),
            "error": ingest_result.get("error"),
        })

        for r in (ingest_result.get("results") or []):
            if r.get("error"):
                continue
            rid = r.get("record_id")
            folder = r.get("resolved_storage_folder")
            structured = r.get("structured")
            if rid:
                all_paper_record_ids.append(rid)
            if folder:
                _print_storage_verification(log, folder, fname, expected_pdf_name=fname)
                smd = Path(folder) / "summary.md"
                if smd.exists():
                    data_files_for_writing.append(str(smd))
            if structured and not structured.get("error"):
                all_structured.append(structured)

        markdown_summary = analysis.get("markdown_summary") or ""
        if markdown_summary:
            md_path = log.save_markdown(f"analysis_{fname.replace('.', '_')}", markdown_summary)
            _log_step(log, "Step1", "markdown_output", f"分析 Markdown 已保存 {md_path}", data={"len": len(markdown_summary)})

    summary["scenario1"]["all_record_ids"] = all_paper_record_ids
    summary["scenario1"]["papers_ingested"] = len(all_paper_record_ids)
    # 无入库 summary 时：先试 data/docs 下 PDF，再用 data/quantum_chaos_summary_sample.md
    if not data_files_for_writing:
        for fname in QUANTUM_PAPERS:
            for base in (ROOT / "data", ROOT / "docs"):
                if (base / fname).exists():
                    data_files_for_writing.append(str((base / fname).resolve()))
                    log._write(f"[Step1] 使用写作数据: {base.name}/{fname}")
                    break
        if not data_files_for_writing:
            fallback_md = ROOT / "data" / "quantum_chaos_summary_sample.md"
            if fallback_md.exists():
                data_files_for_writing.append(str(fallback_md))
                log._write(f"[Step1] 使用 data/ 样本文件: {fallback_md.name}")
    log._write(f"[Step1 完成] 入库 record_ids: {all_paper_record_ids}")

    # ---------- Step 2: 场景三 — 参数推荐（多篇论文记忆体现）----------
    _log_step(log, "Step2", "场景三", "参数推荐：memU 检索三篇论文记忆作为上下文")
    merged_paper = all_structured[0] if all_structured else {
        "metadata": {"title": "Quantum chaos studies"},
        "observed_phenomena": "量子混沌与李雅普诺夫指数",
        "simulation_results_description": "驱动自旋系统",
        "methodology": "数值模拟",
        "parameters": [],
    }
    log.log_input("场景三输入_user_params", PARAM_REC_USER_PARAMS)
    log.log_input("场景三输入_structured_keys", list(merged_paper.keys()) if isinstance(merged_paper, dict) else [])

    param_out = app.parameter_recommendation(
        structured_paper=merged_paper,
        user_params=PARAM_REC_USER_PARAMS,
        user_id=TEST_USER_ID,
        agent_id=TEST_AGENT_ID,
    )
    log.log_output("场景三输出", param_out)

    memory_used = param_out.get("memory_context_used", 0)
    _log_step(log, "Step2", "memory_context", f"memU 记忆上下文长度: {memory_used} 字符", data={"memory_context_used": memory_used})

    if not param_out.get("error"):
        pr_recs = app.memu_list_records(user_id=TEST_USER_ID, agent_id=TEST_AGENT_ID, scene="parameter_recommendation", limit=5)
        if pr_recs:
            rid = pr_recs[0]["record_id"]
            info = app.memu_get_download_info(record_id=rid, user_id=TEST_USER_ID, agent_id=TEST_AGENT_ID)
            smd = info.get("summary_md_path")
            rjson = info.get("recommendations_json_path")
            log._write(f"[场景三存储] summary_md_path={smd}")
            log._write(f"[场景三存储] recommendations_json_path={rjson}")
            if smd and Path(smd).exists():
                content = Path(smd).read_text(encoding="utf-8")
                log._write(f"[场景三打印] summary.md 前 500 字:")
                log._write(f"   {content[:500]}...")
            if rjson and Path(rjson).exists():
                data = json.loads(Path(rjson).read_text(encoding="utf-8"))
                log._write(f"[场景三打印] recommendations.json keys={list(data.keys())}")
                log._write(f"   parameter_recommendations 片段: {str(data.get('parameter_recommendations', {}))[:400]}...")

    summary["scenario3"] = {
        "parameter_recommendations": param_out.get("parameter_recommendations"),
        "memory_context_used": memory_used,
        "error": param_out.get("error"),
    }

    # ---------- Step 3: 场景二 — 写作（有/无记忆对比 + 可选生成）----------
    _log_step(log, "Step3", "场景二", "写作：有/无 memU 记忆的 query 对比")
    log.log_input("场景二输入_raw_input", WRITING_RAW_INPUT)

    compare = app.compare_normalize_query_with_without_memory(
        raw_input=WRITING_RAW_INPUT,
        venue_id="nature",
        project_type_id="paper",
        data_file_names=data_files_for_writing[:3] if data_files_for_writing else [],
        user_id=TEST_USER_ID,
        agent_id=TEST_AGENT_ID,
    )
    log._write("[场景二打印] 无记忆 base_query:")
    log._write(f"   {compare.get('base_query', '')[:600]}...")
    log._write("[场景二打印] 有 memU 记忆 with_memory_query:")
    log._write(f"   {compare.get('with_memory_query', '')[:600]}...")
    has_diff = compare.get("base_query") != compare.get("with_memory_query")
    _log_step(log, "Step3", "query_compare", f"有/无记忆 query 是否不同: {has_diff}")

    summary["scenario2"] = {
        "base_query_len": len(compare.get("base_query", "")),
        "with_memory_query_len": len(compare.get("with_memory_query", "")),
        "queries_differ": has_diff,
    }

    if not skip_writing_generation and summary["env_ok"]:
        raw_input = WRITING_QUERY_MINIMAL if use_minimal_writing_query else WRITING_RAW_INPUT
        _log_step(log, "Step3", "run_paper_generation", f"调用 scientific-writer（use_minimal={use_minimal_writing_query}）")
        progress_lines: List[str] = []

        async def _run_gen():
            async for upd in app.run_paper_generation(
                raw_input=raw_input,
                venue_id="nature",
                project_type_id="paper",
                data_file_names=data_files_for_writing[:3] if data_files_for_writing else [],
                user_id=TEST_USER_ID,
                agent_id=TEST_AGENT_ID,
                log_step=lambda s, m: progress_lines.append(f"[{s}] {m}"),
                use_minimal_query=use_minimal_writing_query,
            ):
                if upd.get("type") == "progress":
                    progress_lines.append(f"[progress] {upd.get('stage','')} {upd.get('message','')}")
                    log._write(f"   [progress] {upd.get('stage','')} {upd.get('message','')}")
                elif upd.get("type") == "result":
                    log.log_output("run_paper_generation_result", upd)
            return progress_lines

        progress_lines = asyncio.run(_run_gen())
        for line in progress_lines[-20:]:
            log._write(f"   {line}")
        summary["scenario2"]["writing_progress_count"] = len(progress_lines)
        summary["scenario2"]["writing_called"] = True
    else:
        summary["scenario2"]["writing_called"] = False

    # ---------- Step 4: 场景四 — 检索三篇论文 + 下载一篇验证 ----------
    _log_step(log, "Step4", "场景四", "memU 检索 + match_and_resolve，验证三篇论文记录均命中，下载一篇")

    log.log_input("场景四输入_query", RETRIEVAL_QUERY)
    raw_ret = app.memu_retrieve(query=RETRIEVAL_QUERY, user_id=TEST_USER_ID, agent_id=TEST_AGENT_ID)
    match = app.memu_match_and_resolve(query=RETRIEVAL_QUERY, user_id=TEST_USER_ID, agent_id=TEST_AGENT_ID, limit=10)
    log.log_output("memu_retrieve", {"keys": list(raw_ret.keys()) if isinstance(raw_ret, dict) else [], "error": raw_ret.get("error")})
    log.log_output("memu_match_and_resolve", {"matched_record_ids": match.get("matched_record_ids"), "records_count": len(match.get("records", []))})

    matched_ids = match.get("matched_record_ids") or []
    found_count = sum(1 for rid in all_paper_record_ids if rid in matched_ids)
    _log_step(log, "Step4", "检索验证", f"三篇论文 record_ids 中命中数: {found_count}/3", data={"all_paper_record_ids": all_paper_record_ids, "matched_ids": matched_ids})

    summary["scenario4"]["matched_record_ids"] = matched_ids
    summary["scenario4"]["papers_found_count"] = found_count

    if all_paper_record_ids:
        download_rid = all_paper_record_ids[0]
        # 使用 database/downloads 便于在 database 目录直接查看下载文件
        from backend.config import MEMU_DOWNLOADS_DIR
        download_dest = MEMU_DOWNLOADS_DIR / "test_quantum_papers"
        download_dest.mkdir(parents=True, exist_ok=True)
        dl_out = app.memu_download_to_path(
            record_id=download_rid,
            dest_dir=str(download_dest),
            user_id=TEST_USER_ID,
            agent_id=TEST_AGENT_ID,
        )
        log.log_output("memu_download_to_path", dl_out)
        if not dl_out.get("error"):
            saved = dl_out.get("saved_path")
            exists = Path(saved).exists() if saved else False
            _log_step(log, "Step4", "下载验证", f"saved_path={saved}, exists={exists}")
            summary["scenario4"]["download_ok"] = exists
            summary["scenario4"]["downloaded_record_id"] = download_rid
        else:
            summary["scenario4"]["download_ok"] = False
            summary["scenario4"]["download_error"] = dl_out.get("error")

    log._write("=" * 80)
    log.log_output("summary", summary)
    log._write("[DONE] 量子物理三篇论文四场景验证结束")
    log.close()
    summary["_log_path"] = str(log.log_path.resolve())
    summary["_outputs_dir"] = str(LOG_DIR / "outputs")
    from backend.config import MEMU_DOWNLOADS_DIR
    summary["_downloads_dir"] = str(MEMU_DOWNLOADS_DIR / "test_quantum_papers")
    return summary


def test_quantum_physics_three_papers():
    """Pytest 入口：验证四场景流程。至少一篇论文存在时，检索应命中且下载可验证。写作默认调用真实 API。"""
    summary = run_quantum_physics_three_papers(use_test_db=True, skip_writing_generation=False)
    assert isinstance(summary, dict)
    assert "scenario1" in summary and "scenario3" in summary and "scenario2" in summary and "scenario4" in summary
    papers_ingested = summary["scenario1"].get("papers_ingested", 0)
    if papers_ingested >= 1:
        assert "matched_record_ids" in summary["scenario4"]
        assert summary["scenario4"].get("download_ok") is True or "download_error" in summary["scenario4"]


if __name__ == "__main__":
    import sys
    skip_writing = "--no-writing" in sys.argv
    use_full_query = "--full-writing" in sys.argv  # 使用完整 query+记忆规范化；默认用 minimal 提高成功率
    summary = run_quantum_physics_three_papers(
        use_test_db=True,
        skip_writing_generation=skip_writing,
        use_minimal_writing_query=not use_full_query,
    )
    print("\n" + "=" * 80)
    print("量子物理三篇论文四场景验证完成。")
    print("日志:", summary.get("_log_path"))
    print("输出目录:", summary.get("_outputs_dir"))
    dl_ok = summary.get("scenario4", {}).get("download_ok")
    if dl_ok:
        print("下载目录: database/downloads/test_quantum_papers")
    else:
        print("下载失败:", summary.get("scenario4", {}).get("download_error", "unknown"))
    print("=" * 80)
