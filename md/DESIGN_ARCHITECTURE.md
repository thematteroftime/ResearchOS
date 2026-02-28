# 多 Agent 联合分析科研学习平台 — 详细设计架构文档

> **定位**：多 agent 联合分析的科研学习平台，支持论文阅读、实验模拟、写作与记忆查询；所有能力以 agent_id 区分模板与记忆格式，统一经 memU 记录与本地 DB 溯源。  
> **实施状态**：四场景已实施并通过验证，详见 [IMPLEMENTATION_STATUS.md](./IMPLEMENTATION_STATUS.md)。

**参考**：merge_project 实现与测试、[memU 官方文档](https://memu.pro/docs)、[claude-scientific-writer](https://github.com/K-Dense-AI/claude-scientific-writer)。

---

## 一、总体架构

### 1.1 系统边界与目标

- **平台角色**：为科研用户提供「论文上传分析 → 精简化阅读 + 记忆」「论文写作」「参数推荐」「记忆与源文件查询」的闭环；所有任务均写入 memU 并落库路径，便于溯源与下载。
- **多 Agent 策略**：以 **agent_id** 区分领域（如 physics_agent、cs_agent、chemistry_agent、_default 等）。意图识别（小模型）根据输入/文件名给出 agent_id 列表；后续模板（prompt）、memU 的 memory_types/categories、检索配置均按 agent_id 从 config 加载。
- **统一约束**：
  - 所有调用模型 API 的提示词放在**独立 config/prompts 目录**下，按 agent_id 分子目录，便于修改与扩展。
  - 所有场景产生的「任务记录」均写入 **memU**（conversation 形式 + override_config），并在**本地 DB** 中保存 scene、task_id、user_id、agent_id、相对路径等，用于源文件与结果文件的定位与下载。
  - 部署时：路径最终可转换为 **URL**，便于前端跳转与下载。

### 1.2 与现有项目的关系

- **merge_project**：作为当前后端与 config 的基底。final_project 的设计在此之上做「场景细化、流程扩展、三线程/多线程与外部能力整合」，不推翻已有 agent_config、memu_client、paper_ingest、parameter_recommendation、scientific_writer_client 等，而是明确各场景的输入/输出/子步骤及与 memU、DB、prompt 的对应关系。
- **memU**：云端 v3 API（memorize / retrieve）或自建 MemoryService；用于记忆写入与检索，override_config 来自 config（memu_scenarios.json + tasks）。
- **claude-scientific-writer**：论文写作能力来源；通过封装其 API（含 research-lookup 等）提供写作与可选联网扩展。
- **输出物**：本设计文档落在 **final_project**；后续实现代码可仍在 merge_project 中扩展，或部分迁至 final_project 与前端一起交付。

### 1.3 核心数据流概览

```
用户/前端
    │
    ├─ 场景一：PDF + 用户文本 → 意图识别 → 多线程(文本提取 | 图像理解 | 用户输入+memU) → 扩展检索 → 大模型整合 → .md + .json → memU + DB
    ├─ 场景二：格式+场景+用户输入+数据 → 记忆增强输入 → (可选)多模态规范化 → scientific-writer → PDF → peer_review/summary → memU + DB
    ├─ 场景三：期望现象+参数+可选文件 → memU 检索 → 联网扩展 → 长文本模型推荐 → .md → memU + DB
    └─ 场景四：用户问题 → memU retrieve → task_id/user_id/agent_id → DB 查路径 → 源文件链接/URL
```

---

## 二、场景一：论文上传分析

### 2.1 目的与价值

- **精简化阅读**：从 PDF 中提取关键点（参数与含义/单位、背景、创新点、公式、实验数据、数据分析等），输出便于快速阅读的 Markdown 与结构化 JSON。
- **记忆与行为沉淀**：将论文元数据、提取结果及用户个人理解写入 memU，并与本地 DB 关联，用于后续推荐、参数推荐与偏好分析（科研向：研究问题、阅读论文、会议记录等）。

### 2.2 输入与输出

| 项目     | 说明 |
|----------|------|
| **输入** | 论文 PDF；用户输入文本（对论文的理解与想法，可选，建议走多模态大模型以更好结合上下文）。 |
| **输出** | Markdown 格式阅读文件；JSON 结构化文件；memU 记忆条目；DB 中的 record（含 task_id、路径）。 |

### 2.3 存储与展示约定

- **自然语言理解与内部处理**：优先使用 **Markdown**（便于模型与后续卡片化）。
- **网页端呈现与结构化交换**：使用 **JSON**（便于前端组件、筛选与卡片式阅读）。
- **当前阶段**：前端可先用 **Markdown 阅读器** 展示；后续支持用户自定义 prompt 时，可将「各参数模块」作为卡片配置，仍以 JSON 驱动展示。
- **存储**：同一任务同时落盘 **.md** 与 **.json**；路径写入 DB，memU 中存摘要/描述性内容用于检索。

### 2.4 流程分解（按步骤）

#### 步骤 1：意图识别与 agent_id 确定

- **输入**：PDF 元信息（如文件名、可选首段/摘要）及用户输入文本（若有）。
- **实现方式**：小模型意图识别模块（如 qwen-turbo），输入合并后调用 **intent_to_agent_ids**。
- **输出**：`agent_ids: List[str]`，例如 `["physics_agent"]` 或 `["physics_agent", "cs_agent"]`（计算机辅助物理时双 agent，主领域优先，后续 prompt 与主 agent 对齐）。
- **配置**：意图分类系统提示词放在 `config/prompts/intent_classification_system.txt`（或按现有 merge_project 约定），模型名等可在 config 或 env 中配置。

#### 步骤 2：三路并行处理

在得到 agent_ids 后，对**主 agent**（或多 agent 分别执行后再合并）启动三条并行线：

**线程 A：论文文本管线**

1. **XML/结构化提取**：用长文本模型（如 qwen-long）将 PDF 正文转为结构化文本（XML 或与 config 一致的标签格式）。格式可由 `config` 提供模板，或允许用户偏好「更偏自然语言」的格式再由小模型转成统一结构。
2. **JSON 结构化**：在上一阶段输出基础上，用小模型（如 qwen-plus）快速抽取为 JSON（metadata、参数、创新点、方法、图表索引等）。  
   - 字段需与 agent_id 对应模板一致：physics_agent 含物理背景、物理参数等；_default 仅通用字段（标题、作者、摘要、创新点等）。
3. **输出**：论文文本理解结果（可存为 `paper_text.json` / 中间 XML）。

**线程 B：论文图像管线**

1. **图像识别**：对 PDF 中插图进行解析（多模态 API），提取图中实验数据、曲线、标注等。
2. **与公式/数据一致性**：用于校验正文中 LaTeX 公式与实验数据描述的准确性，避免提取错误。
3. **输出**：论文图像理解结果（可存为 `paper_figures.json` 或并入主 JSON 的 `figures` 数组）。

**线程 C：用户输入 + memU 增强**

1. **检索**：用当前用户输入（及可选论文标题/摘要）在 memU 中 **retrieve**（user_id、agent_id 对应已选 agent），获取相关记忆（研究问题、阅读论文、会议报告等）。
2. **融合**：将检索到的记忆条目与用户输入一起交给 LLM，生成「结合过往记录的用户输入」摘要或改写（如 100 字内描述），便于后续与论文理解一起送入最终整合。
3. **提示词**：放在 `config/prompts/<agent_id>/user_input_memory_fusion.txt`（或统一命名），便于按领域调整「研究问题 / 阅读论文 / 会议记录」等类别权重。

#### 步骤 3：相关领域扩展（可选）

- 使用 **claude-scientific-writer** 的实时相关论文查询能力（如 research-lookup），对「论文主题 + 用户输入」做一次扩展检索，得到若干相关文献摘要或链接。
- 结果作为「扩展上下文」参与步骤 4，不写回 memU 主记忆，仅作当次分析增强。

#### 步骤 4：大模型整合与 Markdown 生成

- **输入**：论文文本理解（线程 A）、论文图像理解（线程 B）、融合后的用户输入（线程 C）、以及可选的相关文献扩展结果。
- **模型**：强能力模型（如 Google Gemini 3.1 或配置中的 OPENROUTER_HIGH_TIER_MODEL），若需可支持「原 PDF + 多模态」输入（依 API 能力）。
- **提示词**：按领域（agent_id）从 `config/prompts/<agent_id>/paper_final_summary.txt` 加载；理科场景需明确要求：参数及含义与单位、背景、创新点、数学公式、实验数据、数据分析、以及「结合用户需求给出的建议」等。
- **输出**：最终 **Markdown** 阅读文档；同时可生成或更新 **JSON**（与现有 paper_ingest 的 structured 兼容或扩展）。

#### 步骤 5：memU 记忆与 DB 落库

- **memU**：将本次任务的「摘要描述」（论文标题、主要创新点、用户关注点、最终 .md 路径或内容摘要）以 **conversation** 形式写入 memorize；override_config 使用该 agent 下 `paper_ingest` 的 memory_types/categories（knowledge 等）。
- **DB**：写入 record（record_id、task_id、scene=paper、user_id、agent_id、相对路径：如 `paper/<record_id>/` 下 pdf、structured.json、final.md 等），便于场景四按 task_id 反查路径与生成下载链接/URL。

### 2.5 多 Agent 交叉分析扩展

- 若意图识别返回多个 agent_id（如 physics_agent + cs_agent）：  
  - 可为每个 agent 各跑一遍「文本 + 图像」提取（使用各自 agent 的 paper_extraction_s1/s2、figure_caption 等 prompt），得到多份 per-agent 的 structured。  
  - 最终整合阶段可指定「主 agent」（如物理优先），在最终 Markdown/JSON 中标注哪些结论来自哪个 agent，或合并为一份以主 agent 结构为主的文档，并在 DB 中记录多 agent 联合的 record_id 关联（预留字段即可）。

### 2.6 事实标注、批注视图与项目导向阅读

为满足「**帮用户快速抓住与自己项目最相关的事实，并且每条事实都能在原文中追溯**」的目标，论文解析结果的设计需满足以下要求：

- **事实级结构化 + 溯源信息**：
  - 在最终 JSON 中，除高层字段（metadata/methodology/figures 等）外，还应为每一条重要「事实」增加类似结构：

    ```json
    {
      "fact_id": "f_001",
      "text": "该实验在 300 K 下测量了粒子间相互作用势，观察到 ...",
      "source_refs": [
        {
          "page": 5,
          "section": "3.1 Experimental setup",
          "paragraph_index": 2,
          "offset": [120, 210]
        }
      ],
      "tags": ["参数:温度", "实验条件", "等离子体"],
      "relevant_to": ["current_project", "parameter_recommendation"]
    }
    ```

  - `source_refs` 记录该事实在 PDF 中的页码、章节、小节或段落范围，便于前端在阅读器中高亮 / 跳转；
  - `relevant_to` 可由 LLM 结合 memU 记忆与当前项目意图打标签，标出这条事实对哪些任务（快速阅读/参数推荐/写作）有用。

- **Markdown 批注视图**：
  - 生成的 Markdown 不仅是「总结」，还应体现「**带链接的批注**」：
    - 在正文中为关键结论添加脚注或内联标注，例如：
      - `实验在 300 K 下进行[^f_001]`，脚注中提示「见原文 p.5, Sec.3.1」；
      - 或在段落后附上括号形式的来源 `(见原文 p.5 Sec.3.1, f_001)`。
  - 阅读器可以提供「**高亮事实 → 跳转原文**」的操作，方便有经验的用户快速回到 PDF 原文进行二次确认。

- **多层视图：快速浏览 / 细读 / 项目导向视图**：
  - **快速浏览视图**：只展示标题、摘要精炼版、图表缩略图和少量关键结论，类似「熟练科研人员读标题 + 摘要 + 图」的习惯；
  - **细读视图**：展开所有事实、公式、方法细节，每条都带溯源信息；
  - **项目导向视图**：结合当前项目（从 memU 中获取项目记忆），只筛选与「当前项目目标」最相关的事实，并按「**对当前工作有什么用**」进行分组，如：
    - 「可以直接用作参数范围依据的事实」
    - 「提供新方法 / 新架构灵感的事实」
    - 「与当前设备/平台类似的实验条件」

- **默认模板 vs 用户定制需求**：
  - 若用户未明确说明需求，则使用「默认模板」提取，覆盖常规科研阅读所需的字段（题目、摘要、方法、主要结论、关键参数与图像）；
  - 若用户在上传时明确给出「当前项目目标 / 自己关心的点」，则在线程 C 中先将这些需求与 memU 记忆融合，生成「项目导向意图」，再作为 system / user 提示词的一部分传给 Qwen / Gemini 等模型，使提取与重组过程始终围绕用户目标进行。

---

## 三、场景二：论文写作

### 3.1 目的与价值

- 复用 **claude-scientific-writer** 的写作与格式能力，根据用户选择的格式、场景、用户输入与数据，生成初版论文（PDF）。
- 将写作任务与结果（peer_review.md、summary.md）写入 memU，便于后续检索与溯源。

### 3.2 输入与输出

| 项目     | 说明 |
|----------|------|
| **输入** | 格式（Nature/Science/IEEE 等）；场景（基金申报、论文撰写、海报等）；用户输入文本；数据文件（如 .md/.png/.csv/.pdf 等）。 |
| **输出** | PDF 文档；可选 peer_review.md、summary.md；memU 写作事件记忆；DB 记录（job_id、输出路径）。 |

### 3.3 流程分解

1. **格式与场景选择**：与 merge_project 一致，从 `VENUE_FORMATS`、`PROJECT_TYPES` 等配置提供选项（参考 claude-scientific-writer README），映射到 scientific-writer 的 query 风格（如 "Create a Nature paper on ..."）。
2. **用户输入增强**：与场景一类似，用 memU **retrieve**（user_id、agent_id）得到相关记忆，再通过 LLM 将「用户输入 + 记忆」融合为一段规范化的写作意图描述（可复用场景一的「用户输入 + memU」提示词或单独写作用 prompt）。
3. **输入规范化（可选）**：使用多模态大模型（Google / Qwen 等，不写死，配置项选择）将用户输入与数据文件列表关联，生成符合 scientific-writer 示例语法的英文 query（如 "Present ... from results.csv, Include figure1.png"），确保模型正确理解数据用途；用户可选择跳过此步，直接使用上一步描述。
4. **调用 scientific-writer**：使用封装好的 `ScientificWriterClient`（或等价 API）传入规范化后的 query、venue、project_type、data_files 等，执行 `generate_paper`；轮询或回调得到完成状态与输出目录。
5. **输出与记录**：  
   - 确定 PDF、peer_review.md、summary.md 的最终路径；  
   - 将「写作任务描述 + 输出路径摘要」以 conversation 形式写入 memU（writing 任务，event + knowledge）；  
   - DB 写入 record（scene=writing_event，job_id、output_pdf、output_tex、query、data_files 等），便于场景四按任务查询与下载。

### 3.4 配置与扩展

- 写作相关 prompt（如「用户输入与记忆融合」「多模态规范化」）放在 `config/prompts/<agent_id>/writing_*.txt`；格式与项目类型仍由 backend/config 的 VENUE_FORMATS、PROJECT_TYPES 管理，预留添加自定义格式/类型的接口。

---

## 四、场景三：参数推荐

### 4.1 目的与价值

- 结合「过往模拟记录」与「已上传论文知识」，对用户给出的期望现象与待模拟参数，给出数值区间、模拟环境、推荐工具（如力场、LAMMPS、GPUMD 或实验设备）及推荐原因；
- 不仅输出「参数区间」，还要**帮助用户设计合理的实验/模拟流程**：
  - 软件层面：仿真平台选择（GPUMD/LAMMPS/自研代码等）、数值算法/架构建议（如积分器、并行方式、收敛判据）；
  - 硬件/实验层面：实验装置配置（温度/压力/场强等控制量）、传感器/测量手段安排；
  - 方法创新：在已有文献与记忆基础上提出可行的新方法、新流程或新概念，给出风险与预期收益；
- 整体相当于协助用户「撰写实验（或计算）方案 + 实验报告草稿」，为实际工作落地服务。

### 4.2 输入与输出

| 项目     | 说明 |
|----------|------|
| **输入** | 用户期望现象（文本）；用户希望模拟的参数及其含义与单位；可选：论文 PDF 或其他文本文件（如 .docx）。 |
| **输出** | Markdown：用户期望现象、实验参数、实验装置、参数数值区间、推荐原因、相关链接与资料；memU 记忆；DB 记录。 |

### 4.3 流程分解

1. **用户输入与 memU**：用当前「用户期望现象 + 参数列表」在 memU 中 **retrieve**，得到过往实验记录、相关论文记忆等；可选将本次用户输入先做一次「记忆更新」（简短 conversation 写入），再检索，以增强后续推荐的相关性。
2. **联网扩展**：参考 scientific-writer 的 research-lookup 或同类能力，对「期望现象 + 参数」做一次相关文献/资料查询，限制条数（如约 10 条），与 memU 结果一起作为上下文。
3. **长文本模型推荐**：将「用户输入 + memU 检索结果 + 联网结果 + 可选上传文件内容」交给长文本模型（如 qwen-long），按 agent_id 使用 `parameter_recommendation` 的 system prompt 与模板，输出结构化 Markdown，包括但不限于：
   - 用户期望现象与目标；
   - 实验/模拟参数列表及推荐数值区间（标注参考文献/记忆 ID）；
   - 推荐的模拟/实验平台（软件 + 硬件）；
   - 建议的实验/模拟流程步骤（step-by-step），包括准备 → 预热/调参 → 正式运行 → 数据采集与分析；
   - 若适用，给出可能的改进方向/新方法草案，并明确哪些部分风险较高；
   - 推荐原因与相关链接资料（memU 记录 / 文献 URL 等），确保每一条建议都有可追溯的依据。
4. **memU 与 DB**：将本次推荐的摘要（或关键结论）以 conversation 写入 memU（parameter_recommendation 的 knowledge + behavior）；DB 写入 record（scene 可为 parameter_recommendation 或独立 scene 名），路径指向生成的 .md 文件，便于场景四查询与下载。

### 4.4 配置

- 参数推荐提示词与模板在 `config/prompts/<agent_id>/parameter_recommendation.txt`、`parameter_recommendation_system.txt`；与 merge_project 现有 parameter_recommendation 模块对齐，默认 agent 使用 _default 模板，意图明确时使用对应领域 agent 模板。

---

## 五、场景四：记忆查询与源文件获取

### 5.1 目的与价值

- 用户通过自然语言查询「过往上传的数据、论文与记忆」，获得相关 memory 记录及**原文件链接或下载方式**；部署时支持将路径转为 URL，便于浏览器跳转或下载。

### 5.2 输入与输出

| 项目     | 说明 |
|----------|------|
| **输入** | 用户问题（自然语言）。 |
| **输出** | 相关 memory 记录列表；每条记录对应的 task_id、user_id、agent_id；原文件/结果文件的链接或下载 URL。 |

### 5.3 流程分解

1. **retrieve**：用用户问题调用 memU **retrieve**（user_id、agent_id 可按当前登录用户与可选 agent 过滤），得到 categories、items、resources；其中业务侧需保证写入 memorize 时在 conversation 或描述中携带 **record_id** 或可解析的 **task_id**（如 [MEMU_REF record_id=xxx scene=paper ...]）。
2. **解析 task_id / record_id**：从 retrieve 返回的 items 或描述中解析出 record_id 或与 DB 对应的 task_id。
3. **DB 查路径**：用 task_id、user_id、agent_id 在本地 DB 的 memu_records 表中查询对应记录的「相对路径」或「simplified_path」等字段；若存储规范为「scene 作文件夹、task_id/record_id 作子路径」，则可直接拼出相对路径。
4. **生成链接**：  
   - **本地/开发**：返回绝对路径或 file:// 链接供前端展示与下载。  
   - **服务器部署**：将相对路径映射为可访问的 **URL**（如 /api/download?task_id=xxx&user_id=xxx&agent_id=xxx），后端根据 task_id/user_id/agent_id 鉴权后重定向到文件或返回文件流。  
   - 前端展示：每条 memory 附带「查看精简版」「下载原文件」等按钮，对应不同 URL 或路径。

### 5.4 与现有 MemUClient 的对应

- merge_project 的 MemUClient 已支持 insert_record、按 record_id/task_id 查询、下载到本地等；场景四在设计中明确「retrieve 返回 → 解析 ID → DB 查路径 → 生成 URL」这条链即可，实现时复用现有 DB 表结构与下载接口，仅需统一「写入 memorize 时的描述格式」以便解析 task_id/record_id。

### 5.5 单库方案：memU OSS 作为唯一记忆与资源层

若**仅使用 memU OSS**（自建 MemoryService + SQLite/Postgres），可将 memU 自带的 DB 同时作为「记忆层 + 资源层」，实现**一次 retrieve 直接拿到资源与路径**，无需再维护本地 `memu_records` 表或做「解析 record_id → 查 DB」的后续步骤。

**原理简述**

- memU OSS 的数据库（见 `memU/docs/sqlite.md`）中：
  - **资源层**：`sqlite_resources` 存 Resource（`id`、`url`、`local_path`、`modality`、`caption`、`embedding` 等）；
  - **记忆层**：`sqlite_memory_items`、`sqlite_memory_categories` 等，且 MemoryItem 有 `resource_id` 关联到 Resource。
- 在 **memorize** 时：除写入 conversation 抽取的 memory items 外，将「源文件路径」或可解析的 URL 通过 **Resource** 写入（例如调用 MemoryService 时传入 `resource_url`/对应 path，由 memU 写入 `sqlite_resources` 的 `local_path`/`url`）。
- 在 **retrieve** 时：配置 `resource.enabled = true`，memU 会按相关性返回 `resources[]`；OSS 实现中 `_materialize_hits` 会带出完整 Resource 的序列化（含 `local_path`、`url`），因此**一次 retrieve 即可得到「记忆条目 + 关联资源及其路径」**，直接用于生成下载链接或展示，无需再查本地 DB。

**数据流对比**

| 方案 | 记忆/资源存储 | 场景四查询路径 |
|------|----------------|----------------|
| **双库（当前设计）** | memU 存摘要 + MEMU_REF/record_id；本地 DB 存 record_id → 路径 | retrieve → 解析 record_id → 查 memu_records → 得路径 → 生成 URL |
| **单库（memU OSS 唯一）** | 仅 memU OSS：记忆 + Resource（含 local_path/url） | retrieve → 使用返回的 `resources[].local_path` / `resources[].url` 直接生成 URL |

**优势**

- 查询路径简单：无需「memU 返回 → 解析 ID → 再查业务 DB」。
- 记忆与资源在同一套 schema 内，一致性好；扩展字段可放在 Resource 的 `caption` 或（若 OSS 支持）自定义 metadata。
- 适合**纯本地/自建**、且希望「一个库搞定记忆+资源」的场景。

**前提与代价**

- **必须使用 memU OSS**：云端 memU 平台 API 的 `resources` 多为引用/摘要形态，不保证返回你自建的 `local_path`，故「一步到位拿路径」仅在使用自建 MemoryService + 自带 DB 时成立。
- 所有「路径、任务元数据」需按 memU 的 Resource 模型来存（或通过 url/caption 编码）；若需 scene、task_id 等业务字段，可约定写在 caption 或 url 参数中供后端解析。
- 若未来要**同时支持云端 memU + 本地/多端**，则仍需保留「云端记忆 + 本地 DB 存路径」的双轨设计，否则云端侧无法访问你本地 SQLite/Postgres 中的路径。

**实现要点（单库方案）**

- 论文入库/写作/参数推荐等场景在**写入记忆**时，除 conversation 外，调用 OSS 的 memorize 接口**同时写入 Resource**，`local_path` 或 `url` 指向当前任务的目录或主文件；MemoryItem 与 Resource 的关联由 memU 内部维护（如 `resource_id`）。
- 场景四：直接使用 `retrieve()` 返回的 `response["resources"]`，从中读取 `local_path` 或 `url`，经鉴权后映射为下载 URL，无需再查 memu_records。

---

## 六、配置与目录约定

### 6.1 目录结构（建议）

- **config/**
  - **prompts/**  
    - `intent_classification_system.txt`：意图识别系统提示词。  
    - `<agent_id>/`：如 physics_agent、cs_agent、_default。  
      - 论文分析：`paper_extraction_s1.txt`、`paper_extraction_s2.txt`、`paper_figure_caption.txt`、`user_input_memory_fusion.txt`、`paper_final_summary.txt`。  
      - 写作：`writing_user_fusion.txt`、`writing_normalize_query.txt`（可选）。  
      - 参数推荐：`parameter_recommendation.txt`、`parameter_recommendation_system.txt`。  
  - **tasks/**  
    - `paper_ingest.json`、`parameter_recommendation.json`、`project_proposal.json`、`writing.json`：各任务下 per-agent 的 prompt 键名与 memory 配置引用。  
  - **memu_scenarios.json**：per agent_id 的 memory_types、memory_categories、retrieve 的 method/top_k 等；与现有 merge_project 结构兼容。

### 6.2 环境变量与模型选择（中国优先 Qwen，国外优先代理商，结点分离）

- **完整约定**：见 **[ENV_CONFIG.md](ENV_CONFIG.md)** 与 **`.env.example`**。
- **中国模型**：优先使用 **Qwen（DASHSCOPE_*）**；并保留 **Doubao（DOUBAO_*）**、**DeepSeek（DEEPSEEK_*）** 的独立 API_KEY 与 BASE_URL，实现结点分离调用。
- **国外模型**：优先通过 **OpenRouter（OPENROUTER_*）** 或 **ClaudeAI（CLAUDEAI_*）** 等代理商调用；保留 **OpenAI（OPENAI_*）**、**Anthropic（ANTHROPIC_*）** 直连。
- **业务选用**：INTENT_MODEL、CONTEXT_MODEL 建议默认中国（如 qwen-turbo、qwen-long）；高阶验证/整合使用 OPENROUTER_HIGH_TIER_MODEL（如 Gemini）；具体调用哪条结点由 config 或 env 决定，不写死厂商。

### 6.3 DB 与存储路径

- **DB**：继续使用 MEMU_DB（如 memu_records.db），表结构包含 record_id、task_id、scene、user_id、agent_id、original_path、simplified_path、file_name、description、created_at 等；写作任务增加 job_id、query、data_files、output_pdf、output_tex 等。
- **存储目录**：MEMU_STORAGE_DIR 下按 `user_id/agent_id/scene/record_id/` 或 `user_id/agent_id/paper/<record_id>/` 组织；同一任务下 PDF、structured.json、final.md、写作输出 PDF 等均放在该任务目录下，DB 只存相对路径或可推导出的相对路径。

---

## 七、memU 记忆格式与场景映射（对齐 memu.pro 平台与 OSS）

本节基于 memU 平台文档：

- 平台 API：`/api/v3/memory/memorize`、`/api/v3/memory/retrieve` 等（[Platform APIs](https://memu.pro/docs#platform-apis)）；
- OSS Python SDK：`MemoryService`（[Python SDK](https://memu.pro/docs#platform-python-sdk) / [OSS Quick Start](https://memu.pro/docs#oss-quick-start)）；
- 自定义配置：`override_config.memory_types` / `memory_categories` / `retrieve`（[Custom Config](https://memu.pro/docs#platform-custom-config)、[Workflow](https://memu.pro/docs#platform-workflow)）。

### 7.1 统一设计原则

- **memU 作为“工作记录大脑”**：负责存储「任务摘要 + 结构化关键信息」，本地 DB 负责存储「文件路径与任务 ID」；两者通过 `record_id` / `task_id` 关联。
- **平台与 OSS 双模式兼容**：
  - 平台云端：使用 `MEMU_API_KEY`、`MEMU_BASE_URL` 调用 `/api/v3/memory/*`（当前 `MemUClient` 已封装）；
  - OSS 本地：在需要时可用 `MemoryService` 替代或补充，`llm_profiles` 中的 `api_key` 优先使用 **Qwen（DASHSCOPE_*）** 或 **OpenRouter（OPENROUTER_*）**，**不再依赖 OPENAI_API_KEY**。
- **场景级 override_config**：每个 `(agent_id, task_name)` 对应一份 `override_config`：
  - `memory_types`: 使用 `["profile", "event", "behavior", "knowledge"]` 中的子集；
  - `memory_categories`: 在 `memu_scenarios.json` 中按 agent 定义（如 physics_agent 的 `paper_metadata` 等）；
  - `retrieve`: `method="rag"`，`item/category/resource.top_k` 等，按场景合理设定（默认 `top_k=5`）。

### 7.2 平台 memorize / retrieve 请求与返回（统一形状）

- **memorize 请求体（平台）**：

  ```json
  {
    "conversation": [
      {"role": "user", "content": "… 原始任务上下文、带 [MEMU_REF record_id=… scene=…] …"},
      {"role": "assistant", "content": "… 确认 / 总结 …"},
      {"role": "user", "content": "请将本次任务作为长期记忆，用于后续检索。"}
    ],
    "user_id": "user_123",
    "agent_id": "physics_agent",
    "override_config": {
      "memory_types": ["knowledge"],
      "memory_categories": [
        {
          "name": "paper_metadata",
          "description": "Paper title, authors, journal, year, innovation, experiment setup, parameters, force fields"
        }
      ]
    }
  }
  ```

- **memorize 响应（平台）**：返回 `task_id`，实际写入完成需通过 `/memorize/status/{task_id}` 轮询：

  ```json
  {
    "task_id": "memu-task-uuid",
    "status": "PENDING"  // 后续 SUCCESS / FAILED
  }
  ```

- **retrieve 请求体（平台）**：

  ```json
  {
    "user_id": "user_123",
    "agent_id": "physics_agent",
    "query": "最近关于复杂等离子体的论文和实验记录有哪些？",
    "override_config": {
      "method": "rag",
      "item": {"top_k": 5, "enabled": true},
      "category": {"top_k": 3, "enabled": true},
      "resource": {"top_k": 5, "enabled": true},
      "route_intention": false,
      "sufficiency_check": false
    }
  }
  ```

- **retrieve 响应（平台）**：含 `rewritten_query`、`categories`、`items`、`resources`：

  ```json
  {
    "rewritten_query": "用户最近的复杂等离子体相关科研工作",
    "categories": [...],
    "items": [
      {
        "content": "2025-01-02 上传的论文《Dusty plasma ...》，主要研究 ...",
        "memory_type": "knowledge",
        "categories": ["paper_metadata"],
        "resource_ids": ["record_id:abcd1234"]
      }
    ],
    "resources": [
      {
        "id": "record_id:abcd1234",
        "metadata": {"title": "Dusty plasma ...", "source": "paper_ingest"},
        "score": 0.92
      }
    ]
  }
  ```

在本项目中，`MemUClient.retrieve` 已对上述形状做了封装；调用方只需关心 `items` / `resources`，并根据其中的 `record_id` / `scene` 去 DB 中查找文件路径。

### 7.3 各场景的 memory_types / categories 与上传内容

结合 `config/memu_scenarios.json` 与 memU 文档的 Memory Types 定义：

#### 7.3.1 论文入库（paper_ingest）

- **memory_types**：`["knowledge"]`  
- **categories（physics_agent）**：
  - `paper_metadata`：论文题目、作者、期刊、年份、摘要、创新点、实验/数值方法、参数与力场摘要；
  - `other`：无法归类的跨领域信息。
- **上传（memorize.conversation）**：  
  - 来自 `paper_ingest_pdf(...)` 的 `summary_text`（标题、创新点、摘要、方法、关键词、现象/模拟描述、用户备注）；
  - `summary_text` 开头包含 `"[MEMU_REF record_id=... scene=paper file=xxx.pdf]"` 标记；
  - `override_config` 使用 `get_memorize_override_config(agent_id, "paper_ingest")`。
- **下发（retrieve）**：  
  - `items[*].categories` 包含 `paper_metadata`；  
  - `resources[*].metadata.title` / `...source="paper_ingest"`；  
  - 结合 DB 中 `scene="paper"` / `record_id` 定位到 `paper/<record_id>/` 目录，得到 `structured.json`、`final.md`、原 PDF 等。

#### 7.3.2 项目提议（project_proposal）

- **memory_types**：`["event", "knowledge"]`  
- **categories（physics_agent）**：
  - `project_proposal`：项目想法、输入数据源（上传文件列表）、memU 检索结果概要、最终输出/建议摘要；
  - `other`：其它。
- **上传**：

  - conversation 中 `user` 首条包含本次项目需求描述（可由小模型规整为 100 字内描述），并附 `"[MEMU_REF record_id=... scene=proposal ...]"`；
  - 若使用云端平台，则 `override_config.memory_types=["event","knowledge"]`，`memory_categories` 使用 physics_agent 下的 `project_proposal`；
  - 若使用本地 MemoryService，则调用 `create_memory_item(memory_type="event"/"knowledge", memory_categories=["project_proposal"], ...)`。

- **下发**：
  - retrieve 时 `items` 返回最近的项目提议记录，可作为后续自动完善/二次写作/参数推荐的「上文」；  
  - `resources` 提供该项目对应的 record_id 与文件路径（如初步方案文档、自动生成的 summary.md）。

#### 7.3.3 参数推荐（parameter_recommendation）

- **memory_types**：`["knowledge", "behavior"]`  
- **categories**（可以继续沿用 physics_agent 里的 `paper_metadata` / `other`，或在后续为参数推荐新增 `parameter_recommendation` 类别）：  
  - knowledge：参数区间、推荐依据（来自哪些论文/实验）、物理背景；  
  - behavior：用户偏好（如“更偏向保守参数区间”“倾向使用某类力场 / 工具链”）。
- **上传**：
  - conversation 中记录本次输入：期望物理现象、用户提供的参数及含义/单位、选定的力场/模拟平台建议、推荐区间及理由；
  - `override_config.memory_types=["knowledge","behavior"]`；categories 可以沿用 physics_agent 的 `paper_metadata` + `other`，或在 memu_scenarios.json 中为该 agent 后续新增 `parameter_recommendation` category。
- **下发**：
  - retrieve 时返回既往参数推荐记录，可用于：
    - 作为「模板」生成当前推荐（类似 few-shot）；  
    - 展示给用户作为「历史实验记录」；  
    - 让 LLM 对比「历史推荐区间 vs 当前推荐」，输出差异与原因。

#### 7.3.4 写作（writing）

- **memory_types**：`["event", "knowledge"]`  
- **categories（physics_agent）**：
  - `writing_event`：每次 scientific-writer 或其它写作任务的 query、格式/场景选择、数据文件列表、输出路径（PDF / SUMMARY.md / peer_review.md）；
  - `other`：通用。
- **上传**：
  - conversation 中包含：
    - 规范化后的写作 `query`（英文长句，如 scientific-writer README 中的示例）；  
    - 数据文件列表（以文件名 + 角色说明方式呈现）；  
    - 生成结果（paper 目录名、最终 PDF / LaTeX / summary 路径摘要）；  
    - MEMU_REF 标记：`[MEMU_REF record_id=... scene=writing_event ...]`。
  - `override_config.memory_types=["event","knowledge"]`，memory_categories 选 `writing_event`。
- **下发**：
  - retrieve 时 `items` 提供近期写作任务摘要（例如「2026-02，使用 NSF 模板撰写量子计算基金申报书」）；  
  - `resources` + DB 使用户可以直接跳转/下载对应 PDF 或查看 SUMMARY.md / peer_review.md。

### 7.4 模型选择与 memU 后端 LLM（不再依赖 OPENAI_API_KEY）

根据 memU 文档（`llm_profiles` 配置与 Platform / OSS 区分）以及本项目 ENV_CONFIG：

- **云端 memU 平台**：  
  - 使用 `MEMU_API_KEY` 与 `MEMU_BASE_URL` 调用，平台内部自行选择模型与 embedding，无需在本项目中维护 OPENAI_API_KEY；  
  - 我们仅通过 `override_config` 与 `retrieve` 设置 memory_types / categories / method / top_k 等。

- **本地 MemU OSS（MemoryService）**：  
  - 默认示例使用 `OPENAI_API_KEY`，本项目应改为使用：

    ```python
    llm_profiles = {
        "default": {
            "provider": "dashscope",  # 或 "openrouter"
            "base_url": os.getenv("DASHSCOPE_BASE_URL") or "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "api_key": os.getenv("DASHSCOPE_API_KEY"),
            "chat_model": "qwen-long",
        },
        "embedding": {
            "provider": "dashscope",
            "base_url": os.getenv("DASHSCOPE_BASE_URL") or "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "api_key": os.getenv("DASHSCOPE_API_KEY"),
            "embed_model": "text-embedding-v2",
        },
    }
    ```

  - 或者使用 OpenRouter 作为后端：

    ```python
    llm_profiles = {
        "default": {
            "provider": "openrouter",
            "base_url": os.getenv("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1",
            "api_key": os.getenv("OPENROUTER_API_KEY"),
            "chat_model": "google/gemini-3-flash-preview",
        },
        "embedding": {
            "provider": "openrouter",
            "base_url": os.getenv("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1",
            "api_key": os.getenv("OPENROUTER_API_KEY"),
            "embed_model": "openai/text-embedding-3-large",
        },
    }
    ```

  - 如此配置后，本项目在本地模式下的 MemU（MemoryService）也会统一走 Qwen 或 OpenRouter 作为 LLM 与向量后端，避免再单独维护 OPENAI_API_KEY，仅在确实需要 OpenAI 官方模型时才单独配置。

---

## 八、部署与 URL 化

- 所有「原文件」与「结果文件」的访问统一通过 **后端 API** 暴露：  
  - 例如 `GET /api/file?task_id=xxx&user_id=xxx&agent_id=xxx&type=original|simplified|pdf`，后端校验 user_id 后根据 DB 查路径，返回重定向或文件流。  
- 前端「下载」或「打开」仅使用该 URL，便于本地与服务器同一套逻辑；若需直链存储（如 OSS），可在后端将相对路径映射为 OSS URL 再返回。

---

## 九、总结

- **四个场景**：论文上传分析（三线程 + 扩展 + 整合 + memU/DB）、论文写作（记忆增强 + 可选规范化 + scientific-writer + memU/DB）、参数推荐（memU + 联网 + 长文本模型 + memU/DB）、记忆与源文件查询（retrieve → ID → DB → URL）。
- **统一原则**：agent_id 驱动模板与记忆配置；所有 prompt 在 config 下可编辑；所有任务写 memU 并落 DB；文件访问经后端转为 URL，便于部署与权限控制。
- 本设计为**纯架构与流程说明**，不包含具体代码实现；实现时可基于 merge_project 逐步扩展，并在 final_project 中维护本设计文档与后续的接口清单、前端交互说明。

---

## 十、后端模块职责与调用关系

> 详见 **[BACKEND_MODULE_DESIGN.md](./BACKEND_MODULE_DESIGN.md)**

### 10.1 核心约束摘要

| 模块 | 职责 | 约束 |
|------|------|------|
| **app_backend** | 唯一前端入口；意图识别；memU 读写；DB 落库；retrieve 统一接口 | 传 agent_id 及业务参数给业务函数；**不**传 model/api_key/base_url |
| **agent_config** | prompt 加载；**所有模型调用的集中转发**；根据 agent_id 从 config/agents 取模型 | 业务函数传入 agent_id，由 agent_config 按配置选择模型并请求 |
| **memU** (MemUClient) | 记忆管理；源文件溯源 | **仅 app_backend 可调用**；cloud 与 oss **类名/接口一致**，env 选 oss\|cloud |
| **业务模块** | 纯业务逻辑 | 无 memorize、无 DB 写入；接收 agent_id，自行调用 agent_config；memU/DB **全部上移至 app_backend** |
| **config/agents/** | 每 agent_id 一个 JSON，按场景写定 provider 与 model | .env 提供 api_key/url；config 提供模型名 |

### 10.2 数据流要点

- **agent_id 锁定模型**：app_backend 传 agent_id 给业务函数；业务函数调用 agent_config，agent_config 从 `config/agents/<agent_id>.json` 读取该场景的模型配置。
- 业务函数**不**直接调用 memU、**不**直接调用 DashScope/OpenRouter；需要模型输出时，调用 `agent_config.invoke_model(agent_id, task_name, step, messages)`。
- app_backend 在得到业务函数返回结果后，统一执行 memorize 与 DB 落库。

---

## 附录 A：配置与数据溯源速查

### A.1 Prompt 与 Config 目录

| 用途 | 位置 |
|------|------|
| 意图识别 | `config/prompts/intent_classification_system.txt` |
| 论文分析 | `config/prompts/<agent_id>/paper_extraction_s1.txt`、`paper_extraction_s2.txt`、`paper_figure_caption.txt`、`user_input_memory_fusion.txt`、`paper_final_summary.txt` |
| 写作 | `config/prompts/<agent_id>/writing_user_fusion.txt` |
| 参数推荐 | `config/prompts/<agent_id>/parameter_recommendation.txt`、`parameter_recommendation_system.txt` |

未配置的 agent 使用 `_default` 兜底。

### A.2 任务配置（tasks）

- `config/tasks/paper_ingest.json`、`parameter_recommendation.json`、`project_proposal.json`、`writing.json`。

### A.3 存储路径与 DB

- **路径**：`{storage}/{user_id}/{agent_id}/{scene}/{record_id}/`
- **scene**：paper（PDF、structured.json、summary.md）、parameter_recommendation（summary.md、recommendations.json）、writing_event（*.pdf、SUMMARY.md、PEER_REVIEW.md）
- **memu_records**：record_id、task_id、scene、original_path、job_id、query、output_pdf 等；writing_event 扩展 job_id、query、data_files。
- **persist 流程**：生成 record_id → build_storage_path → 写入文件 → 构建 record → memorize（可选）→ insert_record。

### A.4 环境变量

见 **[ENV_CONFIG.md](./ENV_CONFIG.md)** 与 **.env.example**。
