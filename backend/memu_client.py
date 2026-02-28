# backend/memu_client.py
"""
memU 记忆系统客户端封装（仅请求云端服务）。
业务逻辑（与 https://memu.pro/docs 一致）：
  1. 上传：多格式文件 → 每条记录具备「文件内容描述」「索引 ID」「存储路径」三要素；描述写入 memU 用于匹配，ID 与路径写入 DB。
  2. 匹配：用户输入 → memU 按描述匹配 → 返回相关度高的文件索引 ID。
  3. 解析：用 ID 从 DB 取资源路径（或 URL）。
  4. 交付：将路径/可下载列表交给用户，用户选择后下载到指定路径。
"""

import json
import re
import shutil
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Literal

import httpx

from .config import get_env, MEMU_DB, MEMU_STORAGE_DIR, MEMU_SCENARIOS_PATH

# 场景类型：论文入库 / 项目提议 / 写作事件 / 参数推荐
SceneType = Literal["paper", "proposal", "writing_event", "parameter_recommendation", "data", "image", "other"]


def build_storage_path(storage_dir: Path, user_id: str, agent_id: str, scene: str, record_id: str) -> Path:
    """
    统一存储路径：{storage_dir}/{user_id}/{agent_id}/{scene}/{record_id}/。
    供 paper_ingest、parameter_recommendation、writing_event 等场景复用。
    """
    return storage_dir / user_id / agent_id / scene / record_id

# 云端 API 仅支持 conversation 型 memorize，不支持 resource_url+modality
SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".doc", ".csv", ".xlsx", ".xls", ".png", ".jpg", ".jpeg", ".md", ".txt", ".json"}


def _read_file_summary(file_path: str, max_chars: int = 4000) -> str:
    """读取文件摘要或前 N 字符，用于放入对话供 memU 索引。"""
    path = Path(file_path)
    if not path.exists():
        return f"[File not found: {path.name}]"
    ext = path.suffix.lower()
    try:
        if ext in (".txt", ".md", ".json"):
            return path.read_text(encoding="utf-8", errors="replace")[:max_chars]
        if ext == ".csv":
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                return "".join(f.readlines()[:100])[:max_chars]
        return f"[Binary/structured file: {path.name}, type={ext}]"
    except Exception as e:
        return f"[Read error for {path.name}: {e}]"


def _row_to_record(row: tuple, cols: List[str]) -> Dict[str, Any]:
    """将 SQLite row 转为 record 字典。"""
    d = dict(zip(cols, row))
    for k in ("data_files",):
        if k in d and isinstance(d.get(k), str) and d[k]:
            try:
                d[k] = json.loads(d[k])
            except Exception:
                d[k] = []
    return d


