"""Neo4j-backed implementation of the GraphStore port.

Stores directed relationships as Neo4j graph edges with batched
write-behind buffering. Nodes are automatically created by MERGE.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple

from neo4j import GraphDatabase

from ..domain.types import Uid
from ..ports.graph_store import GraphStore
from .config import Neo4jConfig


class Neo4jGraphStore(GraphStore):
    """Graph store backed by a Neo4j graph database.

    Relationships are buffered in pending lists and flushed to Neo4j
    on explicit flush() calls. Nodes are named by their Uid; edges
    carry a type label and a properties dictionary.

    Attributes:
        _cfg: Neo4j connection configuration.
        _driver: Neo4j Python driver instance.
        _pending_upserts: Batched edge inserts (source, target, type, props).
        _pending_deletes: Batched edge deletes (source, target, type).
        _pending_nodes: Batched node upserts (uid, props, labels).
    """

    def __init__(self, *, config: Optional[Neo4jConfig] = None):
        self._cfg = config or Neo4jConfig()
        self._driver = GraphDatabase.driver(
            self._cfg.uri, auth=(self._cfg.user, self._cfg.password)
        )
        self._pending_upserts: List[tuple[Uid, Uid, str, Dict[str, Any]]] = []
        self._pending_deletes: List[tuple[Uid, Uid, Optional[str]]] = []
        # 节点属性 buffer:每条 (uid, properties, labels) 在 flush() 时合并写入
        self._pending_nodes: List[tuple[Uid, Dict[str, Any], Tuple[str, ...]]] = []

    # ------------------------------------------------------------------
    # 节点操作
    # ------------------------------------------------------------------
    def upsert_node(
        self,
        uid: Uid,
        properties: Optional[Dict[str, Any]] = None,
        labels: Optional[Iterable[str]] = None,
    ) -> None:
        """Buffer a node upsert.

        与边一样,采用 write-back 模式,在 flush() 时一次性写入,
        避免每个节点都跑一次 Cypher。
        """
        clean_props: Dict[str, Any] = {"uid": str(uid)}
        for k, v in (properties or {}).items():
            if k.startswith("_") or v is None:
                continue
            try:
                import json as _json
                _json.dumps(v)
                clean_props[k] = v
            except (TypeError, ValueError):
                clean_props[k] = str(v)
        clean_labels = tuple(
            {str(lbl).strip() for lbl in (labels or []) if str(lbl).strip()}
        )
        self._pending_nodes.append((Uid(str(uid)), clean_props, clean_labels))

    def get_node(self, uid: Uid) -> Optional[Dict[str, Any]]:
        """Return node properties for *uid* or ``None`` if missing."""
        query = "MATCH (n {uid: $uid}) RETURN properties(n) AS props LIMIT 1"
        with self._driver.session(database=self._cfg.database) as sess:
            rec = sess.run(query, uid=str(uid)).single()
            if not rec:
                return None
            props = rec.get("props") or {}
            return dict(props) if isinstance(props, dict) else None

    def upsert_relationship(
        self, source: Uid, target: Uid, rel_type: str, properties: Dict[str, Any]
    ) -> None:
        """Buffer an edge upsert for the next flush.

        Args:
            source: Source node Uid.
            target: Target node Uid.
            rel_type: Relationship type string.
            properties: Key-value edge metadata.
        """
        self._pending_upserts.append(
            (Uid(str(source)), Uid(str(target)), str(rel_type), dict(properties))
        )

    def delete_relationship(
        self, source: Uid, target: Uid, rel_type: Optional[str] = None
    ) -> None:
        """Buffer an edge deletion for the next flush.

        Args:
            source: Source node Uid.
            target: Target node Uid.
            rel_type: If provided, only delete edges of this type.
        """
        self._pending_deletes.append((Uid(str(source)), Uid(str(target)), rel_type))

    def get_relationship(
        self, source: Uid, target: Uid, rel_type: str
    ) -> Optional[Dict[str, Any]]:
        """Query a specific relationship directly from Neo4j.

        Args:
            source: Source node Uid.
            target: Target node Uid.
            rel_type: Relationship type to look up.

        Returns:
            Edge properties dict if found, or None.
        """
        s = str(source)
        t = str(target)
        rt = str(rel_type)
        query = (
            "MATCH (a {uid: $s})-[r]->(b {uid: $t}) "
            "WHERE type(r) = $rt RETURN properties(r) AS props LIMIT 1"
        )
        with self._driver.session(database=self._cfg.database) as sess:
            rec = sess.run(query, s=s, t=t, rt=rt).single()
            if not rec:
                return None
            props = rec.get("props")
            return dict(props) if isinstance(props, dict) else {}

    def get_neighbors(
        self, uid: Uid, *, rel_type: Optional[str] = None, direction: str = "out"
    ) -> List[Uid]:
        """Return neighbors reachable via outgoing or incoming edges.

        Args:
            uid: The node whose neighbors are requested.
            rel_type: Optional filter for edge type.
            direction: \"out\" for successors, \"in\" for predecessors.

        Returns:
            List of neighbor Uids.

        Raises:
            ValueError: If direction is not \"out\" or \"in\".
        """
        u = str(uid)
        if direction not in {"out", "in"}:
            raise ValueError("direction must be 'out' or 'in'")

        if direction == "out":
            pat = "(a {uid: $u})-[r]->(b)"
            ret = "b.uid as uid"
        else:
            pat = "(a)-[r]->(b {uid: $u})"
            ret = "a.uid as uid"

        where = "" if rel_type is None else "WHERE type(r) = $rt"
        query = f"MATCH {pat} {where} RETURN {ret}"
        params = {"u": u}
        if rel_type is not None:
            params["rt"] = str(rel_type)

        out: List[Uid] = []
        with self._driver.session(database=self._cfg.database) as sess:
            for rec in sess.run(query, **params):
                v = rec.get("uid")
                if v is not None:
                    out.append(Uid(str(v)))
        return out

    def flush(self) -> None:
        """Write all buffered upserts and deletes to Neo4j in a single session."""
        if (
            not self._pending_upserts
            and not self._pending_deletes
            and not self._pending_nodes
        ):
            return

        with self._driver.session(database=self._cfg.database) as sess:
            for s, t, rel_type in self._pending_deletes:
                if rel_type is None:
                    q = (
                        "MATCH (a {uid: $s})-[r]->(b {uid: $t}) DELETE r"
                    )
                    sess.run(q, s=str(s), t=str(t))
                else:
                    q = (
                        "MATCH (a {uid: $s})-[r]->(b {uid: $t}) "
                        "WHERE type(r) = $rt DELETE r"
                    )
                    sess.run(q, s=str(s), t=str(t), rt=str(rel_type))

            # 1) 节点属性 + labels(去重:同一 uid 后写覆盖前写,labels 取并集)
            node_accum: Dict[str, Dict[str, Any]] = {}
            node_labels: Dict[str, set] = {}
            for uid, props, labels in self._pending_nodes:
                key = str(uid)
                acc = node_accum.setdefault(key, {"uid": key})
                for k, v in props.items():
                    if v is not None:
                        acc[k] = v
                if labels:
                    node_labels.setdefault(key, set()).update(labels)

            for uid_key, props in node_accum.items():
                labels_iter = sorted(node_labels.get(uid_key, set()))
                # Neo4j label 名只允许字母数字下划线,把中文/特殊字符替成 _
                import re as _re
                safe_labels = [
                    _re.sub(r"[^A-Za-z0-9_]", "_", lbl) for lbl in labels_iter
                ]
                label_clause = (
                    ":" + ":".join(safe_labels) if safe_labels else ""
                )
                # SET n += props 是合并更新,不会清空已有属性
                q = f"MERGE (n {{uid:$uid}}){label_clause} SET n += $props"
                sess.run(q, uid=uid_key, props=props)

            # 2) 边
            for s, t, rt, props in self._pending_upserts:
                q = (
                    "MERGE (a {uid: $s}) "
                    "MERGE (b {uid: $t}) "
                    f"MERGE (a)-[r:{rt}]->(b) "
                    "SET r += $props"
                )
                sess.run(q, s=str(s), t=str(t), props=props)

        self._pending_upserts.clear()
        self._pending_deletes.clear()
        self._pending_nodes.clear()

    def get_all_edges(self):
        """Return all (source, target, rel_type, properties) edges from Neo4j."""
        query = (
            "MATCH (a)-[r]->(b) "
            "RETURN a.uid AS s, b.uid AS t, type(r) AS rt, properties(r) AS props"
        )
        out: List[Tuple[Uid, Uid, str, Dict[str, Any]]] = []
        with self._driver.session(database=self._cfg.database) as sess:
            for rec in sess.run(query):
                s = rec.get("s")
                t = rec.get("t")
                if s is None or t is None:
                    continue
                rt = rec.get("rt") or ""
                props = rec.get("props") or {}
                out.append((Uid(str(s)), Uid(str(t)), str(rt), dict(props)))
        return out

    def clear(self) -> None:
        """Delete all relationships and nodes in the configured database."""
        with self._driver.session(database=self._cfg.database) as sess:
            sess.run("MATCH (n) DETACH DELETE n")
        self._pending_upserts.clear()
        self._pending_deletes.clear()
        self._pending_nodes.clear()
