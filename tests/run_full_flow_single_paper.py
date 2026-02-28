#!/usr/bin/env python3
"""
单论文全流程验证入口：使用 docs/2601.00062v1.pdf 覆盖四场景。

前置条件：
  1. 将 2601.00062v1.pdf 置于 merge_project/docs/ 目录
  2. 配置 .env（DASHSCOPE_API_KEY、MEMU_API_KEY 等，见 .env.example）

运行（在 merge_project 根目录）：
  python tests/run_full_flow_single_paper.py

输出：控制台打印 + 日志文件 tests/logs/single_paper_full_flow_<时间>.log
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env", override=True)
except ImportError:
    pass

from tests.test_single_paper_full_flow import run_single_paper_full_flow
from tests.test_utils import LOG_DIR, get_docs_path

SINGLE_PAPER = "2601.00062v1.pdf"


def main():
    pdf_path = get_docs_path(SINGLE_PAPER)
    if not pdf_path.exists():
        print(f"[WARN] 未找到 {SINGLE_PAPER}，请将 PDF 置于 merge_project/docs/ 目录")
        print("        测试将继续执行（使用 mock 数据完成参数推荐/写作/检索）")
    else:
        print(f"[OK] 使用论文: {pdf_path}")

    print("\n开始单论文四场景全流程...")
    summary = run_single_paper_full_flow(
        pdf_path_override=str(pdf_path) if pdf_path.exists() else None,
        use_test_db=True,
        skip_writing_generation=True,
    )

    log_path = summary.get("_log_path") or str(LOG_DIR)
    outputs_dir = summary.get("_outputs_dir") or str(LOG_DIR / "outputs")
    print("\n" + "=" * 60)
    print("单论文全流程验证完成。")
    print("日志文件:", log_path)
    print("Markdown 输出目录:", outputs_dir)
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
