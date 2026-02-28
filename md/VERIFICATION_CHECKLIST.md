# merge_project 整体校验清单

> 用于全流程验证前的快速核对，确保配置与逻辑正确�?

## 一、配置与依赖

| �?| 检�?| 说明 |
|----|------|------|
| .env | 复制 .env.example �?.env，填�?DASHSCOPE_API_KEY �?| 论文提取、意图识别、参数推荐需 DASHSCOPE |
| requirements.txt | pymupdf 已列�?| PyMuPDF 文本/图像提取 |
| 论文 PDF | docs/2601.00062v1.pdf 存在 | 单论文全流程需此文�?|

## 二、模块与文档对应

| 模块 | 设计文档 | 职责 |
|------|----------|------|
| app_backend | BACKEND_MODULE_DESIGN.md | 场景编排、memU、DB |
| paper_ingest | DESIGN_PAPER_EXTRACT_PYMUPDF.md | 提取、结构化、figures |
| pdf_extract | DESIGN_PAPER_EXTRACT_PYMUPDF.md | PyMuPDF 提取、公式校�?|
| agent_config | README_CONFIG.md | 意图、模型、prompt |
| parameter_recommendation | BACKEND_MODULE_DESIGN 7.2 | 参数推荐 |

## 三、场景一流程（paper_analysis_scenario�?

1. PyMuPDF 提取 �?失败则回退 file-extract
2. 意图识别（raw_text[:1000] �?file_name�?
3. LLM 公式校验（main_agent 一次）
4. extract_paper_structure（raw_text_input �?file-extract�?
5. paper_ingest_pdf（含 extract_figures�?
6. 用户 memU 融合、文献扩展、入�?

## 四、全流程测试命令

```bash
cd merge_project
pip install -r requirements.txt
python tests/run_full_flow_single_paper.py
```

日志：`tests/logs/single_paper_full_flow_<时间>.log`

## 五、评估要点（根据 log�?

- PyMuPDF 是否成功提取（`[STEP] pymupdf`�?
- 意图识别 agent_ids（`[STEP] paper_analysis | agents`�?
- 公式校验（`[STEP] paper_analysis | formula_verify`�?
- 文本结构化（`[STEP] paper_analysis | thread_text`�?
- 入库结果（`[STEP] paper_analysis | paper_ingest`�?
- 参数推荐、写作规范化、记忆检�?
