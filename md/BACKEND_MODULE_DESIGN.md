# 后端模块职责与调用关系设�?

> **状�?*：已实施并验证（详见 [IMPLEMENTATION_STATUS.md](./IMPLEMENTATION_STATUS.md)�? 
> **目标**：明�?app_backend、agent_config、memU、业务模块的边界与数据流，实现解耦与职责单一�?

---

## 一、总体原则

1. **app_backend** 为唯一前端入口，负责意图识别、memU 读写、DB 记录；将 **agent_id** 传给业务函数，不传�?model/api_key/base_url�?
2. **agent_id 锁定模型**：各场景使用的模型由 `config/agents/<agent_id>.json` 写定；业务函数接�?agent_id 后，自行调用 agent_config 获取模型并完�?LLM 请求�?
3. **agent_config** 为唯一模型调用中心；根�?agent_id + 场景/步骤�?config 读取模型名，�?.env 读取 api_key/base_url，转发请求�?
4. **memU**（MemUClient）仅�?app_backend 调用；cloud �?oss 实现**类名/接口一�?*，由 env `MEMU_BACKEND=oss|cloud` 选择�?
5. **业务模块**：接收参数（�?agent_id）→ 调用 agent_config �?返回结果�?*�?* memorize�?*�?* DB 写入；memU/DB 逻辑**全部上移�?app_backend**�?
6. **config.py** 管理路径、常量、环境变量；`.env` 配置可用 API key �?URL；`config/agents/` �?agent_id 配置各场景使用的模型名称�?

---

## 二、四场景与数据流

| 场景 | 简要流�?|
|------|----------|
| **场景一** 论文阅读入库 | PDF + 用户问题 �?app_backend 意图识别、memU 检索增�?�?�?agent_id、file_path、user_input �?�?paper_ingest 内部�?agent_id �?agent_config 获取 prompt 与模�?�?返回 structured �?**app_backend** �?memorize + DB 落库 |
| **场景�?* 科研写作 | 格式/类型 + 用户输入 + 数据文件 �?app_backend memU 检索增�?�?�?agent_id �?�?scientific_writer_client 内部�?agent_config（按需）→ 返回 PDF �?�?**app_backend** �?memorize + DB 落库 |
| **场景�?* 参数推荐 | 结构化论�?+ 用户参数 �?app_backend memU 检索得�?memory_context �?�?agent_id、structured_paper、user_params、memory_context �?�?parameter_recommendation 内部�?agent_config �?返回推荐结果 �?**app_backend** �?memorize + DB 落库 |
| **场景�?* 记录查询及源文件下载 | 用户问题 �?app_backend 调用 memU retrieve �?解析 record_id/task_id �?DB 查路�?�?返回记录列表与下�?URL |

---

## 三、app_backend 职责

### 3.1 定位

- 长期运行的服务器端口，与 Gradio 前端持续交互�?
- 接收用户参数，完�?*意图识别、memU 检索增�?*，将 **agent_id** 及业务所需参数传给业务函数�?
- **�?*向业务函数传�?model、api_key、base_url；由业务函数通过 agent_config �?agent_id 自行获取�?

### 3.2 参数准备与传�?

1. **意图识别**（按场景需要）：`agent_config.intent_to_agent_ids` �?`agent_ids`�?
2. **memU 检索增�?*（按场景需要）：调�?memU `retrieve`，形�?`memory_context` 或「增强后的用户输入」，作为参数传入业务函数�?
3. **打包参数**：将 `agent_id`、`user_id`、`file_path`、`user_input`、`memory_context`、`structured_paper` 等业务参数传给下游；**不含** model、api_key、base_url�?
4. **�?agent 场景**：仅�?`agent_ids` 或逐个调用，参数精简，便于管理�?

### 3.3 任务记录与持久化（仅 app_backend 执行�?

- 业务函数返回结果后，app_backend 负责�?
  1. **memU memorize**：将任务摘要、MEMU_REF 等以 conversation 形式写入 memU�?
  2. **本地 DB**：写�?memu_records 表（scene、路径、描述等）�?
  3. **retrieve 统一接口**：提供面向所有场景的 retrieve 函数�?

### 3.4 约束

- 业务函数**�?* memorize 权限�?*�?* DB 写入权限�?
- **全部** memU �?DB 逻辑上移�?app_backend；业务函数仅负责业务逻辑�?agent_config 调用�?

---

## 四、agent_config 职责

### 4.1 定位

