# 存储格式与位置验证报告

## 终端输出 vs 实际存储对照

### 1. 论文入库（场景一）

**终端 record_ids**：`a94f4804-9b0`、`dc76a66f-f6d`、`e6e37f06-1f7`（与 2511.00150v1.pdf、2601.00062v1.pdf、2601.00077v1.pdf 对应）

**预期存储路径**（`CONFIG` + `build_storage_path` 规范）：
```
{database}/memu_storage_test/{user_id}/physics_agent/paper/{record_id}/
```
即：`merge_project/database/memu_storage_test/quantum_physics_three_papers_user/physics_agent/paper/{record_id}/`

**预期文件**：
- `{record_id}/` 下：`2511.00150v1.pdf`（或对应 pdf 名）、`structured.json`、`summary.md`
- `{record_id}/figures/` 下：`{record_id}_page_N.png`（extract_figures 生成）

**实际存在**：✅ 三篇论文的 `structured.json`、`summary.md` 均在正确路径

| record_id    | 路径 | structured.json | summary.md |
|--------------|------|-----------------|------------|
| a94f4804-9b0 | .../paper/a94f4804-9b0/ | ✅ | ✅ |
| dc76a66f-f6d | .../paper/dc76a66f-f6d/ | ✅ | ✅ |
| e6e37f06-1f7 | .../paper/e6e37f06-1f7/ | ✅ | ✅ |

**structured.json 内容**：含 `metadata`、`keywords`、`figures`（image_path 如 `figures/a94f4804-9b0_page_1.png`），说明 `extract_figures` 已执行。

**PDF 与 figures**：下次运行测试时，`_print_storage_verification` 会检查并打印 `PDF 存在/缺失` 及 `figures/*.png 数量`。

---

### 2. 测试日志

**日志文件**：`tests/logs/quantum_physics_three_papers_20260227_232612.log` ✅

**Markdown 输出**：
- `tests/logs/outputs/analysis_2511_00150v1_pdf_20260227_233012.md` ✅
- `tests/logs/outputs/analysis_2601_00062v1_pdf_20260227_233434.md` ✅
- 第三篇（2601.00077v1）在终端截断时仍在入库，对应 md 可能稍后生成

---

### 3. 存储规范核对

| 规范项 | 值 |
|--------|-----|
| 路径结构 | `{storage_dir}/{user_id}/{agent_id}/{scene}/{record_id}/` |
| original_path | `paper/{record_id}`（无前导 `user_id/agent_id`） |
| file_name | 原始 PDF 文件名（如 2511.00150v1.pdf） |
| 测试存储 | `database/memu_storage_test` |
| 默认存储 | `database/memu_storage` |

---

### 4. 建议自检（PDF 与 figures）

若下载失败，可手动检查各 `paper/{record_id}/` 目录是否包含：
- 对应 PDF 文件
- `figures/` 目录及 PNG 文件

`paper_ingest` 应执行：`shutil.copy2(path, folder/path.name)` 与 `extract_figures(..., folder)`。
