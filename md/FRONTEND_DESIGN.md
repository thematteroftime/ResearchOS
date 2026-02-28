# �?Agent 联合分析科研学习平台 �?前端设计文档

> **版本**�?.1  
> **设计参�?*：Perplexity AI 界面风格  
> **实现参�?*：`paper_web/front.py`（PlasmaRAG Frontend�? 
> **功能依据**：`final_project`（四场景流程、后端模块设计）  
> **Gradio 参�?*：[Gradio 中文文档](https://gradio.org.cn/docs)

---

## 〇、Perplexity 风格设计参�?

以下设计原则源于 Perplexity AI 界面分析，供本平台前端实现参照�?

### 0.1 整体布局

| 区域 | 宽度占比 | 视觉 | 职责 |
|------|----------|------|------|
| **左侧导航�?* | 15�?0% | 浅灰背景，略深于主区 | 全局导航、当前上下文、快捷操�?|
| **主工作区** | 75�?0% | 纯白 / 浅灰 | 当前场景的内容展示与交互 |
| **右侧补充�?*（可选） | 20�?5% | 白色，与主区分离 | 个性化设置、快捷信息、相关推�?|

### 0.2 左侧导航栏结构（自上而下�?

1. **顶部搜索**：`gr.Textbox`，占位符「搜索」，带搜索图�?
2. **当前上下�?*：高亮显示当前场景（如「论文分析」），带图标
3. **主导航链�?*：每个带图标 + 文案，垂直排�?
   - `+ 新建问题`（或对应主操作）
   - `论文分析`
   - `科研写作`
   - `参数推荐`
   - `记忆查询`
   - `更多...`
4. **最�?快捷**：动态区域，「最近和活跃的任务将显示在这里」占�?
5. **底部**：登�?/ 账户与设�?

### 0.3 主工作区模式

| 模式 | 典型布局 | 示例 |
|------|----------|------|
| **入口/主页** | 居中大输入框 + 快捷建议按钮 | 主操作输入、模型下拉、附�?语音 |
| **列表/历史** | 顶部分类 Tab + 搜索 + 筛�?排序 | 问题 / 媒体 / 应用 / 文件 |
| **内容展示** | 卡片网格或单列详�?| 论文卡片、推荐卡片、文章列�?|
| **空状�?* | 居中提示文案 + �?CTA 按钮 | 「尚无内容�?「新建任务�?|

### 0.4 视觉与交互原�?

- **配色**：白/浅灰背景，深灰文字，主色用于按钮和强�?
- **留白**：内容之间保持足够间�?
- **图标**：简单线条图标，与文字成对出�?
- **卡片**：圆角、细边框或轻阴影，统一高度/比例
- **按钮**：主操作 `variant="primary"`，次要操�?`variant="secondary"`

---

## 一、设计概�?

### 1.1 目标

基于 Gradio 构建�?agent 联合分析的科研学习平台前端，覆盖以下四种核心场景�?

| 场景 | 功能 | 用户入口 |
|------|------|----------|
| **场景一** | 论文上传分析 | PDF 上传 + 用户输入 �?结构化提�?+ memU/DB |
| **场景�?* | 科研写作 | 格式/场景 + 用户输入 + 数据文件 �?生成 PDF |
| **场景�?* | 参数推荐 | 期望现象 + 参数�?�?推荐区间与力�?|
| **场景�?* | 记忆查询与下�?| 自然语言问题 �?记录列表 + 源文�?URL |

### 1.2 参考案例：paper_web/front.py

`front.py` 已实�?PlasmaRAG 的三模块布局，为本设计提供可复用模式�?

- **布局**：`gr.Blocks` + `gr.Row` + `gr.Column`，左侧导�?+ 右侧工作�?
- **视图切换**：`gr.Radio` 切换 Paper Analysis / Simulation Setup / Library，通过 `nav.change` 控制可见�?
- **数据展示**：`gr.Markdown` + `gr.HTML` 渲染卡片，`gr.Gallery` 展示图片，`gr.Dataframe` 编辑参数
- **状态管�?*：`gr.State` 存储结构�?JSON、选中论文 ID
- **样式**：自定义 CSS 注入 `gr.HTML`，实现卡片、参数网格、推荐仪表盘
- **数学公式**：`gr.Markdown` �?`latex_delimiters` 支持 KaTeX 渲染

---

## 二、整体布局�?Gradio 组件选择

### 2.1 根布局：gr.Blocks + gr.Sidebar（Perplexity 风格�?

```python
with gr.Blocks(title="科研学习平台", theme=gr.themes.Base(primary_hue="slate", neutral_hue="gray")) as demo:
    with gr.Row():
        # 左侧导航栏（scale�?，浅灰背景）
        with gr.Column(scale=1, elem_classes=["nav-sidebar"]):
            search_input = gr.Textbox(placeholder="🔍 搜索...", show_label=False)
            nav = gr.Radio(["论文分析", "科研写作", "参数推荐", "记忆查询"], value="论文分析", show_label=False)
            gr.Markdown("---")
            recent_section = gr.Markdown("*最近和活跃的任务将显示在这�?")
            # 底部占位：登�?设置

        # 主工作区（scale=4�?
        with gr.Column(scale=4):
            # 各场景内容，�?nav.change 控制可见�?
            ...
```

**参�?*：[gr.Blocks](https://gradio.org.cn/docs/gradio/blocks)、[gr.Sidebar](https://gradio.org.cn/docs/gradio/sidebar)

### 2.2 布局结构（Perplexity 式两栏）

| 区域 | 组件 | scale | 说明 |
|------|------|-------|------|
| 左侧�?| `gr.Column` + `elem_classes=["nav-sidebar"]` | 1 | 全局搜索、主导航、最近动态、底部账�?|
| 主工作区 | `gr.Column` | 4 | 当前场景的输入与输出，大块内容区 |
| 顶部（可选） | 主工作区�?`gr.Row` | �?| 场景标题、筛�?Tab、搜索、排�?|

**导航实现**：`gr.Radio`（`show_label=False`�? 自定�?CSS 使每项呈「图�?文案」按钮样式；`nav.change` 切换主工作区内各区块可见性�?

### 2.3 主导航项与场景映�?

| 导航�?| 场景 | 主操�?|
|--------|------|--------|
| 论文分析 | 场景一 | 上传 PDF + 分析并入�?|
| 科研写作 | 场景�?| 选择格式 + 生成论文 |
| 参数推荐 | 场景�?| 填写现象与参�?+ 生成推荐 |
| 记忆查询 | 场景�?| 输入问题 + 检索并下载 |

---

## 三、各场景前端设计

### 3.1 场景一：论文上传分�?

**主工作区布局（Perplexity 入口风格�?*：顶部为大输�?上传区，下方为快捷操作与结果区�?

#### 3.1.1 主工作区顶部（入口区�?

| 组件 | Gradio API | 参数建议 | 说明 |
|------|------------|----------|------|
| 场景标题 | `gr.Markdown` | `"## 论文分析"` | �?Perplexity 各页标题一�?|
| 主输入区 | `gr.Row` | 内含 File + Textbox + Button | 仿照「问任何事情...」的大输入块 |
| PDF 上传 | `gr.File` | `file_types=[".pdf"]`, `label="上传 PDF"` | 左侧或上方，支持拖拽 |
| 用户输入（可选） | `gr.Textbox` | `placeholder="对论文的理解或关注点（选填�?.."`, `lines=2` | 参与 memU 增强 |
| 模型/模式 | `gr.Dropdown` | `choices=["默认", "快�?, "详细"]` | 可选，控制提取粒度 |
| 分析按钮 | `gr.Button` | `"🚀 分析并入�?`, `variant="primary"` | 主操�?|
| 快捷建议 | `gr.Row` | 若干 `gr.Button` | 如「提取参数」「提取图表」「全文摘要�?|
| 示例加载 | `gr.Button` | `"🧪 加载示例"`, `variant="secondary"` | 渲染测试 |
| 进度展示 | `gr.HTML` | 5 步进度条 | 参�?front.py `render_progress_html` |

**空状�?*：未上传时，显示「上�?PDF 开始分析」提�?+ 示例按钮�?

#### 3.1.2 输出区（主工作区主体�?

| 组件 | Gradio API | 说明 |
|------|------------|------|
| 论文头部 | `gr.Markdown` | 标题、期刊、年份、创新点 |
| 图表画廊 | `gr.Gallery` | `columns=3`, `object_fit="contain"`, `height=380` |
| 详细内容 | `gr.Markdown` | 物理背景、现象、参数、力�?|
| 结构化状�?| `gr.State` | `structured_json`，供场景三复�?|

#### 3.1.3 展示层级（DESIGN_ARCHITECTURE §2.6�?

- **快速浏�?*：标�?+ 摘要 + 图表缩略�?
- **细读**：展开事实、公式、参数，带溯�?
- **项目导向**：结�?memU 筛选相关事�?

建议：默认「细读」；�?`gr.Accordion` 折叠各模块�?

---

### 3.2 场景二：科研写作

**主工作区布局**：顶部为标题 + 大输入区；下方为格式/文件选择与结果区�?

#### 3.2.1 主工作区入口�?

| 组件 | Gradio API | 参数建议 | 说明 |
|------|------------|----------|------|
| 场景标题 | `gr.Markdown` | `"## 科研写作"` | 与导航对�?|
| 主输�?| `gr.Textbox` | `placeholder="描述您的写作意图，例如：Create a Nature paper on..."`, `lines=5` | 记忆增强后规范化 |
| 附件 | `gr.File` | `file_count="multiple"`, `file_types=[".pdf", ".md", ".png", ".csv"]` | 左侧 `+` 附件，类�?Perplexity |
| 格式/场景 | `gr.Row` | 两列 `gr.Dropdown` | 格式（Nature/Science/IEEE�? 类型（基�?论文/海报�?|
| 写作按钮 | `gr.Button` | `"📝 生成论文"`, `variant="primary"` | 主操�?|
| 快捷建议 | `gr.Row` | 若干 `gr.Button` | 如「Nature 风格」「基金申报」「会议海报�?|

#### 3.2.2 输出区（主工作区主体�?

| 组件 | Gradio API | 说明 |
|------|------------|------|
| 任务状�?| `gr.Markdown` | job_id、进度提�?|
| 进度�?| `gr.Progress` | 长时任务轮询 |
| PDF 链接 | `gr.DownloadButton` �?`gr.File` | 生成完成后的下载 |
| 摘要/Peer Review | `gr.Markdown` | SUMMARY.md、PEER_REVIEW.md |

**空状�?*：未提交时显示「输入写作意图并选择格式开始�? 示例按钮�?

---

### 3.3 场景三：参数推荐

**主工作区布局**：顶部为大输�?+ 参数表；下方为推荐结果卡片网格（�?Perplexity Discover 卡片布局）�?

#### 3.3.1 主工作区入口�?

| 组件 | Gradio API | 参数建议 | 说明 |
|------|------------|----------|------|
| 场景标题 | `gr.Markdown` | `"## 参数推荐"` | 与导航对�?|
| 期望现象 | `gr.Textbox` | `placeholder="期望观察到的物理现象，例如：观察到微粒在微重力流场中形成的链状结�?`, `lines=3` | 用户目标 |
| 参数�?| `gr.Dataframe` | `headers=["参数名称","目标数�?,"单位","物理意义"]`, `row_count="dynamic"`, `column_count=(4,"fixed")` | 可增减行 |
| 增减�?| `gr.Row` | `"�?` / `"�?` 按钮 | 参�?front.py |
| 生成推荐 | `gr.Button` | `"💡 生成对标推荐"`, `variant="primary"` | 需已解析论�?|
| 示例推荐 | `gr.Button` | `"🧪 加载示例"`, `variant="secondary"` | 渲染测试 |
| Expert 模式 | `gr.Checkbox` | `label="显示原始 JSON"` | 展示完整 JSON |

#### 3.3.2 输出区（主工作区主体，卡片网格）

| 组件 | Gradio API | 说明 |
|------|------------|------|
| 推荐面板 | `gr.Markdown` | 参数卡片 + 力场卡片，LaTeX 公式 |
| 卡片样式 | 自定�?HTML/CSS | 参数区间、步长、理由，�?Perplexity Finance 数据卡片 |

**空状�?*：未解析论文时显示「请先在「论文分析」中上传并解析论文�? 示例按钮�?

参�?front.py �?`format_recommendation_panel_v2`�?

---

### 3.4 场景四：记忆查询与下�?

**主工作区布局（仿 Perplexity 历史 / 库页面）**：顶部为筛�?Tab + 搜索 + 排序；主体为记录列表或空状态�?

#### 3.4.1 主工作区顶部（筛选与搜索�?

| 组件 | Gradio API | 参数建议 | 说明 |
|------|------------|----------|------|
| 场景标题 | `gr.Markdown` | `"## 记忆查询"` | 与导航对�?|
| 分类 Tab | `gr.Tabs` �?`gr.Radio` | `["全部", "论文", "写作", "推荐"]` | 对应 scene：paper / writing_event / parameter_recommendation |
| 搜索�?| `gr.Textbox` | `placeholder="搜索你的记录..."` | 过滤检索结�?|
| 筛�?排序 | `gr.Row` | `gr.Dropdown` 类型 + `gr.Dropdown` 排序（最�?最早） | 类型筛选、排序方�?|
| 查询输入 | `gr.Textbox` | `placeholder="例如：最近关于复杂等离子体的论文有哪些？"` | 主检索输�?|
| 查询按钮 | `gr.Button` | `"🔍 检�?`, `variant="primary"` | 触发 memU retrieve |

#### 3.4.2 输出区（主工作区主体�?

| 组件 | Gradio API | 说明 |
|------|------------|------|
| 记录列表 | `gr.Dataframe` | `columns=["状�?,"任务","文件"]`, `interactive=False` | �?Perplexity 任务列表 |
| 选中查看 | 行点击或 `gr.Button` | 根据选中行解�?record_id �?DB 查路�?|
| 详情展示 | `gr.Markdown` / `gr.HTML` | 选中记录的摘要、元数据、下载链�?|
| 下载 | `gr.DownloadButton` | 生成下载 URL |

**空状�?*：无记录时显示「尚无记录�?「尝试上传论文或执行一次写�?推荐�? 主操作引导�?

**可�?*：用 `gr.Chatbot` / `gr.ChatInterface` 实现对话式检索；当前以「Tab + 搜索 + 列表 + 选中查看/下载」为主�?

---

## 四、事件与状态流

### 4.1 核心事件绑定

| 事件 | 输入 | 输出 | 后端调用 |
|------|------|------|----------|
| 分析按钮 click | `upload`, `user_input` | `parse_status`, `progress_html`, `header`, `body`, `raw_structured_state`, `fig_gallery` | `paper_analysis_scenario` |
| 写作按钮 click | `venue`, `project_type`, `user_input`, `data_files` | `job_status`, `pdf_link`, `summary_md` | `run_paper_generation` |
| 推荐按钮 click | `raw_structured_state`, `phenomena`, `param_df`, `expert_toggle` | `recom_panel` | `parameter_recommendation` |
| 查询按钮 click | `query` | `records_df`, `details_html` | `retrieve` �?DB 查路�?|

### 4.2 状态依�?

- `raw_structured_state`：场景一解析后写入，场景三读取；未解析时推荐按钮可禁用或提示「请先分析论文�?
- `lib_selected_id`：Library 表格 `select` 事件写入，供「查看选中论文」使�?
- `fig_gallery`：与论文详情共享，场景一/Library 查看时更�?

### 4.3 跨场景数据流

```
场景一 PDF 解析 �?raw_structured_state
                      �?
场景�?参数推荐 �?raw_structured_state + phenomena + param_df
```

---

## 五、样式与主题

### 5.1 主题配置（Perplexity 风格：浅色、简约）

```python
demo.launch(
    theme=gr.themes.Base(
        primary_hue="slate",   # �?"gray"，偏中�?
        neutral_hue="gray",
        radius_size="lg"      # 圆角
    ),
    ...
)
```

**参�?*：[gr.themes](https://gradio.org.cn/docs/gradio/themes)

### 5.2 自定�?CSS

#### 5.2.1 左侧导航栏（`.nav-sidebar`�?

| 属�?| 建议�?| 说明 |
|------|--------|------|
| `background` | `#f5f5f5` �?`#f0f0f0` | 略深于主区，区分层次 |
| `padding` | `16px 12px` | 内边�?|
| `min-width` | `200px` | 最小宽�?|
| `border-right` | `1px solid #e5e7eb` | 与主区分�?|

#### 5.2.2 内容卡片（沿�?front.py + Perplexity 卡片风格�?

| 类名 | 用�?|
|------|------|
| `.paper-workbench` | 工作台容�?|
| `.paper-header` / `.paper-title` | 论文头部 |
| `.paper-card` / `.paper-card-physics` | 内容卡片 |
| `.param-grid` / `.param-card` | 参数网格 |
| `.phenomena-card` | 观测现象卡片 |
| `.force-section` / `.force-card` | 力场卡片 |
| `.recom-card` / `.reason-box` | 推荐卡片 |
| `.content-card` | 通用内容卡片（圆角、浅灰边框、轻阴影�?|

#### 5.2.3 空状�?

| 类名 | 用�?|
|------|------|
| `.empty-state` | 居中、浅灰文�?|
| `.empty-state-cta` | �?CTA 按钮样式 |

注入方式：`gr.HTML(card_css() + nav_sidebar_css())`，放在布局最前�?

### 5.3 LaTeX 支持

`gr.Markdown` 配置�?

```python
gr.Markdown(
    ...,
    latex_delimiters=[
        {"left": "$", "right": "$", "display": False},
        {"left": "$$", "right": "$$", "display": True},
        {"left": r"\[", "right": r"\]", "display": True},
    ],
)
```

---

## 六、后端对接与 API

### 6.1 后端入口

所有前端交互经 `app_backend` 统一入口，参�?BACKEND_MODULE_DESIGN�?

- 不向前端暴露 model、api_key、base_url
- 业务参数：`agent_id`、`user_id`、`file_path`、`user_input`、`structured_paper` �?
- memU �?DB 逻辑全部�?app_backend 内完�?

### 6.2 接口映射（示意）

| 前端操作 | 后端方法 | 主要参数 |
|----------|----------|----------|
| 分析 PDF | `paper_analysis_scenario` | `file_path`, `user_input`, `user_id` |
| 生成论文 | `run_paper_generation` | `normalized_query`, `venue_id`, `project_type_id`, `data_files` |
| 参数推荐 | `parameter_recommendation` | `structured_paper`, `user_params`, `memory_context` |
| 记忆查询 | `retrieve` + DB 查路�?| `query`, `user_id`, `agent_id` |

### 6.3 文件与路�?

- **allowed_paths**：`demo.launch(allowed_paths=[current_dir, images_dir, figures_dir])` 以支�?`file=` 协议访问本地图片
- **下载 URL**：部署时路径转为 `/api/download?task_id=...`，前端使�?`gr.DownloadButton` 或链�?

---

## 七、Gradio 组件速查�?

| 场景/用�?| 推荐组件 | 文档链接 |
|-----------|----------|----------|
| 根布局 | `gr.Blocks`, `gr.Row`, `gr.Column` | [Blocks](https://gradio.org.cn/docs/gradio/blocks), [Row](https://gradio.org.cn/docs/gradio/row), [Column](https://gradio.org.cn/docs/gradio/column) |
| 导航/切换 | `gr.Radio`, `gr.Tab`, `gr.TabbedInterface` | [Radio](https://gradio.org.cn/docs/gradio/radio), [Tab](https://gradio.org.cn/docs/gradio/tab), [TabbedInterface](https://gradio.org.cn/docs/gradio/tabbedinterface) |
| 文件 | `gr.File`, `gr.UploadButton` | [File](https://gradio.org.cn/docs/gradio/file), [UploadButton](https://gradio.org.cn/docs/gradio/uploadbutton) |
| 文本 | `gr.Textbox`, `gr.Markdown`, `gr.Code` | [Textbox](https://gradio.org.cn/docs/gradio/textbox), [Markdown](https://gradio.org.cn/docs/gradio/markdown), [Code](https://gradio.org.cn/docs/gradio/code) |
| 表格 | `gr.Dataframe`, `gr.Dataset` | [Dataframe](https://gradio.org.cn/docs/gradio/dataframe), [Dataset](https://gradio.org.cn/docs/gradio/dataset) |
| 图片 | `gr.Gallery`, `gr.Image`, `gr.AnnotatedImage` | [Gallery](https://gradio.org.cn/docs/gradio/gallery), [Image](https://gradio.org.cn/docs/gradio/image), [AnnotatedImage](https://gradio.org.cn/docs/gradio/annotatedimage) |
| 按钮 | `gr.Button`, `gr.ClearButton`, `gr.DownloadButton` | [Button](https://gradio.org.cn/docs/gradio/button), [ClearButton](https://gradio.org.cn/docs/gradio/clearbutton), [DownloadButton](https://gradio.org.cn/docs/gradio/downloadbutton) |
| 选项 | `gr.Dropdown`, `gr.Checkbox`, `gr.CheckboxGroup` | [Dropdown](https://gradio.org.cn/docs/gradio/dropdown), [Checkbox](https://gradio.org.cn/docs/gradio/checkbox), [CheckboxGroup](https://gradio.org.cn/docs/gradio/checkboxgroup) |
| 布局 | `gr.Accordion`, `gr.Group`, `gr.Sidebar` | [Accordion](https://gradio.org.cn/docs/gradio/accordion), [Group](https://gradio.org.cn/docs/gradio/group), [Sidebar](https://gradio.org.cn/docs/gradio/sidebar) |
| 状�?进度 | `gr.State`, `gr.Progress` | [State](https://gradio.org.cn/docs/gradio/state), [Progress](https://gradio.org.cn/docs/gradio/progress) |
| 事件 | `gr.on`, `SelectData`, `EventData` | [on](https://gradio.org.cn/docs/gradio/on), [SelectData](https://gradio.org.cn/docs/gradio/selectdata), [EventData](https://gradio.org.cn/docs/gradio/eventdata) |

---

## 八、实施建�?

### 8.1 Perplexity 风格实现要点

1. **左侧�?*：使�?`gr.Column(scale=1, elem_classes=["nav-sidebar"])`，注�?`.nav-sidebar` CSS；顶部放搜索 `gr.Textbox`；主导航�?`gr.Radio` �?`gr.Button` 列表；底部「最近」区可绑�?`list_indexed_papers()` 或最近任务，空时显示占位文案�?
2. **主工作区**：各场景统一「标�?+ 入口�?+ 内容区」结构；入口区模仿大输入�?+ 快捷建议按钮；内容区用卡片网格或列表�?
3. **空状�?*：各场景未操作时显示 `.empty-state` + �?CTA，如「上�?PDF 开始」「输入意图开始」「检索记忆开始」�?
4. **分类与筛�?*：记忆查询页�?`gr.Tabs` �?`gr.Radio` 做「全�?/ 论文 / 写作 / 推荐」；配合搜索、类型、排�?`gr.Dropdown`�?

### 8.2 技术实�?

1. **复用 front.py 逻辑**：`render_header_html`、`render_body_html`、`extract_figure_paths`、`card_css`、`format_recommendation_panel_v2` 等可直接迁移或轻量适配�?
2. **场景扩展**：在 `gr.Radio` 中保留「论文分析」「科研写作」「参数推荐」「记忆查询」，并实�?`switch_view` 与事件绑定�?
3. **写作流程**：格�?场景�?`gr.Dropdown` 从配置加载；数据文件�?`gr.File(file_count="multiple")`；长时任务用 `gr.Progress` 或轮询状态�?
4. **记忆查询**：`retrieve` 返回后解�?items/resources，构�?`Dataframe`；选中行解�?record_id，调用后端生成下�?URL�?
5. **�?Agent**：若需用户选择 agent，可增加 `gr.Dropdown(choices=agent_ids)`；否则由意图识别在后台决定�?

---

## 九、文档索�?

- **设计参�?*：Perplexity AI 界面（搜索、历史、发现、空间、金融、Computer 等页�?
- **功能与流�?*：`DESIGN_ARCHITECTURE.md`
- **后端模块**：`BACKEND_MODULE_DESIGN.md`
- **实施状�?*：`IMPLEMENTATION_STATUS.md`
- **参考实�?*：`paper_web/front.py`
- **Gradio 文档**：https://gradio.org.cn/docs
