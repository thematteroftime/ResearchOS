# backend/memu_oss_client.py
"""
本地 memU 客户端：基于 memU OSS Python SDK（MemoryService）。
- 记忆层：MemoryService + SQLite（sqlite_memory_items / sqlite_resources 等）。
- 资源与路径：复用 MemUClient 的 memu_records.db + MEMU_STORAGE_DIR（双库设计）。
通过 MEMU_BACKEND=oss 或 create_memu_client(backend="oss") 选用。
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from .config import DB_DIR, get_env
from .memu_client import MemUClient


class UserModelWithAgent(BaseModel):
    """memU OSS 用户模型：支持 user_id 与 agent_id 双维度隔离。"""

    user_id: Optional[str] = None
    agent_id: Optional[str] = None


# 延迟导入，避免未安装 memU 时导入失败
def _get_memory_service_class():
    try:
        from memu.app import MemoryService
        return MemoryService
    except ImportError:
        return None


def _run_coro_sync(coro: Any) -> Any:
    """在同步代码中安全执行 async 协程。"""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(asyncio.run, coro)
        return future.result()


class MemUOSSClient(MemUClient):
    """基于 memU OSS MemoryService 的客户端，与 MemUClient 接口一致，记忆存本地 SQLite。"""

    def __init__(
        self,
        *,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        db_path: Optional[Path] = None,
        storage_dir: Optional[Path] = None,
        oss_db_path: Optional[Path] = None,
        llm_api_key: Optional[str] = None,
        llm_base_url: Optional[str] = None,
        **kwargs: Any,
    ):
        super().__init__(
            api_key="",
            base_url="",
            user_id=user_id,
            agent_id=agent_id,
            db_path=db_path,
            storage_dir=storage_dir,
        )
        oss_db_path = Path(oss_db_path or DB_DIR / "memu_oss_memory.db")
        oss_db_path.parent.mkdir(parents=True, exist_ok=True)

        api_key = (llm_api_key or os.getenv("OPENAI_API_KEY") or get_env("DASHSCOPE_API_KEY") or "").strip()
        base_url = (llm_base_url or os.getenv("OPENAI_BASE_URL") or "").strip()
        if not base_url and get_env("DASHSCOPE_API_KEY"):
            base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"

        self._oss_enabled = bool(api_key)
        if not self._oss_enabled:
            self.enabled = False
            self._service = None
            return

        MemoryService = _get_memory_service_class()
        if not MemoryService:
            self._oss_enabled = False
            self.enabled = False
            self._service = None
            return

        db_dsn = f"sqlite:///{oss_db_path}"
        llm_profiles: Dict[str, Any] = {"default": {"api_key": api_key}}
        if base_url:
            llm_profiles["default"]["base_url"] = base_url

        database_config: Dict[str, Any] = {
            "metadata_store": {"provider": "sqlite", "dsn": db_dsn},
        }
        user_config = {"model": UserModelWithAgent}

        self._service = MemoryService(
            llm_profiles=llm_profiles,
            database_config=database_config,
            user_config=user_config,
        )
        self.enabled = True

    def memorize(
        self,
        conversation: List[Dict[str, str]],
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        override_config: Optional[Dict[str, Any]] = None,
        wait: bool = True,
        poll_interval: float = 2.0,
        timeout: float = 120.0,
    ) -> Dict[str, Any]:
        if not self._oss_enabled or self._service is None:
            return {"error": "memu_oss_disabled"}

        uid = user_id or self.user_id
        aid = agent_id or self.agent_id

        contents = [str((m or {}).get("content", "")) for m in conversation if (m or {}).get("content")]
        memory_content = "\n\n".join(contents).strip()

        override = override_config or {}
        memory_types = override.get("memory_types") or ["knowledge"]
        memory_type = memory_types[0] if isinstance(memory_types, list) and memory_types else "knowledge"

        raw_cats = override.get("memory_categories") or []
        memory_categories: List[str] = []
        for c in raw_cats:
            if isinstance(c, dict) and c.get("name"):
                memory_categories.append(str(c["name"]).strip())
            elif isinstance(c, str) and c.strip():
                memory_categories.append(c.strip())

        user_scope = {"user_id": uid}
        if aid:
            user_scope["agent_id"] = aid
        coro = self._service.create_memory_item(
            memory_type=memory_type,
            memory_content=memory_content,
            memory_categories=memory_categories,
            user=user_scope,
        )
        resp = _run_coro_sync(coro)
        item = (resp or {}).get("memory_item") or {}
        memory_id = item.get("id") or item.get("memory_id") or ""

        return {
            "task_id": memory_id,
            "status": "SUCCESS" if memory_id else "UNKNOWN",
            "memory_item": item,
            "raw": resp,
        }

    def retrieve(
        self,
        query: str,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        override_config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not self._oss_enabled or self._service is None:
            return {"error": "memu_oss_disabled"}

        uid = user_id or self.user_id
        aid = agent_id or self.agent_id
        queries = [{"role": "user", "content": query}]
        where = {"user_id": uid}
        if aid:
            where["agent_id"] = aid

        coro = self._service.retrieve(queries=queries, where=where)
        resp = _run_coro_sync(coro)
        return resp or {}

    def format_retrieve_for_writing(
        self,
        retrieve_response: Dict[str, Any],
        max_chars: int = 4000,
    ) -> str:
        """
        将 OSS retrieve 响应格式化为供写作使用的文本。
        OSS 返回的 items 使用 summary 字段，categories 使用 summary 或 description。
        """
        if not retrieve_response or retrieve_response.get("error"):
            return ""
        parts: List[str] = []
        for key in ("items", "categories", "resources"):
            items = retrieve_response.get(key)
            if isinstance(items, list):
                for it in items[:10]:
                    if isinstance(it, dict):
                        raw = it.get("summary") or it.get("content") or it.get("description") or ""
                    else:
                        raw = str(it) if it is not None else ""
                    if raw:
                        content = raw if isinstance(raw, str) else json.dumps(raw, ensure_ascii=False)
                        parts.append(content[:800])
        answer = retrieve_response.get("answer") or retrieve_response.get("summary")
        if answer is not None and answer != "":
            answer_str = answer if isinstance(answer, str) else json.dumps(answer, ensure_ascii=False) if isinstance(answer, (dict, list)) else str(answer)
            if answer_str:
                parts.append(answer_str[:2000])
        text = "\n\n".join(parts).strip()
        if len(text) > max_chars:
            text = text[:max_chars] + "\n..."
        return text