- 接收 `agent_id`、`scene`、`step`（或 `task_name`）等，从 `config/agents/<agent_id>.json` �?`config/prompts/` 加载模型配置�?prompt�?
- **集中负责**所有模�?API 调用；业务函数需要模型输出时，调�?agent_config �?API�?

### 4.2 能力清单

| 能力 | 说明 |
|------|------|
| `get_prompt(agent_id, prompt_key, task_name, **format_vars)` | 加载 prompt，agent_specific + default_base 拼接 |
| `get_task_config(agent_id, task_name)` | 获取任务配置（prompt 文件名等�?|
| `get_memorize_override_config(agent_id, task_name)` | 获取 memU memorize �?override_config |
| `intent_to_agent_ids(input_text, file_path, file_name)` | 意图识别，返�?agent_id 列表 |
| `get_model_for_step(agent_id, task_name, step)` | 根据 agent_id + 任务 + 步骤�?config/agents 获取 model、provider |
| `get_client_for_step(agent_id, task_name, step)` | 返回�?config/agents 配置�?OpenAI 兼容 client，供 file-extract 等需直接�?API 的场�?|
| `invoke_model(agent_id, task_name, step, messages, ...)` | 根据 agent_id 配置选择模型�?provider，从 .env �?api_key/base_url，转发请求；支持容错回退 |

### 4.3 模型调用流程

1. 业务函数传入 `agent_id`、`task_name`、`step`（如 `extraction_s1`、`extraction_s2`、`figure_caption`、`parameter_recommendation`）�?
2. agent_config �?`config/agents/<agent_id>.json` 读取该步骤的 `provider`、`model`�?
3. 根据 `provider` �?.env �?`DASHSCOPE_*` / `OPENROUTER_*` / `ANTHROPIC_*` 等�?
4. 发起请求；若失败，按配置进行容错回退（如 qwen 不可用时回退 openrouter 等）�?

---

## 五、config/agents �?.env 分工

### 5.1 .env：可用模�?API �?URL

- 配置�?provider �?api_key、base_url（未配置则不可用）：
  - `DASHSCOPE_API_KEY`、`DASHSCOPE_BASE_URL`（Qwen�?
  - `OPENROUTER_API_KEY`、`OPENROUTER_BASE_URL`
  - `ANTHROPIC_API_KEY`、`ANTHROPIC_BASE_URL`
  - 可扩展：`PERPLEXITY_*` �?

### 5.2 config/agents/<agent_id>.json：各场景使用的模型名�?

- 每个 agent_id 一�?JSON 文件，按**场景/步骤**写定使用�?`provider` �?`model`�?
- 示例结构（按功能划分）：

```json
{
  "paper_ingest": {
    "extraction_s1": {"provider": "qwen", "model": "qwen-long"},
    "extraction_s2": {"provider": "qwen", "model": "qwen-plus"},
    "figure_caption": {"provider": "qwen", "model": "qwen-vl-plus"}
  },
  "parameter_recommendation": {
    "main": {"provider": "qwen", "model": "qwen-long"}
  },
  "paper_integration": {"provider": "openrouter", "model": "google/gemini-2.0-flash-exp"},
  "research_lookup": {"provider": "openrouter", "model": "perplexity/llama-3.1-sonar-large-128k-online"},
  "intent": {"provider": "qwen", "model": "qwen-turbo"}
}
```

- **容错**：若�?provider 不可用（�?.env 未配或请求失败），可回退到同场景的备�?model；回退规则可在 config 或代码中约定�?

### 5.3 场景与模型对应（参考）

| 场景功能 | 典型模型 | provider |
|----------|----------|----------|
| 长文本提�?| qwen-long | qwen |
| 图像理解 | qwen-vl-plus | qwen |
| 论文整合 / 高阶 | gemini-2.0-flash-exp �?| openrouter |
| 资料检�?| perplexity/llama-3.1-sonar-large-128k-online | openrouter |
| 意图识别 | �?5.4，单独配�?| - |

### 5.4 容错与回退

- **兜底配置**：config/agents 缺失或某步骤未配置时，一律使�?qwen 系列模型（最便宜、最方便）�?
- **回退机制**：当指定 provider 未配置（.env �?key）或请求失败时，**一律回退�?qwen 系列模型**（如 qwen-turbo、qwen-plus、qwen-long，按场景选合适的）�?

### 5.5 意图识别配置

