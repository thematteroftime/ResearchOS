# 论文提取流程设计：PyMuPDF + LLM 校验 + 图像理解

> **状态**：已确认，实施中  
> **参考**：ex.py、pdf_code.py、paper_web/backend.py、BACKEND_MODULE_DESIGN.md、DESIGN_ARCHITECTURE.md

---

## 一、设计目标

1. **pre_extracted 采用 PyMuPDF**：用保证准确性的专用库（PyMuPDF）+ LLM 校验做首轮文本/图像提取。
2. **公式 vs 文字**：文字不易出错，公式易出错；由大模型对提取文本做二次校验，重点评估并修正公式部分。
3. **意图识别后置**：放在文字提取之后，用前约 1000 字（摘要段）作为意图识别的输入。
4. **图像理解**：参考 paper_web 格式，将图片与文字图注、提取参数关联，为后续 Markdown 撰写提供图片信息和位置。

---

## 二、流程变更（场景一：论文上传分析）

### 2.1 新旧流程对比

| 步骤 | 原流程 | 新流程 |
|------|--------|--------|
| 0 | 意图识别（文件名 + user_question） | **PyMuPDF 原始提取**（文本 + 图像） |
| 1 | 文本结构化（DashScope file-extract + 双阶段） | **意图识别**（raw_text[:1000]） |
| 2 | 图像/图注（从 structured.figures 占位） | **LLM 公式校验**（评估并修正公式部分） |
| 3 | 用户问题 + memU 融合 | **文本结构化**（以修正后文本为输入，agent 模板） |
| 4 | 文献扩展 query | **图像理解**（paper_web 格式：caption + linked_parameters） |
| 5 | 入库 | 用户问题 + memU 融合、文献扩展、入库（逻辑不变） |

### 2.2 新流程详细说明

```
Step 0: PyMuPDF 提取
  - extract_raw_with_pymupdf(file_path) → raw_text, pages, images
  - raw_text: 全文（页级拼接）
  - images: [{page, path, image_path, filename}]

Step 1: 意图识别
  - input = raw_text[:1000]（摘要段）
  - intent_to_agent_ids(input_text=..., file_name=...)
  - agent_ids, main_agent

Step 2: LLM 公式校验
  - verify_formulas_with_llm(raw_text, agent_id=main_agent)
  - 模型评估并修正公式部分，文字保持
  - corrected_text

Step 3: 文本结构化（agent 模板）
  - 输入：corrected_text（不再用 file-extract 读 PDF）
  - extract_paper_structure(..., raw_text_input=corrected_text)
  - 双阶段：S1 对 corrected_text 做标签提取 → S2 转为 JSON
  - structured（含 parameters、force_fields 等）

Step 4: 图像理解（paper_web 格式）
  - extract_figures(file_path, structured, storage_folder)
  - 对每页/每图：提取图像、VLM 生成 caption + linked_parameters
  - 格式：{id, caption, page, linked_parameters, image_path}
  - 合并到 structured.figures

Step 5–7: 用户 memU 融合、文献扩展、入库（与当前一致）
```

---

## 三、模块职责与接口

### 3.1 新增模块：pdf_extract.py

| 函数 | 说明 |
|------|------|
| `extract_raw_with_pymupdf(file_path, output_image_dir)` | PyMuPDF 提取全文与图像，返回 raw_text、pages、images |
| `verify_formulas_with_llm(raw_text, agent_id, max_chars)` | 大模型校验并修正公式部分，返回 corrected_text |

**依赖**：PyMuPDF（已入 requirements.txt）、agent_config.invoke_model

### 3.2 paper_ingest.py 变更

| 变更 | 说明 |
|------|------|
| `extract_paper_structure` 新增 `raw_text_input` | 当提供时，S1 不再用 file-extract，而是直接对 raw_text 做标签提取 |
| `extract_figures` 新增 | 参考 paper_web.extract_figures，按页导出图像 + VLM 标注，返回 paper_web 格式 figures |

### 3.3 图像数据结构（paper_web 格式）

```json
{
  "id": "page-1",
  "caption": "一句话物理/内容说明",
  "page": 1,
  "linked_parameters": ["symbol1", "name2"],
  "image_path": "figures/<pdf_stem>/page_1.png"
}
```

- **image_path**：相对路径（含 record_id 便于回溯）；存于 `.../paper/<record_id>/figures/`
- **linked_parameters**：与 structured.parameters 中符号/名称对应，用于参数推荐与写作时引用

### 3.4 agent_config 新增步骤

- `paper_ingest.formula_verification`：公式校验所用模型（建议 qwen-plus）