class MemUClient:
    """
    memU 云端 v3 HTTP API 封装。
    - memorize(conversation): 写入记忆
    - retrieve(query): 检索记忆
    - 多格式上传 + 本地 SQLite 存储；删除、检索、下载记录；可选 OpenRouter 检索增强
    """

    _MEMU_RECORDS_COLS = [
        "record_id", "task_id", "scene", "original_path", "file_name", "simplified_path",
        "description", "user_input", "user_id", "agent_id", "created_at",
        "job_id", "query", "data_files", "output_pdf", "output_tex", "memu_error",
    ]
    _MEMU_REF_PATTERN = re.compile(r"record_id=([a-zA-Z0-9\-]+)")

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        db_path: Optional[Path] = None,
        storage_dir: Optional[Path] = None,
    ):
        # 显式传入 api_key（含空串）时不再从 env 读取，便于单测强制禁用云端
        self.api_key = (api_key if api_key is not None else get_env("MEMU_API_KEY") or "").strip()
        self.base_url = (base_url or get_env("MEMU_BASE_URL") or "https://api.memu.so").rstrip("/")
        self.user_id = user_id or get_env("MEMU_USER_ID") or "merge_user"
        self.agent_id = agent_id or get_env("MEMU_AGENT_ID") or "_default"
        self.enabled = bool(self.api_key)
        self._db_path = Path(db_path or MEMU_DB)
        self._storage_dir = Path(storage_dir or MEMU_STORAGE_DIR)
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._scenarios_config: Dict[str, Any] = {}
        self._load_scenarios_config()
        self._init_db()

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _post(self, path: str, payload: Dict[str, Any], timeout: float = 30.0) -> Dict[str, Any]:
        if not self.enabled:
            return {"error": "memu_disabled"}
        url = f"{self.base_url}{path}"
        try:
            r = httpx.post(url, headers=self._headers(), json=payload, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            return {"error": str(e), "url": url}

    def _get(self, path: str, timeout: float = 30.0) -> Dict[str, Any]:
        if not self.enabled:
            return {"error": "memu_disabled"}
        url = f"{self.base_url}{path}"
        try:
            r = httpx.get(url, headers=self._headers(), timeout=timeout)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            return {"error": str(e), "url": url}

    def _init_db(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memu_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    record_id TEXT UNIQUE NOT NULL,
                    task_id TEXT,
                    scene TEXT,
                    original_path TEXT,
                    file_name TEXT,
                    simplified_path TEXT,
                    description TEXT,
                    user_input TEXT,
                    user_id TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    created_at TEXT,
                    job_id TEXT,
                    query TEXT,
                    data_files TEXT,
                    output_pdf TEXT,
                    output_tex TEXT
                )
            """)
            try:
                conn.execute("ALTER TABLE memu_records ADD COLUMN description TEXT")
            except sqlite3.OperationalError:
                pass
            try:
                conn.execute("ALTER TABLE memu_records ADD COLUMN memu_error TEXT")
            except sqlite3.OperationalError:
                pass
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memu_download_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    record_id TEXT NOT NULL,
                    source_path TEXT NOT NULL,
                    saved_path TEXT,
                    user_id TEXT,
                    downloaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def _db_insert_record(self, record: Dict[str, Any]) -> None:
        data_files = record.get("data_files")
        if isinstance(data_files, list):
            data_files = json.dumps(data_files, ensure_ascii=False)
        desc = record.get("description") or ""
        memu_error = record.get("memu_error") or ""
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.execute("""
                INSERT INTO memu_records (
                    record_id, task_id, scene, original_path, file_name, simplified_path,
                    description, user_input, user_id, agent_id, created_at,
                    job_id, query, data_files, output_pdf, output_tex, memu_error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record.get("record_id"), record.get("task_id"), record.get("scene"),
                record.get("original_path") or "", record.get("file_name") or "",
                record.get("simplified_path") or "", desc, record.get("user_input") or "",
                record.get("user_id"), record.get("agent_id"), record.get("created_at"),
                record.get("job_id") or "", record.get("query") or "",
                data_files or "[]", record.get("output_pdf") or "", record.get("output_tex") or "",
                memu_error,
            ))
            conn.commit()

    def insert_record(self, record: Dict[str, Any]) -> None:
        """插入一条本地记录（供论文入库等流程在已写入存储后调用，与 memorize 配合使用）。"""
        self._db_insert_record(record)

    def _db_list_records(
        self,
        user_id: str,
        agent_id: str,
        scene: Optional[SceneType] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        cols = self._MEMU_RECORDS_COLS
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.row_factory = lambda c, r: r
            cur = conn.cursor()
            if scene:
                cur.execute(
                    "SELECT " + ", ".join(cols) + " FROM memu_records WHERE user_id = ? AND agent_id = ? AND scene = ? ORDER BY created_at DESC LIMIT ?",
                    (user_id, agent_id, scene, limit),
                )
            else:
                cur.execute(
                    "SELECT " + ", ".join(cols) + " FROM memu_records WHERE user_id = ? AND agent_id = ? ORDER BY created_at DESC LIMIT ?",
                    (user_id, agent_id, limit),
                )
            rows = cur.fetchall()
        return [_row_to_record(r, cols) for r in rows]

    def _db_get_record(self, record_id: str, user_id: str, agent_id: str) -> Optional[Dict[str, Any]]:
        cols = self._MEMU_RECORDS_COLS
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.row_factory = lambda c, r: r
            cur = conn.cursor()
            cur.execute(
                "SELECT " + ", ".join(cols) + " FROM memu_records WHERE record_id = ? AND user_id = ? AND agent_id = ?",
                (record_id, user_id, agent_id),
            )
            row = cur.fetchone()
        return _row_to_record(row, cols) if row else None

    def _db_delete_records(self, record_ids: List[str], user_id: str, agent_id: str) -> int:
        if not record_ids:
            return 0
        with sqlite3.connect(str(self._db_path)) as conn:
            placeholders = ",".join("?" * len(record_ids))
            cur = conn.execute(
                f"DELETE FROM memu_records WHERE record_id IN ({placeholders}) AND user_id = ? AND agent_id = ?",
                (*record_ids, user_id, agent_id),
            )
            conn.commit()
            return cur.rowcount

    def _db_log_download(self, record_id: str, source_path: str, saved_path: str, user_id: str) -> None:
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.execute(
                "INSERT INTO memu_download_log (record_id, source_path, saved_path, user_id) VALUES (?, ?, ?, ?)",
                (record_id, source_path, saved_path or source_path, user_id),
            )
            conn.commit()

    def _load_scenarios_config(self) -> None:
        """从 config/memu_scenarios.json 加载按 agent_id 的配置（预留扩展）。"""
        path = Path(MEMU_SCENARIOS_PATH)
        if not path.exists():
            self._scenarios_config = {}
            return
        try:
            self._scenarios_config = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            self._scenarios_config = {}

    def get_retrieve_config(self, agent_id: Optional[str] = None) -> Dict[str, Any]:
        """
        获取当前 agent_id 对应的 retrieve override_config（top_k 等）。
        用于 match_and_resolve 与 retrieve 的扩展接口；未配置时返回 _default 或空。
        """
        aid = agent_id or self.agent_id
        cfg = self._scenarios_config.get(aid) or self._scenarios_config.get("_default") or {}
        retrieve = cfg.get("retrieve") or {}
        return dict(retrieve)

    def _build_storage_path(self, user_id: str, agent_id: str, scene: str, record_id: str) -> Path:
        """
        统一存储路径规范：{storage_dir}/{user_id}/{agent_id}/{scene}/{record_id}/。
        各场景（paper、parameter_recommendation、writing_event、data、image 等）均使用此结构。
        """
        return build_storage_path(self._storage_dir, user_id, agent_id, scene, record_id)

    def _resolve_storage_folder(self, record: Dict[str, Any], user_id: Optional[str] = None, agent_id: Optional[str] = None) -> Optional[Path]:
        """
        将 DB 中的 original_path 解析为本地存储文件夹路径。
        存储规范：original_path = "{scene}/{record_id}"，完整路径为 {storage_dir}/{user_id}/{agent_id}/{scene}/{record_id}/。
        当主存储路径不存在且使用测试存储时，回退到 MEMU_STORAGE_DIR（兼容旧记录）。
        """
        uid = user_id or self.user_id
        aid = agent_id or self.agent_id
        raw = (record.get("original_path") or "").strip()
        if not raw:
            return None
        p = Path(raw)
        if p.is_absolute() or raw.startswith("/") or (len(raw) > 1 and raw[1] == ":"):
            return p if p.exists() else None
        base = self._storage_dir / uid / aid
        full = base / raw
        if full.exists():
            return full
        # 回退：测试存储下未找到时，尝试默认存储（兼容 paper 等旧记录）
        if self._storage_dir != MEMU_STORAGE_DIR:
            fallback_base = MEMU_STORAGE_DIR / uid / aid
            fallback_full = fallback_base / raw
            if fallback_full.exists():
                return fallback_full
        return None

    # ---------- 云端 API：对话式 memorize / retrieve ----------

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
        """
        写入记忆。v3: POST /api/v3/memory/memorize
        override_config 可选，来自 config/memu_scenarios.json 的 memory_types 等（预留扩展）。
        """
        uid = user_id or self.user_id
        aid = agent_id or self.agent_id
        payload = {"conversation": conversation, "user_id": uid, "agent_id": aid}
        if override_config:
            payload["override_config"] = override_config
        out = self._post("/api/v3/memory/memorize", payload)
        task_id = out.get("task_id")
        if not task_id or not wait:
            return out
        start = time.time()
        while time.time() - start < timeout:
            status_resp = self._get(f"/api/v3/memory/memorize/status/{task_id}")
            status = status_resp.get("status")
            if status == "SUCCESS":
                return {"task_id": task_id, "status": status}
            if status == "FAILED":
                return {"task_id": task_id, "status": status, "detail": status_resp}
            time.sleep(poll_interval)
        return {"task_id": task_id, "status": "TIMEOUT", "detail": status_resp}

    def retrieve(
        self,
        query: str,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        override_config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        检索记忆。v3: POST /api/v3/memory/retrieve
        override_config 未传时从 config/memu_scenarios.json 按 agent_id 加载（method=rag, top_k 等）。
        """
        uid = user_id or self.user_id
        aid = agent_id or self.agent_id
        payload = {"user_id": uid, "agent_id": aid, "query": query}
        cfg = override_config if override_config is not None else self.get_retrieve_config(aid)
        if cfg:
            payload["override_config"] = cfg
        return self._post("/api/v3/memory/retrieve", payload)

    def _openrouter_query_rewrite(self, query: str, max_tokens: int = 150) -> str:
        """使用 OpenRouter 对 query 做改写/扩展，提升检索效果。"""
        key = get_env("OPENROUTER_API_KEY")
        if not key or not query.strip():
            return query
        url = "https://openrouter.ai/api/v1/chat/completions"
        payload = {
            "model": "openai/gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "Rewrite the user's search query for a memory retrieval system. Output only the improved query, no explanation. Keep it concise and in the same language."},
                {"role": "user", "content": query},
            ],
            "max_tokens": max_tokens,
        }
        try:
            r = httpx.post(url, headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, json=payload, timeout=15.0)
            r.raise_for_status()
            data = r.json()
            choices = data.get("choices") or []
            if choices and isinstance(choices[0].get("message"), dict):
                text = (choices[0]["message"].get("content") or "").strip()
                if text:
                    return text
        except Exception:
            pass
        return query

    def format_retrieve_for_writing(
        self,
        retrieve_response: Dict[str, Any],
        max_chars: int = 4000,
    ) -> str:
        """
        将 retrieve 接口返回的响应格式化为供写作使用的文本（.md 风格）。
        供 parameter_recommendation、project_proposal_optimize 等复用。
        """
        if not retrieve_response or retrieve_response.get("error"):
            return ""
        parts: List[str] = []
        for key in ("memories", "items", "resources"):
            items = retrieve_response.get(key)
            if isinstance(items, list):
                for it in items[:10]:
                    if isinstance(it, dict):
                        raw = (it.get("memory") or it).get("content", "") if isinstance(it.get("memory"), dict) else it.get("content", it)
                    else:
                        raw = it
                    if raw is None:
                        continue
                    if isinstance(raw, str):
                        content = raw
                    elif isinstance(raw, (dict, list)):
                        content = json.dumps(raw, ensure_ascii=False)
                    else:
                        content = str(raw)
                    if content:
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

    def get_memory_context_for_writing(
        self,
        topic_hint: str,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        max_chars: int = 4000,
    ) -> str:
        """
        为论文写作生成一段“记忆上下文”文本（.md 风格），
        供后续与用户输入一起交给 Qwen 做 query 规范化。
        """
        if not self.enabled:
            return ""
        r = self.retrieve(query=topic_hint, user_id=user_id, agent_id=agent_id)
        return self.format_retrieve_for_writing(r, max_chars=max_chars)

    # ---------- 多格式上传 + 场景记录（本地 DB + 云端对话） ----------

    def _infer_scene(self, file_path: str) -> SceneType:
        ext = Path(file_path).suffix.lower()
        if ext == ".pdf":
            return "paper"
        if ext in (".docx", ".doc", ".md"):
            return "proposal"
        if ext in (".csv", ".xlsx", ".xls", ".json"):
            return "data"
        if ext in (".png", ".jpg", ".jpeg"):
            return "image"
        return "other"

    def upload_files(
        self,
        file_paths: List[str],
        scene: Optional[SceneType] = None,
        user_input: str = "",
        simplified_path: Optional[str] = None,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        wait: bool = True,
    ) -> Dict[str, Any]:
        """
        多格式、多文件上传：将文件信息以对话形式写入 memU，并在本地 DB 建立记录以便检索与下载。
        """
        uid = user_id or self.user_id
        aid = agent_id or self.agent_id
        task_ids: List[str] = []
        record_ids: List[str] = []
        created_records: List[Dict[str, Any]] = []

        for fp in file_paths:
            path = Path(fp)
            if not path.exists():
                continue
            scene_type = scene or self._infer_scene(str(path))
            record_id = str(uuid.uuid4())[:12]
            relative_path = f"{scene_type}/{record_id}"
            storage_folder = self._build_storage_path(uid, aid, scene_type, record_id)
            storage_folder.mkdir(parents=True, exist_ok=True)
            storage_path = storage_folder / path.name
            try:
                shutil.copy2(path, storage_path)
            except Exception:
                continue
            summary = _read_file_summary(str(path))
            ref_line = f"[MEMU_REF record_id={record_id} scene={scene_type} file={path.name}]"
            user_content = f"{ref_line}\n\nFile: {path.name}\nType: {path.suffix}\nScene: {scene_type}\n\nContent or summary:\n{summary}"
            if user_input.strip():
                user_content += f"\n\nUser note: {user_input.strip()}"
            task_id = ""
            if self.enabled:
                conversation = [
                    {"role": "user", "content": user_content},
                    {"role": "assistant", "content": "Stored. This file has been recorded for later retrieval and download."},
                ]
                out = self.memorize(conversation=conversation, user_id=uid, agent_id=aid, wait=wait)
                task_id = out.get("task_id", "")
                if out.get("error"):
                    continue
                task_ids.append(task_id)
            record_ids.append(record_id)
            record = {
                "record_id": record_id,
                "task_id": task_id,
                "scene": scene_type,
                "original_path": relative_path,
                "file_name": path.name,
                "simplified_path": simplified_path or "",
                "description": user_content,
                "user_input": user_input.strip(),
                "user_id": uid,
                "agent_id": aid,
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
            }
            created_records.append(record)
            self._db_insert_record(record)
        return {
            "task_ids": task_ids,
            "record_ids": record_ids,
            "records": created_records,
            "error": "memu_disabled" if not self.enabled else None,
        }

    def register_writing_event(
        self,
        job_id: str,
        query: str,
        data_files: List[str],
        output_pdf: str = "",
        output_tex: str = "",
        output_directory: str = "",
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        将一次写作任务打包为「写作事件」记录。
        若提供 output_directory（writing_outputs/<job_dir>），则按 claude-scientific-writer 输出结构
        复制 PDF、SUMMARY.md、PEER_REVIEW.md 到 memU 存储，便于检索与下载。
        """
        uid = user_id or self.user_id
        aid = agent_id or self.agent_id
        record_id = str(uuid.uuid4())[:12]

        # 若提供 output_directory，复制关键文件到 memU 存储
        original_path = ""
        file_name = ""
        if output_directory:
            job_dir = Path(output_directory)
            if job_dir.exists():
                relative_path = f"writing_event/{record_id}"
                dest_folder = self._build_storage_path(uid, aid, "writing_event", record_id)
                dest_folder.mkdir(parents=True, exist_ok=True)

                # 按 claude-scientific-writer 结构：final/*.pdf, SUMMARY.md, PEER_REVIEW.md
                if output_pdf and Path(output_pdf).exists():
                    shutil.copy2(output_pdf, dest_folder / Path(output_pdf).name)
                    file_name = Path(output_pdf).name
                else:
                    final_dir = job_dir / "final"
                    if final_dir.exists():
                        pdfs = list(final_dir.glob("*.pdf"))
                        if pdfs:
                            shutil.copy2(pdfs[0], dest_folder / pdfs[0].name)
                            file_name = pdfs[0].name
                for name in ("SUMMARY.md", "PEER_REVIEW.md"):
                    src = job_dir / name
                    if src.exists():
                        shutil.copy2(src, dest_folder / name)
                original_path = relative_path

        user_content = (
            f"[MEMU_REF record_id={record_id} scene=writing_event job_id={job_id}]\n\n"
            f"Writing event.\nQuery: {query}\nData files: {', '.join(data_files or [])}\n"
            f"Output PDF: {output_pdf or file_name}\nOutput TeX: {output_tex}"
        )

        task_id = ""
        if self.enabled:
            conversation = [
                {"role": "user", "content": user_content},
                {"role": "assistant", "content": "Writing event recorded for retrieval."},
            ]
            out = self.memorize(conversation=conversation, user_id=uid, agent_id=aid, wait=True)
            task_id = out.get("task_id", "")
            if out.get("error"):
                return {"error": out.get("error"), "record_id": record_id, "task_id": task_id}

        record = {
            "record_id": record_id,
            "task_id": task_id,
            "scene": "writing_event",
            "job_id": job_id,
            "query": query,
            "data_files": data_files or [],
            "output_pdf": output_pdf or file_name,
            "output_tex": output_tex,
            "user_id": uid,
            "agent_id": aid,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
            "original_path": original_path,
            "file_name": file_name,
            "simplified_path": "",
            "description": user_content,
            "user_input": "",
        }
        self._db_insert_record(record)
        return {"record_id": record_id, "task_id": task_id, "record": record}

    def _parse_record_ids_from_retrieve_response(self, cloud: Dict[str, Any]) -> List[str]:
        """从 memU retrieve 响应中解析出 record_id 列表（MEMU_REF record_id=xxx）。"""
        seen: set = set()
        ids: List[str] = []

        def scan(val: Any) -> None:
            if isinstance(val, str):
                for m in self._MEMU_REF_PATTERN.finditer(val):
                    rid = m.group(1)
                    if rid and rid not in seen:
                        seen.add(rid)
                        ids.append(rid)
            elif isinstance(val, dict):
                for v in val.values():
                    scan(v)
            elif isinstance(val, list):
                for v in val:
                    scan(v)

        scan(cloud)
        return ids

    def match_and_resolve(
        self,
        query: str,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        limit: Optional[int] = None,
        use_openrouter_query_rewrite: bool = False,
    ) -> Dict[str, Any]:
        """
        业务主流程：用户输入 → memU 按 agent 配置检索 → 得到相关记录 ID + scene → 从本地 DB 取相对路径 → 解析为可访问的存储路径。
        返回 matched_record_ids 与 records（含 record_id, scene, description, storage_path 相对路径, resolved_storage_folder, file_name），
        limit 未传时从 config/memu_scenarios.json 的 retrieve.item.top_k 读取（如 physics_agent 为 5）。
        """
        uid = user_id or self.user_id
        aid = agent_id or self.agent_id
        print(f"[MEMU] match_and_resolve 入口 | user_id={uid} agent_id={aid} query={repr((query or '')[:80])}", flush=True)
        if limit is None:
            rcfg = self.get_retrieve_config(aid)
            limit = (rcfg.get("item") or {}).get("top_k", 5)
        effective_query = query
        if use_openrouter_query_rewrite and query.strip():
            effective_query = self._openrouter_query_rewrite(query)
        cloud = self.retrieve(query=effective_query, user_id=uid, agent_id=aid) if self.enabled else {}
        matched_ids = self._parse_record_ids_from_retrieve_response(cloud) if cloud else []
        print(f"[MEMU] match_and_resolve 云端/本地 | cloud_enabled={self.enabled} matched_ids={len(matched_ids)}", flush=True)
        if not matched_ids and (query or effective_query).strip():
            local_all = self._db_list_records(uid, aid, scene=None, limit=limit * 3)
            q = ((query or effective_query) or "").strip().lower()
            for r in local_all:
                if q and q not in (r.get("description") or "").lower() and q not in (r.get("file_name") or "").lower():
                    continue
                matched_ids.append(r.get("record_id", ""))
            matched_ids = matched_ids[:limit]
        else:
            matched_ids = matched_ids[:limit]
        print(f"[MEMU] match_and_resolve 最终 matched_ids | count={len(matched_ids)} ids={matched_ids[:5]}", flush=True)
        records_with_paths: List[Dict[str, Any]] = []
        for rid in matched_ids:
            r = self._db_get_record(rid, uid, aid)
            if not r:
                continue
            # 无 original_path 的记录（如 writing_event）仍返回，便于展示；有路径时解析为本地文件夹
            storage_path = r.get("original_path") or ""
            folder = self._resolve_storage_folder(r, uid, aid) if storage_path else None
            rec = {
                "record_id": r.get("record_id"),
                "scene": r.get("scene"),
                "agent_id": r.get("agent_id") or aid,
                "description": (r.get("description") or "")[:500],
                "storage_path": storage_path,
                "file_name": r.get("file_name"),
                "created_at": r.get("created_at"),
            }
            if folder is not None:
                rec["resolved_storage_folder"] = str(folder)
                fn = r.get("file_name")
                if fn and (folder / fn).exists():
                    rec["resolved_primary_path"] = str(folder / fn)
            records_with_paths.append(rec)
        print(f"[MEMU] match_and_resolve 完成 | records_count={len(records_with_paths)} error={cloud.get('error') if cloud else None}", flush=True)
        return {
            "query": query,
            "effective_query": effective_query if use_openrouter_query_rewrite else None,
            "matched_record_ids": matched_ids,
            "records": records_with_paths,
            "cloud_response": cloud,
            "error": cloud.get("error"),
        }

    # ---------- 检索：云端 retrieve + 本地 DB 过滤/补充 ----------

    def search(
        self,
        query: str,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        scene: Optional[SceneType] = None,
        limit: int = 20,
        use_openrouter_query_rewrite: bool = False,
    ) -> Dict[str, Any]:
        """
        根据用户输入检索：调用云端 retrieve，并与本地记录合并。
        use_openrouter_query_rewrite=True 时先用 OpenRouter 改写 query 再检索（需 OPENROUTER_API_KEY）。
        """
        uid = user_id or self.user_id
        aid = agent_id or self.agent_id
        effective_query = query
        if use_openrouter_query_rewrite and query.strip():
            effective_query = self._openrouter_query_rewrite(query)
        cloud = self.retrieve(query=effective_query, user_id=uid, agent_id=aid) if self.enabled else {}

        q_lower = (query or "").strip().lower()
        local_hits = []
        for r in self._db_list_records(uid, aid, scene=scene, limit=limit * 2):
            if q_lower:
                searchable = " ".join([
                    r.get("file_name", ""),
                    r.get("user_input", ""),
                    r.get("query", ""),
                    r.get("scene", ""),
                ]).lower()
                if q_lower not in searchable:
                    continue
            local_hits.append(r)
        local_hits = local_hits[:limit]

        return {
            "query": query,
            "effective_query": effective_query if use_openrouter_query_rewrite else None,
            "cloud": cloud,
            "local_records": local_hits,
            "error": cloud.get("error"),
        }

    def get_download_info(
        self,
        record_id: str,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """根据 record_id 返回该条记录的下载信息；含相对路径 original_path 及解析后的 resolved_storage_folder / resolved_primary_path。"""
        uid = user_id or self.user_id
        aid = agent_id or self.agent_id
        print(f"[MEMU] get_download_info 入口 | record_id={record_id} user_id={uid} agent_id={aid}", flush=True)
        r = self._db_get_record(record_id, uid, aid)
        if not r:
            print(f"[MEMU] get_download_info 未找到记录 | record_id={record_id}", flush=True)
            return None
        out = {
            "record_id": r.get("record_id"),
            "scene": r.get("scene"),
            "original_path": r.get("original_path"),
            "file_name": r.get("file_name"),
            "description": r.get("description"),
            "simplified_path": r.get("simplified_path"),
            "user_input": r.get("user_input"),
            "output_pdf": r.get("output_pdf"),
            "output_tex": r.get("output_tex"),
            "data_files": r.get("data_files"),
            "created_at": r.get("created_at"),
        }
        folder = self._resolve_storage_folder(r, uid, aid)
        if folder is not None:
            out["resolved_storage_folder"] = str(folder)
            fn = r.get("file_name")
            if fn and (folder / fn).exists():
                out["resolved_primary_path"] = str(folder / fn)
            # scene=paper 时，与 JSON 同存的 Markdown 与 structured.json 路径
            if r.get("scene") == "paper":
                if (folder / "structured.json").exists():
                    out["structured_json_path"] = str(folder / "structured.json")
                if (folder / "summary.md").exists():
                    out["summary_md_path"] = str(folder / "summary.md")
            # scene=parameter_recommendation 时，summary.md 与 recommendations.json
            elif r.get("scene") == "parameter_recommendation":
                if (folder / "summary.md").exists():
                    out["summary_md_path"] = str(folder / "summary.md")
                if (folder / "recommendations.json").exists():
                    out["recommendations_json_path"] = str(folder / "recommendations.json")
            # scene=writing_event 时，SUMMARY.md、PEER_REVIEW.md、final/*.pdf
            elif r.get("scene") == "writing_event":
                if (folder / "SUMMARY.md").exists():
                    out["summary_md_path"] = str(folder / "SUMMARY.md")
                if (folder / "PEER_REVIEW.md").exists():
                    out["peer_review_md_path"] = str(folder / "PEER_REVIEW.md")
                if not out.get("resolved_primary_path"):
                    pdfs = list(folder.glob("*.pdf"))
                    if pdfs:
                        out["resolved_primary_path"] = str(pdfs[0])
        # writing_event 无 original_path 时（旧记录），尝试用 output_pdf 绝对路径
        if r.get("scene") == "writing_event" and not out.get("resolved_primary_path"):
            op = r.get("output_pdf") or ""
            if op and Path(op).exists():
                out["resolved_primary_path"] = op
        print(f"[MEMU] get_download_info 完成 | record_id={record_id} scene={out.get('scene')} folder={out.get('resolved_storage_folder')}", flush=True)
        return out

    def log_download(
        self,
        record_id: str,
        source_path: str,
        saved_path: str = "",
        user_id: Optional[str] = None,
    ) -> None:
        """记录一次下载行为到 memu_download_log，便于审计与统计。"""
        uid = user_id or self.user_id
        self._db_log_download(record_id, source_path, saved_path or source_path, uid)

    def download_to_path(
        self,
        record_id: str,
        dest_dir: str | Path,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        从 DB 查记录 → 按 scene/record_id 解析存储文件夹 → 将主文件（或文件夹内首个文件）复制到 dest_dir → 写下载日志。
        """
        uid = user_id or self.user_id
        aid = agent_id or self.agent_id
        info = self.get_download_info(record_id=record_id, user_id=uid, agent_id=aid)
        if not info:
            return {"error": "record_not_found", "record_id": record_id}
        primary = info.get("resolved_primary_path")
        folder = info.get("resolved_storage_folder")
        if primary and Path(primary).exists():
            src_path = Path(primary)
        elif folder:
            folder_path = Path(folder)
            if not folder_path.exists():
                return {"error": "storage_folder_not_found", "record_id": record_id, "resolved_storage_folder": folder}
            file_name = info.get("file_name")
            if file_name and (folder_path / file_name).exists():
                src_path = folder_path / file_name
            else:
                first = next((f for f in folder_path.iterdir() if f.is_file()), None)
                if not first:
                    return {"error": "no_file_in_folder", "record_id": record_id, "resolved_storage_folder": folder}
                src_path = first
        else:
            return {"error": "storage_file_not_found", "record_id": record_id, "original_path": info.get("original_path")}
        dest_dir = Path(dest_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)
        saved_path = dest_dir / src_path.name
        try:
            shutil.copy2(src_path, saved_path)
        except Exception as e:
            return {"error": str(e), "record_id": record_id}
        self.log_download(record_id=record_id, source_path=str(src_path), saved_path=str(saved_path), user_id=uid)
        return {"record_id": record_id, "saved_path": str(saved_path), "file_name": src_path.name}

    def delete_record(
        self,
        record_id: str,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        remove_from_storage: bool = False,
    ) -> Dict[str, Any]:
        """删除一条本地记录；remove_from_storage=True 时同时删除资源存储区中的 scene/record_id 文件夹。"""
        uid = user_id or self.user_id
        aid = agent_id or self.agent_id
        if remove_from_storage:
            r = self._db_get_record(record_id, uid, aid)
            if r:
                folder = self._resolve_storage_folder(r, uid, aid)
                if folder is not None:
                    fp = Path(folder)
                    if fp.exists():
                        try:
                            if fp.is_dir():
                                shutil.rmtree(fp)
                            else:
                                fp.unlink()
                        except Exception:
                            pass
        n = self._db_delete_records([record_id], uid, aid)
        return {"deleted": n, "record_id": record_id}

    def delete_records(
        self,
        record_ids: List[str],
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        remove_from_storage: bool = False,
    ) -> Dict[str, Any]:
        """批量删除本地记录；remove_from_storage=True 时同时删除资源存储区中的 scene/record_id 文件夹。"""
        uid = user_id or self.user_id
        aid = agent_id or self.agent_id
        if remove_from_storage:
            for rid in record_ids:
                r = self._db_get_record(rid, uid, aid)
                if r:
                    folder = self._resolve_storage_folder(r, uid, aid)
                    if folder is not None:
                        fp = Path(folder)
                        if fp.exists():
                            try:
                                if fp.is_dir():
                                    shutil.rmtree(fp)
                                else:
                                    fp.unlink()
                            except Exception:
                                pass
        n = self._db_delete_records(record_ids, uid, aid)
        return {"deleted": n, "record_ids": record_ids}

    def list_records(
        self,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        scene: Optional[SceneType] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """列出本地记录（用于前端展示、下载入口）。"""
        uid = user_id or self.user_id
        aid = agent_id or self.agent_id
        rows = self._db_list_records(uid, aid, scene=scene, limit=limit)
        print(f"[MEMU] list_records | user_id={uid} agent_id={aid} scene={scene} count={len(rows)}", flush=True)
        return rows


def create_memu_client(backend: Optional[str] = None, **kwargs: Any) -> MemUClient:
    """
    工厂：按 MEMU_BACKEND 或 backend 参数返回云端或本地 OSS 客户端。
    - backend "cloud" 或未设置：MemUClient（云端 API + 本地 memu_records）。
    - backend "oss"：尝试 MemUOSSClient（本地 MemoryService）；不可用时回退 MemUClient。
    """
    mode = (backend or get_env("MEMU_BACKEND") or "cloud").strip().lower()
    if mode == "oss":
        try:
            from .memu_oss_client import MemUOSSClient
            oss_client = MemUOSSClient(**kwargs)
            if getattr(oss_client, "_oss_enabled", False):
                return oss_client
        except Exception:
            pass
    return MemUClient(**kwargs)