- **单独配置**：意图识别使用独立的 `intent_model` 配置（如 .env �?`INTENT_MODEL=qwen-turbo`），**�?*�?`config/agents/<agent_id>.json` 读取�?
- 意图识别�?agent_id 确定之前执行，故不与 agent_id 绑定�?

---

## 六、memU（MemUClient）职责与类名一�?

### 6.1 定位

- memU 作为「大脑」，管理所有记忆条目及源文件溯源路径�?
- 支持 **cloud**（云�?API）与 **oss**（本�?MemoryService）两种实现�?

### 6.2 类名与接口管�?

- **app_backend 中统一实例�?*：在 app_backend 实例化时使用统一变量名（�?`memu`），避免因类名不一致带来管理不便。工�?`create_memu_client(backend=oss|cloud)` 返回可用实例�?
- **env 选择实现**：`MEMU_BACKEND=oss|cloud` 决定调用 cloud（MemUClient）或 oss（MemUOSSClient）�?
- **接口一一对应**：按 memU 官方文档（docs、examples、src）设计适配业务逻辑的函数；cloud �?oss 对外方法（memorize、retrieve、insert_record 等）需一一对应，实现可依各自官方示例撰写�?

### 6.3 调用约束

- **仅有 app_backend 可调�?memU**；业务模块不直接使用 memU�?

### 6.4 接口能力

- `memorize(conversation, user_id, agent_id, override_config, wait)`
- `retrieve(query, user_id, agent_id, override_config)`
- `upload_files`、`register_writing_event`、`insert_record` �?
- 本地 DB：memu_records 表，供检索与下载溯源
- **统一存储路径**：`build_storage_path(storage_dir, user_id, agent_id, scene, record_id)` �?`{storage_dir}/{user_id}/{agent_id}/{scene}/{record_id}/`

### 6.5 各场�?persist 流程（统一形式�?

所有需落库的场景（paper、parameter_recommendation、writing_event、data、image 等）遵循同一模式�?
1. 生成 record_id�?
2. �?`build_storage_path` 创建目标文件夹；
3. 写入场景特定文件（PDF/JSON/MD 等）�?
4. 构建 record（含 original_path=`{scene}/{record_id}`、description 等）�?
5. memorize（可选）�?
6. insert_record�?
详见 DESIGN_ARCHITECTURE.md 附录 A�?

---

## 七、业务模块职�?

### 7.1 paper_ingest

- **输入**（由 app_backend 传入）：  
  - `file_path`、`agent_id`、`user_id`、`storage_dir` 等；**不含** model、api_key、base_url�?
- **逻辑**�? 
  - 调用 `agent_config.get_prompt(agent_id, "extraction_s1", task_name="paper_ingest")` 等获�?prompt�? 
  - 调用 `agent_config.invoke_model(agent_id, "paper_ingest", "extraction_s1", messages)` 完成 LLM 请求�? 
  - 双阶段提取（文本 + JSON 结构化）�? 
  - 返回 `structured`、`extracted_text` 等�?
- **输出**：structured JSON�?*�?*写入 memU�?*�?*写入 DB�?
- **memorize、insert_record**：由 app_backend 在得到结果后执行�?

**扩展设计**：PyMuPDF 预提�?+ LLM 公式校验 + 图像理解（paper_web 格式）详�? 
`DESIGN_PAPER_EXTRACT_PYMUPDF.md`（待确认后实施）�?

### 7.2 parameter_recommendation

- **输入**�? 
  - `structured_paper`、`user_params`、`agent_id`、`memory_context`（由 app_backend �?memU 检索后传入）、`relevant_forces` 等�? 
  - **不含** model、api_key、base_url�?*不含** memu_client�?
- **逻辑**�? 
  - 调用 `agent_config.get_prompt` 获取 prompt�? 
  - 调用 `agent_config.invoke_model(agent_id, "parameter_recommendation", "main", messages)`�? 
  - 解析 JSON 推荐结果�?
- **输出**：`parameter_recommendations`、`force_field_recommendation` 等；**�?*写入 memU�?*�?*写入 DB�?

### 7.3 scientific_writer_client

- **输入**（由 app_backend 传入，且�?*已记忆增强、已规范�?*的内容）�? 
  - `normalized_query`（app_backend 先做 memU 检索增强，再经 agent_config 规范化后的用户输入）、`venue_id`、`project_type_id`、`data_file_names` 等�?