### 3.5 已确认决策（2025 实施）

| 项 | 结论 |
|----|------|
| Q1 pre_extracted | 仍指 structured JSON；raw/corrected_text 仅作 pipeline 中间态；使用专用库 + LLM 校验保证准确性 |
| Q2 多 agent | 公式校验仅 main_agent 做一次，其余 agent 共用 corrected_text |
| Q3 图像目录 | 存于 `.../paper/<record_id>/figures/`，image_path 用 record_id 便于回溯查询 |
| Q4 prompt 入 config | formula_verification.txt 与意图识别 prompt 同级（`config/prompts/`） |
| Q5 图像展示 | 首版整页截图；预留扩展接口供后续 PyMuPDF 精确提取图片并与文字、参数对应 |
| Q6 file-extract | PyMuPDF 文本可交给 qwen-long 作为核对文本；保留回退：PyMuPDF 失败时使用原 file-extract 流程 |
| Q7 回退机制 | 必须实现；PyMuPDF 不可用或提取失败时回退到 DashScope file-extract |

---

## 四、数据流示意

```
PDF 文件
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│  pdf_extract.extract_raw_with_pymupdf                     │
│  → raw_text, pages, images                                │
└─────────────────────────────────────────────────────────┘
    │
    ├── raw_text[:1000] ──► intent_to_agent_ids ──► agent_ids
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│  pdf_extract.verify_formulas_with_llm(raw_text)           │
│  → corrected_text                                        │
└─────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│  paper_ingest.extract_paper_structure(raw_text_input=..) │
│  → structured（含 parameters、metadata 等）               │
└─────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│  paper_ingest.extract_figures(file_path, structured)      │
│  → figures: [{id,caption,page,linked_parameters,image_path}]│
│  合并入 structured.figures                                │
└─────────────────────────────────────────────────────────┘
```

---

## 五、疑问与决策点（需确认后实施）

### Q1. pre_extracted 与 agent 模板的关系

- 当前 `paper_ingest_pdf` 的 `pre_extracted` 为「已结构化 JSON」（extract_paper_structure 输出）。
- 新流程中，PyMuPDF + 公式校验得到的是**纯文本**，需经 agent 模板才能变成 structured JSON。
- **建议**：`pre_extracted` 仍指「structured JSON」；新增中间产物 `raw_text` / `corrected_text` 不入库，仅作 pipeline 中间态。是否同意？

### Q2. 多 agent 时的文本与公式校验

- 若 `intent_to_agent_ids` 返回多个 agent，公式校验是否对每个 agent 各做一次，还是只用 main_agent 做一次共用？
- **建议**：仅 main_agent 做一次公式校验，后续各 agent 共用 `corrected_text`。是否同意？

### Q3. 图像导出目录与 image_path 约定

- paper_web 将图像存于 `<PROJECT_ROOT>/figures/<pdf_stem>/page_N.png`。
- merge_project 的 storage 为 `MEMU_STORAGE_DIR/user_id/agent_id/paper/<record_id>/`。
- **建议**：图像存于 `.../paper/<record_id>/figures/`，`image_path` 为相对该目录或相对 storage 根的路径，便于 record 自包含。是否同意？

### Q4. 公式校验的 prompt 是否入 config

- 当前 `verify_formulas_with_llm` 的 system prompt 写死在代码中。
- **建议**：抽到 `config/prompts/_default/formula_verification.txt`，与其它 paper_ingest 步骤一致。是否同意？

### Q5. 整页截图 vs 精确图表裁剪

- paper_web 对每页做整页截图（`page.get_pixmap()`），未做图表区域精确裁剪。
- **建议**：首版沿用整页截图，后续可扩展为图表区域检测再裁剪。是否同意？

### Q6. 与 DashScope file-extract 的并存策略

- 新流程以 PyMuPDF 文本为主，不再用 file-extract。
- 若需「PDF 原文 + 模型直接读」能力（如多模态理解），是否保留 file-extract 作为可选路径（如通过参数 `use_file_extract=True` 切换）？还是完全移除 file-extract 依赖？

---

## 六、兼容与回退

| 情况 | 回退行为 |
|------|----------|
| **PyMuPDF 不可用或提取失败** | 回退到 DashScope file-extract 流程；意图识别用 file_name 或 user_question |
| **公式校验失败** | 保留 raw_text 不做修正，后续流程照常 |
| **VLM 图像理解不可用** | figures 使用占位 caption（如「第 N 页整页快照」），linked_parameters 为空 |
| **raw_text_input 未提供** | extract_paper_structure 使用原有 file-extract 逻辑 |
