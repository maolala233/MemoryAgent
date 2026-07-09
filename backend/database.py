"""SQLite database layer with FTS5 full-text index and JSON-stored embeddings.

Schema:
- memory_docs     : metadata for every markdown file in the vault
- memory_fts      : FTS5 virtual table over title + content + summary
- memory_vectors  : per-document embedding stored as JSON array
- chat_history    : persisted chat sessions
- audit_log       : import / mutation audit trail
"""
from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .config.settings import settings

_LOCK = threading.RLock()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS memory_docs (
    rel_path        TEXT PRIMARY KEY,
    title           TEXT,
    memory_type     TEXT DEFAULT 'note',
    track           TEXT DEFAULT 'note',
    project_id      TEXT,
    status          TEXT DEFAULT 'active',
    summary         TEXT,
    keywords_json   TEXT DEFAULT '[]',
    open_loops_json TEXT DEFAULT '[]',
    frontmatter_json TEXT DEFAULT '{}',
    size_bytes      INTEGER DEFAULT 0,
    indexed_at      TEXT,
    verified_at     TEXT,
    updated_at      TEXT,
    created_at      TEXT
);

CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
    rel_path UNINDEXED,
    title,
    content,
    summary,
    tokenize='porter unicode61'
);

CREATE TABLE IF NOT EXISTS memory_vectors (
    rel_path   TEXT PRIMARY KEY,
    vector_json TEXT,
    model      TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS chat_history (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id   TEXT,
    role       TEXT,
    content    TEXT,
    memories_json TEXT,
    thinking   TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS audit_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    action     TEXT,
    target     TEXT,
    detail     TEXT,
    created_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_memory_track ON memory_docs(track);
CREATE INDEX IF NOT EXISTS idx_memory_type ON memory_docs(memory_type);
CREATE INDEX IF NOT EXISTS idx_memory_status ON memory_docs(status);
CREATE INDEX IF NOT EXISTS idx_memory_project ON memory_docs(project_id);
CREATE INDEX IF NOT EXISTS idx_chat_agent ON chat_history(agent_id);

-- v2: 多模型会话
CREATE TABLE IF NOT EXISTS chat_sessions (
    id            TEXT PRIMARY KEY,
    title         TEXT,
    profile_id    TEXT,
    space_name    TEXT,
    search_strategy TEXT,
    top_k         INTEGER,
    use_rerank    INTEGER,
    save_to_space TEXT,
    created_at    TEXT,
    updated_at    TEXT
);

CREATE TABLE IF NOT EXISTS chat_session_messages (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id   TEXT,
    role         TEXT,
    content      TEXT,
    memories_json TEXT,
    thinking     TEXT,
    trace_json   TEXT,
    created_at   TEXT
);

CREATE INDEX IF NOT EXISTS idx_sess_messages_session ON chat_session_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_sessions_updated ON chat_sessions(updated_at DESC);
"""


def _now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


class Database:
    """Thin SQLite wrapper with helpers used across services."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = Path(path) if path else settings.db_path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, check_same_thread=False, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    def _initialize(self) -> None:
        with _LOCK:
            conn = self._connect()
            try:
                conn.executescript(_SCHEMA)
                conn.commit()
            finally:
                conn.close()

    @contextmanager
    def session(self):
        conn = self._connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ---------------- Memory docs ----------------
    def upsert_doc(self, doc: Dict[str, Any]) -> None:
        with _LOCK, self.session() as conn:
            conn.execute(
                """
                INSERT INTO memory_docs (
                    rel_path, title, memory_type, track, project_id, status,
                    summary, keywords_json, open_loops_json, frontmatter_json,
                    size_bytes, indexed_at, verified_at, updated_at, created_at
                ) VALUES (
                    :rel_path, :title, :memory_type, :track, :project_id, :status,
                    :summary, :keywords_json, :open_loops_json, :frontmatter_json,
                    :size_bytes, :indexed_at, :verified_at, :updated_at, :created_at
                )
                ON CONFLICT(rel_path) DO UPDATE SET
                    title=excluded.title,
                    memory_type=excluded.memory_type,
                    track=excluded.track,
                    project_id=excluded.project_id,
                    status=excluded.status,
                    summary=excluded.summary,
                    keywords_json=excluded.keywords_json,
                    open_loops_json=excluded.open_loops_json,
                    frontmatter_json=excluded.frontmatter_json,
                    size_bytes=excluded.size_bytes,
                    indexed_at=excluded.indexed_at,
                    verified_at=excluded.verified_at,
                    updated_at=excluded.updated_at
                """,
                {
                    "rel_path": doc["rel_path"],
                    "title": doc.get("title"),
                    "memory_type": doc.get("memory_type", "note"),
                    "track": doc.get("track", "note"),
                    "project_id": doc.get("project_id"),
                    "status": doc.get("status", "active"),
                    "summary": doc.get("summary"),
                    "keywords_json": json.dumps(doc.get("keywords", []), ensure_ascii=False),
                    "open_loops_json": json.dumps(doc.get("open_loops", []), ensure_ascii=False),
                    "frontmatter_json": json.dumps(doc.get("frontmatter", {}), ensure_ascii=False),
                    "size_bytes": doc.get("size_bytes", 0),
                    "indexed_at": doc.get("indexed_at") or _now_iso(),
                    "verified_at": doc.get("verified_at"),
                    "updated_at": doc.get("updated_at") or _now_iso(),
                    "created_at": doc.get("created_at") or _now_iso(),
                },
            )

    def upsert_fts(self, rel_path: str, title: str, content: str, summary: str = "") -> None:
        with _LOCK, self.session() as conn:
            conn.execute("DELETE FROM memory_fts WHERE rel_path = ?", (rel_path,))
            conn.execute(
                "INSERT INTO memory_fts(rel_path, title, content, summary) VALUES (?, ?, ?, ?)",
                (rel_path, title or "", content or "", summary or ""),
            )

    def delete_doc(self, rel_path: str, soft: bool = True) -> None:
        with _LOCK, self.session() as conn:
            if soft:
                conn.execute(
                    "UPDATE memory_docs SET status='deleted', updated_at=? WHERE rel_path=?",
                    (_now_iso(), rel_path),
                )
            else:
                conn.execute("DELETE FROM memory_docs WHERE rel_path=?", (rel_path,))
            conn.execute("DELETE FROM memory_fts WHERE rel_path=?", (rel_path,))
            conn.execute("DELETE FROM memory_vectors WHERE rel_path=?", (rel_path,))

    def get_doc(self, rel_path: str) -> Optional[Dict[str, Any]]:
        with self.session() as conn:
            row = conn.execute(
                "SELECT * FROM memory_docs WHERE rel_path=?", (rel_path,)
            ).fetchone()
        return self._row_to_doc(row) if row else None

    def list_docs(
        self,
        skip: int = 0,
        limit: int = 50,
        track: Optional[str] = None,
        memory_type: Optional[str] = None,
        status: Optional[str] = None,
        project_id: Optional[str] = None,
        has_open_loop: Optional[bool] = None,
    ) -> Tuple[int, List[Dict[str, Any]]]:
        clauses = []
        params: List[Any] = []
        if track:
            clauses.append("track=?")
            params.append(track)
        if memory_type:
            clauses.append("memory_type=?")
            params.append(memory_type)
        if status:
            clauses.append("status=?")
            params.append(status)
        if project_id:
            clauses.append("project_id=?")
            params.append(project_id)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        with self.session() as conn:
            total = conn.execute(
                f"SELECT COUNT(*) FROM memory_docs {where}", params
            ).fetchone()[0]
            rows = conn.execute(
                f"""
                SELECT * FROM memory_docs {where}
                ORDER BY updated_at DESC NULLS LAST
                LIMIT ? OFFSET ?
                """,
                params + [limit, skip],
            ).fetchall()
        docs = [self._row_to_doc(r) for r in rows]
        if has_open_loop is True:
            docs = [d for d in docs if d.get("open_loops")]
        if has_open_loop is False:
            docs = [d for d in docs if not d.get("open_loops")]
        return total, docs

    def search_keyword(
        self,
        query: str,
        limit: int = 20,
        track: Optional[str] = None,
        memory_type: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        if not query.strip():
            return []
        fts_query = self._build_fts_query(query)
        clauses = ["d.status != 'deleted'"]
        params: List[Any] = []
        if track:
            clauses.append("d.track=?")
            params.append(track)
        if memory_type:
            clauses.append("d.memory_type=?")
            params.append(memory_type)
        if status:
            clauses.append("d.status=?")
            params.append(status)
        where = " AND ".join(clauses)
        sql = f"""
            SELECT d.rel_path, d.title, d.summary, d.memory_type, d.track,
                   d.updated_at, snippet(memory_fts, 2, '<mark>', '</mark>', '…', 12) as snippet,
                   rank as score
            FROM memory_fts
            JOIN memory_docs d ON d.rel_path = memory_fts.rel_path
            WHERE memory_fts MATCH ? AND {where}
            ORDER BY rank
            LIMIT ?
        """
        params = [fts_query] + params + [limit]
        with self.session() as conn:
            rows = conn.execute(sql, params).fetchall()
        results = []
        for r in rows:
            score = 1.0 / (1.0 + abs(float(r["score"])))
            results.append(
                {
                    "rel_path": r["rel_path"],
                    "title": r["title"] or r["rel_path"],
                    "snippet": r["snippet"] or r["summary"] or "",
                    "score": round(score, 4),
                    "memory_type": r["memory_type"],
                    "track": r["track"],
                    "updated_at": r["updated_at"],
                }
            )
        return results

    @staticmethod
    def _build_fts_query(query: str) -> str:
        tokens = [t for t in query.strip().split() if t]
        if not tokens:
            return ""
        return " ".join(f'"{t}"' if " " in t else t for t in tokens)

    def get_suggestions(self, prefix: str, limit: int = 8) -> List[str]:
        if not prefix.strip():
            return []
        prefix = prefix.strip()
        sql = """
            SELECT DISTINCT title FROM memory_fts
            WHERE title LIKE ?
            LIMIT ?
        """
        with self.session() as conn:
            rows = conn.execute(sql, (f"{prefix}%", limit)).fetchall()
        return [r["title"] for r in rows if r["title"]]

    def get_filters(self) -> Dict[str, List[str]]:
        with self.session() as conn:
            tracks = [r[0] for r in conn.execute(
                "SELECT DISTINCT track FROM memory_docs WHERE status!='deleted' AND track IS NOT NULL"
            ).fetchall()]
            types = [r[0] for r in conn.execute(
                "SELECT DISTINCT memory_type FROM memory_docs WHERE status!='deleted' AND memory_type IS NOT NULL"
            ).fetchall()]
            projects = [r[0] for r in conn.execute(
                "SELECT DISTINCT project_id FROM memory_docs WHERE status!='deleted' AND project_id IS NOT NULL"
            ).fetchall()]
        return {"tracks": tracks, "memory_types": types, "projects": projects}

    # ---------------- Vectors ----------------
    def upsert_vector(self, rel_path: str, vector: List[float], model: str) -> None:
        with _LOCK, self.session() as conn:
            conn.execute(
                """
                INSERT INTO memory_vectors(rel_path, vector_json, model, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(rel_path) DO UPDATE SET
                    vector_json=excluded.vector_json,
                    model=excluded.model,
                    created_at=excluded.created_at
                """,
                (rel_path, json.dumps(vector, ensure_ascii=False), model, _now_iso()),
            )

    def get_vector(self, rel_path: str) -> Optional[List[float]]:
        with self.session() as conn:
            row = conn.execute(
                "SELECT vector_json FROM memory_vectors WHERE rel_path=?", (rel_path,)
            ).fetchone()
        return json.loads(row["vector_json"]) if row else None

    def iter_vectors(self, status: Optional[str] = None) -> Iterable[Tuple[str, List[float]]]:
        sql = """
            SELECT v.rel_path, v.vector_json
            FROM memory_vectors v
            JOIN memory_docs d ON d.rel_path = v.rel_path
            WHERE d.status != 'deleted'
        """
        params: List[Any] = []
        if status:
            sql += " AND d.status=?"
            params.append(status)
        with self.session() as conn:
            rows = conn.execute(sql, params).fetchall()
        for r in rows:
            yield r["rel_path"], json.loads(r["vector_json"])

    # ---------------- Stats ----------------
    def stats_overview(self) -> Dict[str, Any]:
        with self.session() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) as total,
                       COALESCE(SUM(size_bytes), 0) as size,
                       MAX(updated_at) as last_updated
                FROM memory_docs WHERE status!='deleted'
                """
            ).fetchone()
            open_loops = conn.execute(
                """
                SELECT COUNT(*) FROM memory_docs
                WHERE status!='deleted' AND open_loops_json != '[]'
                """
            ).fetchone()[0]
        return {
            "total_docs": row["total"],
            "total_size": row["size"],
            "open_loops_count": open_loops,
            "last_updated": row["last_updated"],
        }

    def stats_distribution(self) -> Dict[str, Dict[str, int]]:
        out: Dict[str, Dict[str, int]] = {"by_type": {}, "by_track": {}, "by_status": {}}
        with self.session() as conn:
            for col, key in (("memory_type", "by_type"), ("track", "by_track"), ("status", "by_status")):
                rows = conn.execute(
                    f"SELECT {col}, COUNT(*) as cnt FROM memory_docs GROUP BY {col}"
                ).fetchall()
                out[key] = {r[col] or "unknown": r["cnt"] for r in rows}
        return out

    def stats_timeline(self, days: int = 30) -> List[Dict[str, Any]]:
        with self.session() as conn:
            rows = conn.execute(
                """
                SELECT DATE(updated_at) as date, COUNT(*) as cnt
                FROM memory_docs
                WHERE updated_at >= DATE('now', ?)
                GROUP BY DATE(updated_at)
                ORDER BY date
                """,
                (f"-{days} days",),
            ).fetchall()
        return [{"date": r["date"], "doc_count": r["cnt"], "update_count": r["cnt"]} for r in rows]

    def stats_open_loops(self) -> List[Dict[str, Any]]:
        with self.session() as conn:
            rows = conn.execute(
                """
                SELECT rel_path, title, open_loops_json
                FROM memory_docs
                WHERE status!='deleted' AND open_loops_json != '[]'
                """
            ).fetchall()
        out = []
        for r in rows:
            loops = json.loads(r["open_loops_json"] or "[]")
            for item in loops:
                if isinstance(item, dict):
                    out.append(
                        {
                            "path": r["rel_path"],
                            "title": r["title"] or r["rel_path"],
                            "kind": item.get("kind", "todo"),
                            "item": item.get("item", ""),
                            "priority": item.get("priority", "medium"),
                        }
                    )
                elif isinstance(item, str):
                    out.append(
                        {
                            "path": r["rel_path"],
                            "title": r["title"] or r["rel_path"],
                            "kind": "todo",
                            "item": item,
                            "priority": "medium",
                        }
                    )
        return out

    # ---------------- Chat history ----------------
    def save_message(self, agent_id: str, role: str, content: str,
                     memories: Optional[List[Dict[str, Any]]] = None,
                     thinking: Optional[str] = None) -> None:
        with self.session() as conn:
            conn.execute(
                """
                INSERT INTO chat_history(agent_id, role, content, memories_json, thinking, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (agent_id, role, content,
                 json.dumps(memories or [], ensure_ascii=False),
                 thinking, _now_iso()),
            )

    def load_history(self, agent_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        with self.session() as conn:
            rows = conn.execute(
                """
                SELECT * FROM chat_history WHERE agent_id=?
                ORDER BY id DESC LIMIT ?
                """,
                (agent_id, limit),
            ).fetchall()
        out = []
        for r in reversed(rows):
            out.append(
                {
                    "role": r["role"],
                    "content": r["content"],
                    "memories": json.loads(r["memories_json"] or "[]"),
                    "thinking": r["thinking"],
                    "created_at": r["created_at"],
                }
            )
        return out

    # ---------------- Chat sessions (v2) ----------------
    def create_session(self, sess: Dict[str, Any]) -> Dict[str, Any]:
        now = _now_iso()
        row = {
            "id": sess["id"],
            "title": sess.get("title") or "新会话",
            "profile_id": sess.get("profile_id") or "",
            "space_name": sess.get("space_name") or "",
            "search_strategy": sess.get("search_strategy") or "auto",
            "top_k": int(sess.get("top_k") or 5),
            "use_rerank": 1 if sess.get("use_rerank", True) else 0,
            "save_to_space": sess.get("save_to_space") or "",
            "created_at": now,
            "updated_at": now,
        }
        with self.session() as conn:
            conn.execute(
                """
                INSERT INTO chat_sessions(
                    id, title, profile_id, space_name, search_strategy,
                    top_k, use_rerank, save_to_space, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (row["id"], row["title"], row["profile_id"], row["space_name"],
                 row["search_strategy"], row["top_k"], row["use_rerank"],
                 row["save_to_space"], row["created_at"], row["updated_at"]),
            )
        return row

    def update_session(self, sid: str, **fields: Any) -> Optional[Dict[str, Any]]:
        allowed = {"title", "profile_id", "space_name", "search_strategy",
                   "top_k", "use_rerank", "save_to_space"}
        sets: List[str] = []
        vals: List[Any] = []
        for k, v in fields.items():
            if k in allowed:
                sets.append(f"{k}=?")
                vals.append(int(v) if k == "top_k" else (1 if v else 0 if k == "use_rerank" else v))
        if not sets:
            return self.get_session(sid)
        sets.append("updated_at=?")
        vals.append(_now_iso())
        vals.append(sid)
        with self.session() as conn:
            conn.execute(f"UPDATE chat_sessions SET {', '.join(sets)} WHERE id=?", vals)
        return self.get_session(sid)

    def get_session(self, sid: str) -> Optional[Dict[str, Any]]:
        with self.session() as conn:
            row = conn.execute(
                "SELECT * FROM chat_sessions WHERE id=?", (sid,)
            ).fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "title": row["title"],
            "profile_id": row["profile_id"],
            "space_name": row["space_name"],
            "search_strategy": row["search_strategy"],
            "top_k": row["top_k"],
            "use_rerank": bool(row["use_rerank"]),
            "save_to_space": row["save_to_space"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def list_sessions(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self.session() as conn:
            rows = conn.execute(
                "SELECT * FROM chat_sessions ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        out = []
        for r in rows:
            out.append({
                "id": r["id"],
                "title": r["title"],
                "profile_id": r["profile_id"],
                "space_name": r["space_name"],
                "search_strategy": r["search_strategy"],
                "top_k": r["top_k"],
                "use_rerank": bool(r["use_rerank"]),
                "save_to_space": r["save_to_space"],
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
            })
        # 补 message_count
        for s in out:
            with self.session() as conn:
                row = conn.execute(
                    "SELECT COUNT(*) AS c FROM chat_session_messages WHERE session_id=?",
                    (s["id"],),
                ).fetchone()
            s["message_count"] = row["c"] if row else 0
        return out

    def delete_session(self, sid: str) -> bool:
        with self.session() as conn:
            cur = conn.execute("DELETE FROM chat_sessions WHERE id=?", (sid,))
            conn.execute("DELETE FROM chat_session_messages WHERE session_id=?", (sid,))
            return (cur.rowcount or 0) > 0

    def append_session_message(self, sid: str, role: str, content: str,
                               memories: Optional[List[Dict[str, Any]]] = None,
                               thinking: Optional[str] = None,
                               trace: Optional[List[Dict[str, Any]]] = None) -> int:
        now = _now_iso()
        with self.session() as conn:
            cur = conn.execute(
                """
                INSERT INTO chat_session_messages(
                    session_id, role, content, memories_json, thinking, trace_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (sid, role, content,
                 json.dumps(memories or [], ensure_ascii=False),
                 thinking,
                 json.dumps(trace or [], ensure_ascii=False),
                 now),
            )
            conn.execute(
                "UPDATE chat_sessions SET updated_at=? WHERE id=?", (now, sid)
            )
            return int(cur.lastrowid or 0)

    def load_session_messages(self, sid: str, limit: int = 200) -> List[Dict[str, Any]]:
        with self.session() as conn:
            rows = conn.execute(
                """
                SELECT * FROM chat_session_messages
                WHERE session_id=?
                ORDER BY id ASC LIMIT ?
                """,
                (sid, limit),
            ).fetchall()
        out = []
        for r in rows:
            out.append({
                "id": r["id"],
                "role": r["role"],
                "content": r["content"],
                "memories": json.loads(r["memories_json"] or "[]"),
                "thinking": r["thinking"],
                "trace": json.loads(r["trace_json"] or "[]"),
                "created_at": r["created_at"],
            })
        return out

    # ---------------- Audit ----------------
    def audit(self, action: str, target: str, detail: str = "") -> None:
        with self.session() as conn:
            conn.execute(
                "INSERT INTO audit_log(action, target, detail, created_at) VALUES (?, ?, ?, ?)",
                (action, target, detail, _now_iso()),
            )

    # ---------------- Helpers ----------------
    @staticmethod
    def _row_to_doc(row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "rel_path": row["rel_path"],
            "title": row["title"],
            "memory_type": row["memory_type"],
            "track": row["track"],
            "project_id": row["project_id"],
            "status": row["status"],
            "summary": row["summary"],
            "keywords": json.loads(row["keywords_json"] or "[]"),
            "open_loops": json.loads(row["open_loops_json"] or "[]"),
            "frontmatter": json.loads(row["frontmatter_json"] or "{}"),
            "size_bytes": row["size_bytes"],
            "indexed_at": row["indexed_at"],
            "verified_at": row["verified_at"],
            "updated_at": row["updated_at"],
            "created_at": row["created_at"],
        }


db = Database()
