# 测试数据说明 (docs)

本目录用于 **四场景全流程测试** 与日常调试，与 `tests/test_four_scenarios_full_flow.py`、`tests/run_writing_verification.py` 等配合使用。**写作与量子物理测试**会同时查找 `docs/` 与 `data/` 下的 PDF。

## 现有文件

| 文件 | 用途 |
|------|------|
| **FH_data.csv** | 场景一/四：以「数据」场景上传，用于记忆与检索；参数推荐/写作可选引用。 |
| **prompt.txt** | 场景一/四：上传或作为用户输入/论文摘要替代；意图识别与检索测试。 |
| **user_questions_examples.txt** | 多 agent 意图识别与场景四检索：每行一条用户问题或文件名，用于验证 physics/chemistry/biology/cs/math/_default。 |

## 可选：论文 PDF（场景一完整流程）

将 **一篇或多篇 PDF** 放入本目录后，全流程测试会执行真实的「论文上传分析」：

- **单论文全流程验证**（推荐）：将 `2601.00062v1.pdf` 置于 `merge_project/docs/`，运行：
  ```bash
  python tests/run_full_flow_single_paper.py
  # 或
  python tests/test_single_paper_full_flow.py
  ```
  该论文为物理领域（宏观自旋、混沌、Lyapunov 指数）。流程：PyMuPDF 提取 → 意图识别 → LLM 公式校验 → 文本结构化 → 图像理解 → 入库 → 参数推荐 → 写作规范化 → 记忆检索。
- 建议文件名示例（便于多 agent 验证）：  
  `2601.00062v1.pdf`（物理论文）、`2511.00150v1.pdf`、`2601.00077v1.pdf`（量子物理三篇）；`sample_physics.pdf` 等
- **data/** 目录也可放置 PDF；`tests/run_writing_verification.py` 与 `test_quantum_physics_three_papers` 会同时查找 `data/`、`docs/`
- 若 **未放置任何 PDF**，测试会跳过真实 PDF 提取，仅执行：  
  意图识别、数据/文本上传、参数推荐（使用内置最小 structured）、写作规范化、记忆检索。

## 用户问题示例（user_questions_examples.txt）

每行一条，用于：

- **意图识别**：根据文本或文件名推断 `agent_ids`（physics_agent、chemistry_agent 等）。
- **场景四**：memU 检索 + 本地记录解析，验证「用户问题 → 匹配记录 → 可下载列表」。

可自行追加行，覆盖生物、物理、化学、计算机、数学等不同表述，以验证多 agent 与检索逻辑。
