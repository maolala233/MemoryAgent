"""Markdown frontmatter parsing helpers."""
from __future__ import annotations

import re
from typing import Dict, Any, Tuple, List

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.DOTALL)


def split_frontmatter(text: str) -> Tuple[Dict[str, Any], str]:
    """Return (frontmatter dict, body) from a markdown string."""
    if not text:
        return {}, ""
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    raw_meta, body = match.group(1), match.group(2)
    meta = _parse_simple_yaml(raw_meta)
    return meta, body


def _parse_simple_yaml(raw: str) -> Dict[str, Any]:
    """Tiny YAML parser for flat frontmatter with common types."""
    out: Dict[str, Any] = {}
    current_key: str = ""
    current_list: List[str] = []
    in_list = False

    def flush_list() -> None:
        nonlocal in_list, current_list, current_key
        if in_list and current_key:
            out[current_key] = current_list
        in_list = False
        current_list = []

    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("- ") and in_list:
            current_list.append(stripped[2:].strip().strip('"').strip("'"))
            continue
        if ":" in stripped:
            flush_list()
            key, _, value = stripped.partition(":")
            key = key.strip()
            value = value.strip()
            if value == "":
                current_key = key
                in_list = True
                current_list = []
            else:
                out[key] = _coerce(value)
    flush_list()
    return out


def _coerce(value: str) -> Any:
    if not value:
        return ""
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1]
        return [v.strip().strip('"').strip("'") for v in inner.split(",") if v.strip()]
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]
    low = value.lower()
    if low in ("true", "false"):
        return low == "true"
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value


def build_frontmatter(meta: Dict[str, Any]) -> str:
    """Serialize a dict back to YAML-ish frontmatter."""
    if not meta:
        return ""
    lines = ["---"]
    for key, value in meta.items():
        if isinstance(value, list):
            if not value:
                lines.append(f"{key}: []")
            else:
                lines.append(f"{key}:")
                for item in value:
                    lines.append(f"  - {item}")
        elif isinstance(value, bool):
            lines.append(f"{key}: {'true' if value else 'false'}")
        elif isinstance(value, (int, float)):
            lines.append(f"{key}: {value}")
        elif value is None:
            lines.append(f"{key}:")
        else:
            escaped = str(value).replace('"', '\\"')
            lines.append(f'{key}: "{escaped}"')
    lines.append("---")
    return "\n".join(lines)


def compose_markdown(meta: Dict[str, Any], body: str) -> str:
    fm = build_frontmatter(meta)
    if not fm:
        return body
    return f"{fm}\n\n{body}"


def extract_title(body: str, rel_path: str) -> str:
    for line in body.splitlines():
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
    return rel_path.rsplit("/", 1)[-1].rsplit(".", 1)[0]


def extract_open_loops(body: str) -> List[Dict[str, Any]]:
    """Detect TODO / FIXME / OPEN items."""
    loops: List[Dict[str, Any]] = []
    markers = ("- [ ]", "TODO:", "FIXME:", "OPEN:")
    for line in body.splitlines():
        stripped = line.strip()
        for marker in markers:
            if stripped.startswith(marker):
                item = stripped[len(marker):].strip()
                if item:
                    loops.append({"kind": "todo", "item": item, "priority": "medium"})
                break
    return loops
