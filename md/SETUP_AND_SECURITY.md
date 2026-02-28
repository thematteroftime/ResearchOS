# 安全与首次配置指南

本文档说明**敏感信息保护**与**首次使用需修改的配置**，确保项目可安全分享或开源。

---

## 一、敏感信息保护

### 1.1 切勿提交的文件

以下文件/目录已加入 `.gitignore`，**请勿**移除或提交到版本库：

| 路径 | 说明 |
|------|------|
| `.env` | 环境变量与 **API 密钥**（最重要） |
| `.env.local`、`.env.*.local` | 本地覆盖配置 |
| `job_records/` | 写作任务记录（含本地绝对路径） |
| `writing_outputs/` | 生成的论文、PDF、LaTeX |
| `database/` | SQLite 数据库、memU 存储、下载文件 |
| `tests/logs/` | 测试日志（可能含路径与中间数据） |
| `*.db` | 任何数据库文件 |

### 1.2 API 密钥

所有 API 密钥**仅**存放在 `.env` 中，由 `backend/config.py` 通过 `get_env()` 读取。  
**代码中不包含任何硬编码的密钥。**

| 变量 | 用途 | 必填场景 |
|------|------|----------|
| `ANTHROPIC_API_KEY` | Claude 写作 | 科研写作 |
| `DASHSCOPE_API_KEY` | 通义/Qwen（论文提取、意图识别、参数推荐） | 论文入库、参数推荐 |
| `MEMU_API_KEY` | memU 云端记忆 | 记忆与检索 |
| `OPENROUTER_API_KEY` | 多模型代理、query 改写 | 可选 |

**若 `.env` 曾意外提交或泄露**：请在各平台（Anthropic、DashScope、memU、OpenRouter）**立即轮换（Rotate）** 相关 API 密钥。

---

## 二、首次使用需修改的配置

### 2.1 环境变量（必需）

1. 复制示例配置：
   ```bash
   cp .env.example .env
   ```

2. 在 `.env` 中**按需填写**以下变量（示例值仅供格式参考）：

   ```
   # === 写作必填 ===
   ANTHROPIC_API_KEY=sk-...your-anthropic-key...
   ANTHROPIC_BASE_URL=https://api.anthropic.com    # 或你的代理地址

   # === 论文提取/参数推荐必填 ===
   DASHSCOPE_API_KEY=sk-...your-dashscope-key...
   DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

   # === memU 记忆（可选，未配置时记忆功能受限）===
   MEMU_API_KEY=                               # 留空则禁用云端记忆
   MEMU_BASE_URL=https://api.memu.so
   MEMU_USER_ID=paper_web_user                 # 可改为你的 user_id
   MEMU_AGENT_ID=physics_agent                 # 可改为默认 agent

   # === OpenRouter（可选）===
   OPENROUTER_API_KEY=sk-or-v1-...your-key...
   OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
   ```

3. 详细说明见 [md/ENV_CONFIG.md](ENV_CONFIG.md)。

### 2.2 自定义 BASE_URL（可选）

若使用代理或自建 API 网关，修改 `*_BASE_URL` 即可，例如：

```
ANTHROPIC_BASE_URL=https://your-proxy.example.com/anthropic
DASHSCOPE_BASE_URL=https://your-dashscope-proxy.example.com/v1
```

### 2.3 默认用户与 Agent（可选）

- `MEMU_USER_ID`：memU 默认 user_id，可按业务区分（如按租户、项目）。
- `MEMU_AGENT_ID`：默认 agent，与 `config/agents/` 中的配置对应。

### 2.4 数据库与存储路径

- 数据库路径由 `backend/config.py` 中 `DB_DIR`、`MEMU_DB`、`MEMU_STORAGE_DIR` 等定义。
- 默认在 `merge_project/database/` 下，**一般无需修改**。
- 若需修改：编辑 `backend/config.py` 中对应常量。

### 2.5 测试数据

- **论文 PDF**：置于 `docs/` 或 `data/`，文件名见 [md/README_DOCS.md](README_DOCS.md)。
- **用户问题示例**：`docs/user_questions_examples.txt`，可自行增删行。

---

## 三、配置检查清单

部署或分享前，请确认：

- [ ] `.env` 未纳入版本控制（`git status` 中不应出现 `.env`）
- [ ] 已删除或替换 `.env.example` 中可能残留的占位密钥
- [ ] `job_records/`、`writing_outputs/`、`database/`、`tests/logs/` 已加入 `.gitignore`
- [ ] 若曾泄露密钥，已在对应平台完成轮换

---

## 四、相关文档

| 文档 | 说明 |
|------|------|
| [ENV_CONFIG.md](ENV_CONFIG.md) | 环境变量详细说明与命名约定 |
| [README_CONFIG.md](README_CONFIG.md) | 配置目录结构（prompts、tasks、agents） |
| [README_TESTS.md](README_TESTS.md) | 测试说明与运行方式 |
