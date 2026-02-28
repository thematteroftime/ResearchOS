#!/usr/bin/env python3
"""
写作功能验证：通过 AppBackend → ScientificWriterClient 完整调用链验证。

调用链：AppBackend.run_paper_generation → ScientificWriterClient.generate_paper → scientific_writer.generate_paper

前置条件：
  1. 数据文件（任选其一）：
     - data/ 或 docs/ 下的 2511.00150v1.pdf、2601.00062v1.pdf、2601.00077v1.pdf
     - 或 data/quantum_chaos_summary_sample.md（无 PDF 时使用）
  2. pip install scientific-writer 及 merge_project 依赖（见 requirements.txt）
  3. 配置 .env（ANTHROPIC_API_KEY 必需，OPENROUTER_API_KEY 可选）

运行（在 merge_project 根目录）：
  python tests/run_writing_verification.py
  python tests/run_writing_verification.py --full-query   # 完整 query+记忆规范化

输出：writing_outputs/<timestamp>_*/ 及 tests/logs/
"""

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env", override=True)
except ImportError:
    pass

# 三篇论文文件名（优先 data/，其次 docs/）
PAPER_NAMES = [
    "2511.00150v1.pdf",
    "2601.00062v1.pdf",
    "2601.00077v1.pdf",
]

# 用户输入：参考 claude-scientific-writer README 格式
USER_INPUT = (
    "Create a short Nature paper summarizing the three attached PDF papers. "
    "Paper 1 (2511.00150v1.pdf): simulated vs quantum reverse annealing, phase transitions. "
    "Paper 2 (2601.00062v1.pdf): quantum chaos, Lyapunov exponent, macrospin dynamics. "
    "Paper 3 (2601.00077v1.pdf): detection efficiency, Bell nonlocality. "
    "Present key findings from each paper. Target 1000 words."
)

# 最简 fallback（无 PDF 时与 quantum_chaos_summary_sample.md 配合）
USER_INPUT_MINIMAL = (
    "Create a short Nature paper on quantum chaos in driven spin systems. "
    "Summarize the attached summary file. Keep manuscript to 800 words."
)


def _resolve_data_files(paper_names: list, data_dir: Path, docs_dir: Path) -> list:
    """解析 data_files：优先 data/，其次 docs/，支持绝对路径。"""
    resolved = []
    for name in paper_names:
        p = Path(name)
        if p.is_absolute():
            if p.exists():
                resolved.append(str(p))
            continue
        for base in (data_dir, docs_dir):
            cand = base / name
            if cand.exists():
                resolved.append(str(cand.resolve()))
                break
    return resolved


def main():
    data_dir = ROOT / "data"
    docs_dir = ROOT / "docs"

    # 1) 收集 data_files：先试 PDF，无则用 quantum_chaos_summary_sample.md
    data_files = _resolve_data_files(PAPER_NAMES, data_dir, docs_dir)
    if not data_files:
        fallback = data_dir / "quantum_chaos_summary_sample.md"
        if fallback.exists():
            data_files = [str(fallback.resolve())]
            print(f"[OK] 使用备用数据: {fallback.name}")
        else:
            print(f"[MISS] 未找到 PDF 或 {fallback.name}，请将三篇 PDF 置于 data/ 或 docs/")
            return 1

    for f in data_files:
        print(f"[OK] {Path(f).name}")

    print(f"\n共 {len(data_files)} 个数据文件")
    use_minimal = "--full-query" not in sys.argv
    print(f"模式: {'minimal query' if use_minimal else 'full query+记忆规范化'}")
    raw_input = USER_INPUT if data_files and any("pdf" in p.lower() for p in data_files) else USER_INPUT_MINIMAL
    print("用户输入:", raw_input[:200] + "...")
    print("\n开始调用 AppBackend.run_paper_generation（完整调用链）...\n")

    # 2) 通过 AppBackend 调用（验证 AppBackend → ScientificWriterClient → scientific_writer）
    try:
        from backend.app_backend import AppBackend
        from tests.test_utils import get_test_db_and_storage
    except ImportError as e:
        err = str(e)
        print(f"导入失败: {err}")
        if "httpx" in err:
            print("缺少依赖，请运行: pip install httpx python-dotenv scientific-writer")
        elif "scientific_writer" in err:
            print("请运行: pip install scientific-writer")
        else:
            print("请运行: pip install -r requirements.txt")
        print("（在 merge_project 根目录执行）")
        return 1

    test_db, test_storage = get_test_db_and_storage()
    app = AppBackend(
        project_root=ROOT,
        memu_user_id="writing_verification_user",
        memu_agent_id="physics_agent",
        memu_db_path=test_db,
        memu_storage_dir=test_storage,
    )

    # data_file_names: 传绝对路径，app_backend 直接使用；传相对路径则从 project_root/data_dir 解析
    data_file_names = [str(Path(f).resolve()) for f in data_files]

    _last_progress: list = [None]  # 用 list 以便闭包可修改

    def _log_progress(stage: str, msg: str) -> None:
        """统一 progress 打印；去重，避免 scientific-writer 多次 emit 同一条导致刷屏。"""
        key = (stage, msg)
        if key != _last_progress[0]:
            _last_progress[0] = key
            print(f"  [progress] {stage} {msg}")

    async def run():
        result = None
        async for upd in app.run_paper_generation(
            raw_input=raw_input,
            venue_id="nature",
            project_type_id="paper",
            data_file_names=data_file_names,
            user_id="writing_verification_user",
            agent_id="physics_agent",
            use_minimal_query=use_minimal,
            log_step=_log_progress,  # 由脚本统一打印，避免 writer 内部再 print 导致重复
        ):
            if upd.get("type") == "progress":
                # 已通过 log_step 打印，此处不再重复
                pass
            elif upd.get("type") == "result":
                status = upd.get("status", "unknown")
                files = upd.get("files") or {}
                paper_dir = upd.get("paper_directory", "") or upd.get("output_directory", "")
                print("\n" + "=" * 60)
                print(f"写作完成: status={status}")
                print(f"输出目录: {paper_dir}")
                print(f"PDF: {files.get('pdf_final', 'N/A')}")
                print("=" * 60)
                result = upd
        return result

    result = asyncio.run(run())

    if result and result.get("status") == "success":
        print("\n验证通过：AppBackend → ScientificWriterClient → scientific_writer 调用链通畅。")
        return 0
    elif result and result.get("status") == "failed":
        print("\n写作失败，请检查 ANTHROPIC_API_KEY。")
        print("错误:", result.get("errors", []))
        return 1
    else:
        return 0


if __name__ == "__main__":
    sys.exit(main())