- **流程**（在 app_backend 中）�? 
  1. 接收前端输入�? 
  2. memU retrieve 做记忆增强；  
  3. agent_config.invoke_model（writing.query_normalize）做 query 规范化；  
  4. 将规范化后的 query 传给 scientific_writer_client.generate_paper�? 
- **逻辑**�? 
  - scientific_writer_client 仅调�?scientific-writer �?`generate_paper`，接收已规范化的 query，不再做规范化�? 
- **输出**：PDF 路径、job 状态等�?*�?*写入 memU�?*�?*写入 DB�?

---

## 八、数据流示意

```
┌─────────────────────────────────────────────────────────────────────────────�?
�?                             Gradio 前端                                      �?
└─────────────────────────────────────────────────────────────────────────────�?
                                        �?
                                        �?
┌─────────────────────────────────────────────────────────────────────────────�?
�?                           app_backend                                        �?
�? �?接收场景参数                                                               �?
�? �?intent_to_agent_ids（按需�?                                               �?
�? �?memU.retrieve 用户输入增强（按需�?                                         �?
�? �?�?agent_id + 业务参数 �?调用业务模块（不�?model/api_key/base_url�?         �?
�? �?得到结果 �?memU.memorize + DB 落库                                          �?
�? �?提供 retrieve 统一接口                                                      �?
└─────────────────────────────────────────────────────────────────────────────�?
         �?                   �?                   �?
         �?                   �?                   �?
         �?                   �?                   �?
┌───────────────�?  ┌───────────────────�?  ┌──────────────────────────────────�?
�? agent_config �?  �? MemUClient       �?  �? paper_ingest / param_rec /       �?
�? �?get_prompt �?  �? (oss|cloud 同接�?�?  �? scientific_writer_client         �?
�? �?get_model  �?  �? �?memorize       �?  �? �?接收 agent_id，自行调           �?
�? �?invoke_    �?  �? �?retrieve       �?  �?   agent_config 获取模型并请�?     �?
�?   model      �?  �? �?insert_record  �?  �? �?纯业务逻辑，无 memU/DB          �?
└───────────────�?  └───────────────────�?  └──────────────────────────────────�?
         �?                   �?                   �?
         �?                   �?                   �?
         └────────────────────┴────────────────────�?
                   �?app_backend 调用 memU
                   业务模块只调�?agent_config
```

---

## 九、待确认事项（已按用户反馈更新）

| �?| 结论 |
|----|------|
| agent_id 锁定模型 | app_backend 不传 model；业务函数接�?agent_id 后自行调�?agent_config |
| config/agents/<agent_id>.json | �?agent_id 一�?JSON，按场景/步骤写定 provider + model�?env 提供 api_key/url |
| 兜底与回退 | 缺失或失败时一律回退�?qwen 系列模型 |
| 意图识别 | 单独 INTENT_MODEL 配置 |
| 写作流程 | app_backend �?memU 增强 �?agent_config 规范�?�?再传 scientific_writer |
| MemU 实例�?| app_backend 统一变量名；cloud/oss 按文档一一对应 |
| memU/DB 上移 | **全部** memorize、insert_record 上移�?app_backend |

---

## 十、校验与疑惑（待确认后实施）

### 10.1 代码现状与文档差�?

| 模块 | 现状 | 文档要求 |
|------|------|----------|
| **paper_ingest** | `paper_ingest_pdf` 内含 memorize、insert_record；直接调 `_get_dashscope_client()`；model 写死 qwen-long/qwen-plus | 拆出 `extract_paper_structure` �?app_backend 调用；memorize/DB 上移；改�?agent_config.invoke_model |
| **parameter_recommendation** | `get_memory_context_for_agents` 直接�?memu_client.retrieve；`run_parameter_recommendation` 接收 memu_client；直接调 DashScope | memu retrieve 上移�?app_backend，memory_context 作为参数传入；去�?memu_client 依赖；改�?agent_config.invoke_model |
| **agent_config** | �?get_model_for_step、invoke_model；无 config/agents 读取 | 新增 get_model_for_step、invoke_model；读�?config/agents/<agent_id>.json |
| **config** | �?config/agents/ 目录 | 新增 config/agents/，每 agent_id 一�?JSON |
| **memu_client / memu_oss_client** | MemUClient �?MemUOSSClient 类名不同；MemUOSSClient 继承 MemUClient；部分接口实现不�?| 保证对外方法一致；工厂�?MEMU_BACKEND 返回统一实例 |

### 10.2 已确�?

