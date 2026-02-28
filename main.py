"""
merge_project 统一入口：前后端整合

- 初始化 AppBackend（user_id 固定，预留登录接口扩展）
- 调用 front.app.build_ui(backend) 构建 Gradio 界面
- 绑定四场景后端 API 到前端事件
- 启动 demo

运行：cd merge_project && python main.py
"""
import os
from pathlib import Path

# 确保 no_proxy 在导入 backend 前设置（Gradio/httpx 兼容）
os.environ.setdefault("no_proxy", "localhost,127.0.0.1")

import gradio as gr

from backend.app_backend import AppBackend
from backend.config import PROJECT_ROOT
from front import app as front_app


# ---------- 固定 user_id，预留登录接口用于之后扩展 ----------
DEFAULT_USER_ID = "merge_user"


def main():
    print("[MAIN] 启动 merge_project | user_id 固定为 merge_user", flush=True)
    backend = AppBackend(
        project_root=PROJECT_ROOT,
        memu_user_id=DEFAULT_USER_ID,
        memu_agent_id=None,  # agent_id 由各场景从用户输入/工作记录中识别
    )
    print("[MAIN] 初始化 AppBackend 完成 | 构建 UI", flush=True)
    demo = front_app.build_ui(backend=backend)
    print("[MAIN] 启动 Gradio | 四场景已对接后端", flush=True)
    demo.queue()  # 启用队列，提高侧栏切换等事件的响应可靠性
    demo.launch(
        debug=True,
        share=False,
        theme=gr.themes.Soft(primary_hue="amber", neutral_hue="stone", radius_size="xxl"),
    )


if __name__ == "__main__":
    main()
