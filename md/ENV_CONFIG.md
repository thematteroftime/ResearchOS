# 环境变量配置说明

本文档约定**中国模型优先 Qwen、国外模型优先 OpenRouter 等代理商**，并保留 **OpenAI**、**Anthropic（Claude）** 直连；所有结点通过**独立的 API_KEY + BASE_URL** 分离。变量名与 **merge_project**、**claude-scientific-writer**、**memU** 及厂商惯例保持一致。

---

## 一、变量命名依据（参考项目与惯例）

| 变量名 | 参考来源 |
|--------|----------|
| **ANTHROPIC_API_KEY** | claude-scientific-writer `.env.example`、`scientific_writer/core.py`（Claude 官方使用 Anthropic） |
| **OPENROUTER_API_KEY** | claude-scientific-writer 各 skill、memU `example_4_openrouter_memory.py`、merge_project `memu_client.py` |
| **OPENAI_API_KEY** | memU 官方示例（example_1/2/3、sealos-assistant、getting_started_robust）、OpenAI SDK 惯例 |
| **DASHSCOPE_API_KEY** | merge_project `paper_ingest.py`、`agent_config.py`、`parameter_recommendation.py`（Qwen/通义） |
| **MEMU_API_KEY** / **MEMU_BASE_URL** | merge_project `memu_client.py`、memU 文档 https://memu.pro/docs |
| **DEEPSEEK_API_KEY** | DeepSeek 官方文档与生态常用命名 |
| **DOUBAO_API_KEY** | 豆包/火山引擎生态常用命名（如 LobeHub、ArcBlock 等） |

- 规范书写以 **merge_project/.env.example** 为准；final_project 的 `.env.example` 与之对齐并补充注释来源。

---

## 二、设计原则

| 类别     | 原则 |
|----------|------|
| **中国模型** | 优先使用 **Qwen（DASHSCOPE_*）**；保留 **Doubao（DOUBAO_*）**、**DeepSeek（DEEPSEEK_*）** 独立 KEY + BASE_URL，结点分离。 |
| **国外模型** | 优先 **OpenRouter（OPENROUTER_*）**；Claude 使用 **ANTHROPIC_API_KEY**（官方）；并保留 **OPENAI_*** 直连。 |
| **结点分离** | 各厂商/代理商使用各自 `*_API_KEY` 与 `*_BASE_URL`，代码按配置选择结点。 |

---

## 三、变量清单（按用途分组）

### 3.1 中国模型（结点分离）

| 变量名 | 说明 | 典型 Base URL |
|--------|------|----------------|
| **DASHSCOPE_API_KEY** | 通义 / Qwen（阿里 DashScope，OpenAI 兼容）| `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| **DASHSCOPE_BASE_URL** | 同上，可选覆盖默认地址 | 同上 |
| **DOUBAO_API_KEY** | 豆包（字节火山引擎）| — |
| **DOUBAO_BASE_URL** | 豆包 API 地址 | `https://ark.cn-beijing.volces.com/api/v3` |
| **DEEPSEEK_API_KEY** | DeepSeek | — |
| **DEEPSEEK_BASE_URL** | DeepSeek API 地址（OpenAI 兼容）| `https://api.deepseek.com/v1` |

- 未使用的厂商可留空；后端通过 config 或环境变量选择「当前使用的中国模型结点」（如默认 DASHSCOPE）。

### 3.2 国外模型 — 代理商

| 变量名 | 说明 | 典型 Base URL |
|--------|------|----------------|
| **OPENROUTER_API_KEY** | OpenRouter（多模型统一入口，research-lookup / 高阶模型）| `https://openrouter.ai/api/v1` |
| **OPENROUTER_BASE_URL** | 同上，可选覆盖 | 同上 |

- Claude 写作等使用 **ANTHROPIC_***（见下直连）；其它代理商可按需扩展（如 TOGETHER_*），命名保持 `{厂商}_API_KEY` / `{厂商}_BASE_URL`。

