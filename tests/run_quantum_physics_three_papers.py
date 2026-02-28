#!/usr/bin/env python3
"""
量子物理三篇论文四场景验证入口。
使用 docs 下三篇量子物理论文：
  - 2511.00150v1.pdf
  - 2601.00062v1.pdf
  - 2601.00077v1.pdf

前置条件：
  1. 将上述 PDF 置于 merge_project/docs/ 目录
  2. 配置 .env（DASHSCOPE_API_KEY、MEMU_API_KEY 等）

运行（在 merge_project 根目录）：
  python tests/run_quantum_physics_three_papers.py

可选环境变量：
  SKIP_WRITING_GEN=1  跳过论文生成（默认跳过，避免长时间运行）
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env", override=True)
except ImportError:
    pass

from tests.test_quantum_physics_three_papers import run_quantum_physics_three_papers
from tests.test_utils import LOG_DIR, get_docs_path

PAPERS = ["2511.00150v1.pdf", "2601.00062v1.pdf", "2601.00077v1.pdf"]


def main():
    missing = [f for f in PAPERS if not get_docs_path(f).exists()]
    if missing:
        print(f"[WARN] 未找到: {missing}")
        print("       请将 PDF 置于 merge_project/docs/ 目录")
    else:
        print(f"[OK] 使用论文: {PAPERS}")

    skip_gen = os.environ.get("SKIP_WRITING_GEN", "1") == "1"
    print("\n开始量子物理三篇论文四场景验证...")
    summary = run_quantum_physics_three_papers(
        use_test_db=True,
        skip_writing_generation=skip_gen,
    )

    print("\n" + "=" * 80)
    print("量子物理三篇论文四场景验证完成。")
    print("日志文件:", summary.get("_log_path"))
    print("Markdown 输出:", summary.get("_outputs_dir"))
    print("=" * 80)
    return 0


if __name__ == "__main__":
    sys.exit(main())