- config/agents：`_default.json` 作为兜底；缺失时�?qwen�?
- 容错回退：一律回退�?qwen 系列模型�?
- 写作流程：app_backend �?memU 增强 �?agent_config 规范�?�?再传 scientific_writer�?
- MemU：app_backend 中统一实例化；�?memU 文档/examples/src 设计函数，cloud �?oss 一一对应�?
- 意图识别：单�?`INTENT_MODEL` 配置，不�?agent config 读取�?

### 10.3 源码翻阅后的功能与逻辑结论与后续疑�?

经翻�?merge_project、memU 源码�?[memU 官方文档](https://memu.pro/docs) 后，结论如下�?

#### 10.3.1 MemUOSSClient 接口完整�?

- **现状**：仅重写 `memorize`、`retrieve`；`upload_files`、`register_writing_event`、`match_and_resolve` 依赖 HTTP，OSS 下不可用�?
- **实施**：按 memU OSS �?`create_memory_item` + 本地存储，为 MemUOSSClient 补齐等效实现（本地文件复�?+ memu_records DB + MemoryService.memorize），�?cloud/oss 接口一一对应�?

#### 10.3.2 OSS retrieve �?format_retrieve_for_writing 的响应形�?

- **Cloud**：`memories`、`items`、`resources`、`answer`/`summary`；内容取 `it.get("memory", it).get("content", "")` �?`it.get("content", it)`�?
- **OSS**：`categories`、`items`、`resources`；items 来自 `model_dump`，字段为 `summary`（MemoryItem.summary），�?`content`�?
- **实施**：在 MemUOSSClient 中重写或扩展 `format_retrieve_for_writing`，兼�?OSS 形状：items �?`summary`，categories �?`summary`/`description`�?

#### 10.3.3 OSS �?user_id �?agent_id（疑�?3 的结论）

- **DefaultUserModel**（`memU/app/settings.py`）：�?`user_id`；`agent_id` 已注释，但预留扩展�?
- **UserConfig**：`UserConfig.model` 支持自定义模型；MemoryService 接受 `user_config`，`build_database(user_model=...)` �?user_model 字段合并进所�?scoped 表（Resource、MemoryItem、MemoryCategory、CategoryItem），SQLite 会建对应列和索引�?
- **实施**：定�?`UserModelWithAgent(BaseModel): user_id; agent_id`；创�?MemoryService 时传�?`user_config={"model": UserModelWithAgent}`；memorize �?`user_scope={"user_id", "agent_id"}`，retrieve �?`where={"user_id", "agent_id"}`�?
- **注意**：若已有 DB �?DefaultUserModel 建表，需迁移或新�?DB 方能使用 agent_id 列�?

#### 10.3.4 paper_ingest 拆分�?extract �?ingest

- **实施**：拆�?`extract_paper_structure(...)` �?`paper_ingest_pdf(...)`，memorize、insert_record �?app_backend 完成�?

#### 10.3.5 intent_to_agent_ids 的模型来�?

- **实施**：保持从 config/env 读取 `INTENT_MODEL`，不依赖 config/agents�?

---

### 10.4 存储与响应格式对齐（已确认原则）

- **数据库存�?*：memu_records 表结构（record_id、scene、user_id、agent_id 等）�?cloud/oss 下尽量一致；自定义部分统一，便于查询和管理�?
- **官方下发响应**：Cloud API �?OSS MemoryService 返回结构不同时，各自适配或新增格式化函数（如 OSS �?`format_retrieve_for_writing`）�?

---

### 10.5 后续疑问的结论（已确认）

1. **双库 vs 单库**：沿用当前双库设计（memu_records �?ID→路径映射，memU 存记�?ID）。若另起 DB 更便利可考虑，但 cloud/oss 逻辑需更彻底分离；现方案保持双库即可�?

2. **format_retrieve_for_writing 抽象**：在 MemUClient 基类定义抽象方法，由 Cloud �?OSS 各自实现，便于日后重写、减少分支判断�?

3. **memu_records 写入时机**：不�?memorize 成功与否，均写入 memu_records，目的为有迹可循；失败记录也需保存�?

4. **Platform API 容错**：Cloud 模式下需做容错解析；当前以文档为准，实现时主要参考原有代码格式；若实测与文档不符，以原代码为准并补充容错�?

---

### 10.6 实施前可选确认（已确认）

- **memu_records 失败字段**�?*新增** `memu_error` 列，memorize 失败时记录错误信息，便于 traceability�?
- **list_agent_ids 数据�?*：为便于检索与意图识别�?*�?memu_scenarios.json 顶层新增 `agent_ids` 参数**，用于快速统�?agent 数量；`list_agent_ids` 读取该字段�?
- **writing.query_normalize**：query 规范化由 **app_backend 准备**，与其他业务函数一致：使用 agent_id �?agent_config 发起服务请求与解析输出，agent_config 统一解析后交 app_backend，再传给 scientific_writer_client.generate_paper。即 `app_backend �?agent_config.invoke_model(agent_id, "writing", "query_normalize", messages) �?规范�?query �?app_backend �?writer.generate_paper`�?

---

## 十一、与 DESIGN_ARCHITECTURE.md 的关�?

- 本文档为 **backend 模块�?* 的职责与调用关系设计�?
- **DESIGN_ARCHITECTURE.md** 描述四场景的**业务流程**�?
- 实施时需同时参照二者�?

---

## 十二、实施详细设计（代码级）

### 12.1 配置与数据结�?

#### 12.1.1 memu_scenarios.json 新增字段

```json
{
  "agent_ids": ["physics_agent", "chemistry_agent", "biology_agent", "math_agent", "cs_agent", "_default"],
  "_comment": "...",
  "physics_agent": { ... },
  ...
}
```

- **agent_ids**（顶层，数组）：用于快速统�?agent 数量、检索与意图识别；`list_agent_ids()` 读取此字段；不含 `_comment` 等非 agent 键�?

#### 12.1.2 memu_records 表新增列

- **memu_error**（TEXT，可空）：memorize 失败时记录错误信息；成功时为空�?

#### 12.1.3 config/agents/ 目录与文�?

- 路径：`merge_project/config/agents/`
- 文件：`<agent_id>.json`，如 `physics_agent.json`、`_default.json`
- 结构示例（见 `config_agents_example.json`）：

```json
{
  "paper_ingest": {
    "extraction_s1": {"provider": "qwen", "model": "qwen-long"},
    "extraction_s2": {"provider": "qwen", "model": "qwen-plus"},
    "figure_caption": {"provider": "qwen", "model": "qwen-vl-plus"}
  },
  "parameter_recommendation": {"main": {"provider": "qwen", "model": "qwen-long"}},
  "writing": {"query_normalize": {"provider": "qwen", "model": "qwen-plus"}}
}
```

---

### 12.2 agent_config.py

#### 12.2.1 新增常量与路�?

```python
CONFIG_AGENTS_DIR = CONFIG_DIR / "agents"
```

#### 12.2.2 新增函数：get_model_for_step

```python
def get_model_for_step(agent_id: str, task_name: str, step: str) -> Dict[str, str]:
    """
    �?config/agents/<agent_id>.json 读取 (task_name, step) 对应�?provider、model�?
    缺失时回退 _default.json；再缺失则使�?qwen 兜底�?
    返回：{"provider": "qwen", "model": "qwen-long"}
    """
```

#### 12.2.3 新增函数：get_client_for_step

```python
def get_client_for_step(agent_id: str, task_name: str, step: str):
    """
    返回�?config/agents 配置�?OpenAI 兼容 client（OpenAI 或兼容实现）�?
    �?file-extract（files.create + chat）等需直接�?API 的场景�?
    provider 对应�?api_key、base_url �?.env 读取�?
    """
```

#### 12.2.4 新增函数：invoke_model

```python
def invoke_model(
    agent_id: str,
    task_name: str,
    step: str,
    messages: List[Dict[str, str]],
    *,
    temperature: float = 0.2,
) -> str:
    """
    根据 agent_id + task_name + step 获取 provider/model，从 .env �?api_key/base_url�?
    发起 chat.completions.create；失败时回退 qwen 系列�?
    返回：assistant 消息�?content 字符串�?
    """
```

#### 12.2.5 修改函数：list_agent_ids

```python
def list_agent_ids() -> List[str]:
    """�?memu_scenarios.json �?agent_ids 字段读取；若无则回退到遍历排�?_comment 等�?""
```

#### 12.2.6 写作 query 规范化流�?

- 写作 query 规范化统一�?`invoke_model(agent_id, "writing", "query_normalize", messages)`�?
- system prompt：可使用 `config/prompts/_default/query_normalize_system.txt` 或沿�?scientific_writer_client 中的 QUERY_NORMALIZE_SYSTEM 常量�?
- user message：app_backend 组装 raw_input、venue、project_type、data_files、memory_md（与当前 writer.normalize_query �?user_content 一致）�?
- 返回：规范化后的 query 字符串�?

---

### 12.3 paper_ingest.py

#### 12.3.1 修改：extract_paper_structure

- **移除** 直接调用 `_get_dashscope_client` 与硬编码 model�?
- **改为** 使用 `agent_config.get_client_for_step(agent_id, "paper_ingest", "extraction_s1")` 获取已配置的 OpenAI 兼容 client；用�?`files.create` + `chat.completions.create`（file-extract 流程）。extraction_s2 同理�?
- 或：`agent_config.invoke_model` 支持可选的 `file_path` 参数，内部完�?file-extract 流程；否则由 agent_config 提供 `get_client_for_step` 返回配置好的 client，供 paper_ingest 执行 files.create �?chat�?
- 实施选择�?*agent_config 新增 `get_client_for_step(agent_id, task_name, step) -> OpenAI`**，返回按 config/agents 配置�?client；paper_ingest 用该 client �?files.create 与两�?chat�?
- 保持返回值结构不变：`{"metadata": ..., "methodology": ..., "keywords": ..., "figures": ...}` �?`{"error": "..."}`�?

#### 12.3.2 重构：paper_ingest_pdf

- **签名**：`paper_ingest_pdf(file_path, user_id, agent_ids, user_input, storage_dir) -> Dict`�?*移除** `memu_client` 参数�?
- **职责**：对每个 agent：extract_paper_structure �?复制文件到存�?�?构建 `record`、`conversation`�?*�?*调用 memorize、insert_record�?
- **返回**：`{"agent_ids": [...], "results": [{"agent_id": str, "record_id": str, "record": dict, "conversation": list, "structured": dict, "resolved_storage_folder": str}]}`�?
- **app_backend**：调�?`paper_ingest_pdf` 得到 results 后，对每条执�?`memu.memorize(conversation)`；不论成功与否执�?`memu.insert_record(record)`，record 中写�?`memu_error`（memorize 失败时）�?

---

### 12.4 parameter_recommendation.py

#### 12.4.1 移除

- 删除 `get_memory_context_for_agents`，或迁移�?app_backend 作为私有方法�?
- `run_parameter_recommendation` **不再**接收 `memu_client`，改为接�?`memory_context: str`�?

#### 12.4.2 修改：run_parameter_recommendation 签名

```python
def run_parameter_recommendation(
    structured_paper: Dict[str, Any],
    user_params: Dict[str, Any],
    user_id: str,
    agent_id: Optional[str] = None,
    agent_ids: Optional[List[str]] = None,
    memory_context: str = "",  # �?app_backend 传入，不再接�?memu_client
    relevant_forces: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
```

#### 12.4.3 修改：LLM 调用

- �?`client.chat.completions.create(..., model="qwen-long")` 改为 `agent_config.invoke_model(agent_id, "parameter_recommendation", "main", messages)`�?

---

### 12.5 app_backend.py

#### 12.5.1 新增：_get_memory_context_for_agents

```python
def _get_memory_context_for_agents(
    self, query: str, user_id: str, agent_ids: List[str], max_chars_per_agent: int = 3000
) -> str:
    """�?agent 联合检索，合并为一段文本。内部调�?self.memu.retrieve �?format_retrieve_for_writing�?""
```

#### 12.5.2 修改：parameter_recommendation

- 先调�?`_get_memory_context_for_agents` 得到 `memory_context`�?
- 再调�?`param_rec_module.run_parameter_recommendation(..., memory_context=memory_context)`，不�?`memu_client`�?

#### 12.5.3 修改：normalize_query

- **原逻辑**：调�?`self.memu.get_memory_context_for_writing` 得到 memory_md，再�?`self.writer.normalize_query`�?
- **新逻辑**：仍先调 `self.memu.get_memory_context_for_writing` 得到 memory_md；然后调�?`agent_config.invoke_model(agent_id, "writing", "query_normalize", messages)`，其�?messages �?user 内容�?raw_input、venue、project_type、data_files、memory_md 的拼接（与当�?writer.normalize_query �?user_content 一致）；返回规范化 query�?

#### 12.5.4 修改：run_paper_generation

- 记忆增强：不变�?
- 规范化：改为�?`agent_config.invoke_model` 或封装后�?`agent_config.normalize_query_for_writing(agent_id, raw_input, venue_id, project_type_id, data_file_names, memory_md)`（若 agent_config 提供该便捷函数）；再�?query �?`writer.generate_paper`�?

#### 12.5.5 修改：paper_ingest_pdf

- 调用 `paper_ingest_module.paper_ingest_pdf` 得到 `{"results": [...]}`�?
- 对每�?result：执�?`self.memu.memorize(conversation, ...)`；不论成功与否，执行 `self.memu.insert_record(record)`，record 中写�?`memu_error`（memorize 失败时从 memorize 返回值取 error）�?

#### 12.5.6 修改：paper_analysis_scenario

- 步骤 3 �?`get_memory_context_for_agents` 改为 `self._get_memory_context_for_agents`�?
- 步骤 5 �?`paper_ingest_pdf` 调用后，�?app_backend 执行 memorize、insert_record（若 paper_ingest_pdf 改为返回 results 不含 memorize/insert_record）�?

---

### 12.6 memu_client.py / MemUClient

#### 12.6.1 修改：format_retrieve_for_writing

- �?`format_retrieve_for_writing` 改为**抽象方法**（或子类重写入口），�?Cloud 实现具体逻辑；基类可保留默认实现（当前逻辑），并在文档中标�?MemUOSSClient 必须重写�?

#### 12.6.2 修改：_init_db、_db_insert_record、insert_record、_MEMU_RECORDS_COLS

- `_MEMU_RECORDS_COLS` 新增 `"memu_error"`�?
- 表结构新�?`memu_error` 列（ALTER TABLE �?CREATE 时包含）�?
- `insert_record` 接受 `record` 中含 `memu_error` 键；`_db_insert_record` 写入该列�?

---

### 12.7 memu_oss_client.py / MemUOSSClient

#### 12.7.1 新增：UserModelWithAgent

```python
class UserModelWithAgent(BaseModel):
    user_id: str | None = None
    agent_id: str | None = None
```

#### 12.7.2 修改：MemoryService 初始�?

```python
user_config = {"model": UserModelWithAgent}
self._service = MemoryService(..., user_config=user_config)
```

#### 12.7.3 修改：memorize、retrieve

- `user_scope = {"user_id": uid, "agent_id": aid}`
- `where = {"user_id": uid, "agent_id": aid}`

#### 12.7.4 重写：format_retrieve_for_writing

- 解析 OSS 返回�?`categories`、`items`、`resources`；items �?`summary` 字段，categories �?`summary` �?`description`�?

#### 12.7.5 补齐：upload_files、register_writing_event、match_and_resolve

- 本地文件复制 + memu_records DB 写入 + MemoryService.memorize（conversation 形式），�?Cloud �?MemUClient 行为对齐�?

---

### 12.8 scientific_writer_client.py

#### 12.8.1 修改：normalize_query

- **保留** `normalize_query` 作为**后备**（当 agent_config 不可用时的模板拼接）�?
- **�?*标记�?deprecated，app_backend 统一使用 agent_config.invoke_model 做规范化，仅�?agent_config 失败时回退�?writer.normalize_query 的模板逻辑�?
- 实施建议：保�?normalize_query 不变，app_backend �?normalize_query、run_paper_generation 改为优先使用 agent_config.invoke_model；失败时回退 writer.normalize_query�?

---

### 12.9 config.py

#### 12.9.1 新增

```python
CONFIG_AGENTS_DIR = CONFIG_DIR / "agents"
CONFIG_AGENTS_DIR.mkdir(parents=True, exist_ok=True)
```

---

### 12.10 实施顺序建议

1. config.py：CONFIG_AGENTS_DIR
2. memu_scenarios.json：添�?agent_ids
3. config/agents/：创�?_default.json、physics_agent.json �?
4. agent_config.py：get_model_for_step、invoke_model、list_agent_ids 修改
5. memu_client.py：memu_error 列、format_retrieve_for_writing 抽象/标注
6. paper_ingest.py：extract_paper_structure 改为 agent_config.invoke_model；paper_ingest_pdf 返回 results �?app_backend 执行 memorize/insert_record
7. parameter_recommendation.py：去�?memu_client，接�?memory_context；改�?agent_config.invoke_model
8. app_backend.py：_get_memory_context_for_agents；parameter_recommendation、normalize_query、run_paper_generation、paper_ingest_pdf、paper_analysis_scenario 的修�?
9. memu_oss_client.py：UserModelWithAgent、format_retrieve_for_writing、upload_files、register_writing_event、match_and_resolve