### 3.3 国外模型 — 直连厂商

| 变量名 | 说明 | 典型 Base URL |
|--------|------|----------------|
| **OPENAI_API_KEY** | OpenAI 官方 | — |
| **OPENAI_BASE_URL** | OpenAI API 地址 | `https://api.openai.com/v1` |
| **ANTHROPIC_API_KEY** | Anthropic（Claude 官方）| — |
| **ANTHROPIC_BASE_URL** | Anthropic API 地址 | `https://api.anthropic.com` |

- 直连与代理商可并存；具体调用哪条由业务配置（如「高阶模型走 OpenRouter」「写作走 Anthropic」）决定。

### 3.4 memU 记忆服务

| 变量名 | 说明 |
|--------|------|
| **MEMU_API_KEY** | memU 云端 API 密钥 |
| **MEMU_BASE_URL** | memU API 地址，默认 `https://api.memu.so` |
| **MEMU_USER_ID** | 默认 user_id |
| **MEMU_AGENT_ID** | 默认 agent_id |

### 3.5 模型选用（业务侧）

| 变量名 | 说明 | 建议默认 |
|--------|------|----------|
| **INTENT_MODEL** | 意图识别使用的小模型名 | `qwen-turbo`（中国） |
| **CONTEXT_MODEL** | 长上下文 / 论文提取模型名 | `qwen-long`（中国） |
| **OPENROUTER_HIGH_TIER_MODEL** | OpenRouter 上的高阶模型（如 Gemini）| `google/gemini-2.0-flash-exp` |

- 实际调用时：意图/长文本可绑定到 DASHSCOPE_*；高阶验证可绑定到 OPENROUTER_*。

---

## 四、使用方式

1. **复制示例**：将 **merge_project/.env.example** 或 **final_project/.env.example** 复制为 **merge_project/.env**（或项目根目录 `.env`）。
2. **按需填写**：只填写将要使用的结点的 KEY 与 BASE_URL；未用到的可留空。
3. **后端读取**：通过 `backend/config.py` 的 `get_env("XXX_API_KEY")`、`get_env("XXX_BASE_URL")` 读取；代码中根据「当前任务」选择对应结点（如意图识别 → DASHSCOPE，高阶整合 → OPENROUTER）。
4. **结点映射**：建议在 config 或单独配置文件中维护「任务 → 结点」映射，例如：
   - `intent` → DASHSCOPE
   - `paper_extract` → DASHSCOPE
   - `high_tier_verify` → OPENROUTER
   - `writing` → ANTHROPIC 或 OPENROUTER

---

## 五、与现有 merge_project 的兼容

- merge_project 已使用：`DASHSCOPE_API_KEY`、`OPENROUTER_API_KEY`、`ANTHROPIC_*`、`MEMU_*`、`INTENT_MODEL`、`CONTEXT_MODEL`、`OPENROUTER_HIGH_TIER_MODEL`。
- 本方案在**不删除**上述变量的前提下**新增**：
  - `DASHSCOPE_BASE_URL`、`DOUBAO_*`、`DEEPSEEK_*`
  - `OPENROUTER_BASE_URL`
  - `OPENAI_API_KEY`、`OPENAI_BASE_URL`
- 未配置的 `*_BASE_URL` 时，后端可使用文档中的「典型 Base URL」作为默认值。

---

## 六、文件位置

| 文件 | 说明 |
|------|------|
| **merge_project/.env.example** | 规范示例（主参考），与 backend 代码、claude-scientific-writer、memU 变量名一致 |
| **final_project/.env.example** | 与 merge_project 对齐，并注明各变量参考来源 |
| **final_project/ENV_CONFIG.md** | 本文档：命名依据、设计原则、变量清单、使用方式与兼容说明 |

DESIGN_ARCHITECTURE.md 附录 A.4 已指向本文档与 .env.example。
