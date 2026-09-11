#!/usr/bin/env python3
"""Read-only inventory checker for crwu-audit asset and business skills.

源仓维护工具：以 `--repo-root <源仓>` 定位技能树（skills/ 下的 crwu-audit 族），
用于源仓一致性盘点与门禁，运行时不需要它。
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import datetime
import json
from pathlib import Path
import re
import sys
from typing import Iterable, Sequence


REPORT_SCHEMA = "crwu.audit-skill-maintainer.report.v1"
# Canonical crwu-dws artifacts (see crwu-dws cache: 目录快照.json / node-index.json).
DIR_SNAPSHOT_SCHEMA = "crwu.kb-dir-snapshot.v1"
KB_NODE_INDEX_SCHEMA = "crwu.kb-node-index.v1"
# Older nested/legacy shapes kept accepted so existing fixtures and snapshots still load.
SNAPSHOT_SCHEMA = "crwu.kb-catalog.snapshot.v1"
NODE_INDEX_SCHEMA = "crwu.kb-dir-cache.nodeindex.v1"
REQUIRED_REFERENCES = (
    "00-applicability.md",
    "01-kb-assembly.md",
    "02-review-focus.md",
)
AXIS_ROOTS = {
    "asset": "02-资产类型/",
    "business": "01-业务路线/",
}
# Report-shape-independent public capabilities. They are deliberately outside the
# asset/business first-level-root model (their assembly keys live under `06-规则库/`
# and may be more than one path), so they must not be forced into AXIS_ROOTS.
PUBLIC_AXIS = "public"
# Public capabilities are cross-cutting, so they are not held to the asset/business leaf
# naming (`00-applicability/01-kb-assembly/02-review-focus`). What they must not lack is a
# declared KB assembly table: without it the skill has no addressable rule material at all.
PUBLIC_ASSEMBLY_REFERENCES = ("01-kb-assembly.md", "00-KB装配表.md")
AXIS_SKILL_PREFIX = {
    "asset": "crwu-audit-asset-",
    "business": "crwu-audit-biz-",
}
LEGACY_BUSINESS_PREFIX = "crwu-audit-business-"
# Optional shared review layer of a first-level business directory: when the knowledge
# base ships it, the business skill must download and reference it for every subroute.
BUSINESS_COMMON_REVIEW_DOC = "共同审核点"

# ---- 路由层（router ↔ 目录 ↔ 注册表 ↔ 真实 Skill）----
ROUTER_SKILL = "crwu-audit"
ROUTER_REFERENCES = (
    "00-input-and-route-profile.md",
    "02-scope-classification.md",
    "03-asset-classification.md",
    "04-business-classification.md",
    "05-method-classification.md",
    "06-overlay-classification.md",
    "07-skill-registry.md",
    "08-union-dispatch-rules.md",
    "10-capability-gap-proposal.md",
    "99-maintenance.md",
)
# Leaf-owned reference names: the router may name them in prose without owning them.
LEAF_OWNED_REFERENCES = ("00-applicability.md", "01-kb-assembly.md", "02-review-focus.md")
# Catalog axis -> the union-dispatch input variable that must exist for it.
AXIS_DISPATCH_INPUT = {"asset": "asset_skills", "business": "business_skills"}
# Concrete skill names only: excludes wildcards (crwu-audit-asset-*) and placeholders
# (crwu-audit-<axis>-<label>) and longer identifiers such as design-crwu-audit-skills.md.
_SKILL_TOKEN_RE = re.compile(r"(?<![a-z0-9-])crwu-audit-[a-z0-9][a-z0-9-]*(?![a-z0-9*<-])")
_REFERENCE_TOKEN_RE = re.compile(r"(?<![0-9a-z-])(\d\d-[a-z0-9-]+\.md)")
# Skills that are deliberately not axis leaves (router, maintainers, cross-axis
# capabilities), so they are exempt from the asset/biz leaf naming rule.
NON_LEAF_SKILLS = {
    "crwu-audit",
    "crwu-audit-optimize",
    "crwu-audit-skill-maintainer",
    "crwu-audit-datacheck",
}

KNOWN_SKILL_SUFFIXES = {
    ("asset", "房地产"): "realestate",
    ("asset", "机器设备"): "equipment",
    ("asset", "设备"): "equipment",
    ("asset", "无形资产"): "intangible",
    ("asset", "企业价值"): "enterprise-value",
    ("asset", "矿业权"): "mining-right",
    ("asset", "存货"): "inventory",
    ("asset", "债权"): "debt",
    ("asset", "资产组合"): "portfolio",
    ("asset", "交通运输设备"): "transport-equipment",
    ("asset", "资产组-含商誉"): "asset-group-goodwill",
    ("asset", "废旧物资"): "scrap-materials",
    ("asset", "其他"): "other",
    ("business", "资产经营"): "asset-operation",
    ("business", "交易与处置"): "transaction-disposal",
    ("business", "财务报告"): "financial-reporting",
    ("business", "融资与债务"): "financing-debt",
    ("business", "投资与资本运作"): "investment-capital",
    ("business", "税务与历史确认"): "tax-history",
    ("business", "司法清算与补偿"): "judicial-liquidation-compensation",
    ("business", "咨询复核与其他"): "consulting-review",
}


@dataclass(frozen=True)
class Catalog:
    source_schema: str
    generated_at: str | None
    complete: bool | None
    paths: tuple[str, ...]


@dataclass(frozen=True)
class RegistryRow:
    axis: str
    label: str
    skill: str
    status: str
    load_behavior: str


def _normalize_path(raw: str, *, folder: bool | None = None) -> str:
    path = raw.strip().replace("\\", "/")
    path = re.sub(r"/+", "/", path).strip("/")
    if not path:
        return ""
    if folder is True or (folder is None and raw.strip().endswith("/")):
        return f"{path}/"
    return path


def _label(name: str) -> str:
    value = name.strip().strip("/")
    value = re.sub(r"(?i)(?:\.md)+$", "", value)
    return re.sub(r"^\d+[-_、.．]\s*", "", value).strip()


def _is_ignored_label(name: str) -> bool:
    normalized = _label(name).casefold()
    return normalized == "todo" or normalized.endswith("- todo")


# `crwu-dws` writes its `目录树.md` as `/ <folder>` and `- <doc>` with indentation as
# depth. Header lines (`- fetched_at: …`) precede the first folder and are metadata, not nodes.
SLASH_TREE_LINE = re.compile(r"^(?P<indent>[ \t]*)(?P<marker>[/-])\s+(?P<name>\S.*?)\s*$")


def _parse_markdown_tree(text: str) -> tuple[str, ...]:
    """A pasted directory tree, in either published form (icon tree first, then slash tree)."""
    return _parse_icon_tree(text) or _parse_slash_tree(text)


def _parse_icon_tree(text: str) -> tuple[str, ...]:
    paths: set[str] = set()
    folders: list[str] = []
    bullet = re.compile(
        r"^(?P<indent>[ \t]*)[-*]\s+(?P<icon>📁|📄)\s+(?P<name>.+?)\s*$"
    )
    for line in text.splitlines():
        match = bullet.match(line)
        if not match:
            continue
        indent = match.group("indent").replace("\t", "  ")
        level = len(indent) // 2
        name = match.group("name").strip()
        is_folder = match.group("icon") == "📁" or name.endswith("/")
        clean_name = name.rstrip("/").strip()
        folders = folders[:level]
        full = "/".join([*folders, clean_name])
        normalized = _normalize_path(full, folder=is_folder)
        if normalized:
            paths.add(normalized)
        if is_folder:
            folders.append(clean_name)
    return tuple(sorted(paths))


def _parse_slash_tree(text: str) -> tuple[str, ...]:
    """`crwu-dws` `目录树.md`: `/ <folder>` / `- <doc>`, indentation = folder depth."""
    paths: set[str] = set()
    folders: list[str] = []
    started = False
    for line in text.splitlines():
        match = SLASH_TREE_LINE.match(line)
        if not match:
            continue
        is_folder = match.group("marker") == "/"
        if not started:
            if not is_folder:
                continue  # metadata block before the first folder line
            started = True
        indent = match.group("indent").replace("\t", "  ")
        level = len(indent) // 2
        clean_name = match.group("name").strip().rstrip("/").strip()
        if not clean_name:
            continue
        folders = folders[:level]
        normalized = _normalize_path("/".join([*folders, clean_name]), folder=is_folder)
        if normalized:
            paths.add(normalized)
        if is_folder:
            folders.append(clean_name)
    return tuple(sorted(paths))


def _walk_snapshot(nodes: Iterable[object], parents: tuple[str, ...] = ()) -> Iterable[str]:
    for raw_node in nodes:
        if not isinstance(raw_node, dict):
            continue
        name = raw_node.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        node_type = raw_node.get("type")
        is_folder = node_type == "folder"
        parts = (*parents, name.strip().strip("/"))
        yield _normalize_path("/".join(parts), folder=is_folder)
        children = raw_node.get("children")
        if isinstance(children, list):
            yield from _walk_snapshot(children, parts if is_folder else parents)


def _parent_link(node: dict) -> str | None:
    """Authoritative snapshot field is `parentFolderId`; `parentId` is a legacy alias."""
    for field in ("parentFolderId", "parentId"):
        value = node.get(field)
        if isinstance(value, str) and value:
            return value
    return None


def _paths_from_flat_nodes(nodes: Iterable[object]) -> Iterable[str]:
    """Flat snapshot form: rebuild each path by walking the parent link up to a root."""
    by_id: dict[str, dict] = {}
    for raw_node in nodes:
        if not isinstance(raw_node, dict):
            continue
        node_id = raw_node.get("nodeId")
        if isinstance(node_id, str) and node_id:
            by_id[node_id] = raw_node
    for node in by_id.values():
        parts: list[str] = []
        seen: set[str] = set()
        cursor: dict | None = node
        while isinstance(cursor, dict):
            cursor_id = cursor.get("nodeId")
            if cursor_id in seen:
                parts = []  # broken parent chain; refuse to guess a path
                break
            if isinstance(cursor_id, str):
                seen.add(cursor_id)
            name = cursor.get("name")
            if isinstance(name, str) and name.strip():
                parts.append(name.strip().strip("/"))
            cursor = by_id.get(_parent_link(cursor) or "")
        if not parts:
            continue
        yield _normalize_path("/".join(reversed(parts)), folder=node.get("type") == "folder")


def _paths_from_snapshot_nodes(nodes: Iterable[object]) -> Iterable[str]:
    """crwu-dws directory snapshot: authoritative form nests nodes via `children`
    (`crwu-dws/references/00-目录快照schema.md`); a flat list linked by `parentFolderId`
    (legacy alias `parentId`) is tolerated so older snapshots still load."""
    node_list = [n for n in nodes if isinstance(n, dict)]
    if any(isinstance(n.get("children"), list) and n["children"] for n in node_list):
        return _walk_snapshot(node_list)
    return _paths_from_flat_nodes(node_list)


# Capture-time field names vary by producer. `crwu-dws` writes snake_case
# (`fetched_at`, `built_from_snapshot_at`); the older flat probe wrote camelCase
# (`fetchedAt`); the catalog snapshot form uses `generated_at`. All are accepted so a
# real crwu-dws artifact is never rejected as "carries no readable capture time".
CAPTURE_TIME_FIELDS = (
    "fetched_at",
    "fetchedAt",
    "generated_at",
    "generatedAt",
    "built_from_snapshot_at",
    "builtFromSnapshotAt",
)


def _capture_time(data: dict, *fields: str) -> str | None:
    """First non-empty capture timestamp among `fields` (default: all known aliases)."""
    for field in fields or CAPTURE_TIME_FIELDS:
        value = data.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _paths_from_node_index(data: dict, nodes: object = None) -> Iterable[str]:
    """Node index in either naming convention.

    `crwu-dws` writes camelCase maps (`byNodeId` / `byPath` / `byName`) keyed by nodeId;
    `crwu-dws/references/02` documents the snake_case form (`by_node_id` / `by_path`).
    `byPath` keys already are full library paths, so they win when present. Folder-ness comes
    from the entry's `type` (the camelCase form carries no trailing `/` on folder keys).
    """
    for key in ("byPath", "by_path"):
        by_path = data.get(key)
        if isinstance(by_path, dict) and by_path:
            for raw_key, value in by_path.items():
                is_folder: bool | None = None
                if isinstance(value, dict) and isinstance(value.get("type"), str):
                    is_folder = value["type"] == "folder"
                elif str(raw_key).endswith("/"):
                    is_folder = True
                normalized = _normalize_path(str(raw_key), folder=is_folder)
                if normalized:
                    yield normalized
            return
    for key in ("byNodeId", "by_node_id"):
        by_node = data.get(key)
        if isinstance(by_node, dict) and by_node:
            yield from _paths_from_node_values(by_node)
            return
    if isinstance(nodes, dict) and nodes:
        yield from _paths_from_node_values(nodes)
        return
    raise ValueError("node index carries no readable byPath/byNodeId/nodes map")


def _paths_from_node_values(by_node: dict) -> Iterable[str]:
    for value in by_node.values():
        if not isinstance(value, dict):
            continue
        raw_path = value.get("path")
        if not isinstance(raw_path, str) or not raw_path.strip():
            continue
        yield _normalize_path(raw_path, folder=value.get("type") == "folder")


def _snapshot_is_complete(data: dict) -> bool | None:
    """A snapshot is only usable as path truth when every page came back.

    A non-empty `failures` list always wins. Then, in order: a top-level `complete`
    boolean (`crwu-dws` writes it there, alongside `truncated`), `stats.complete`
    (`crwu-dws/references/00` §3), and finally a legacy top-level `evidence[]` receipt list.
    """
    failures = data.get("failures")
    if isinstance(failures, list) and failures:
        return False
    if data.get("truncated") is True:
        return False
    if isinstance(data.get("complete"), bool):
        return data["complete"]
    stats = data.get("stats")
    if isinstance(stats, dict) and isinstance(stats.get("complete"), bool):
        return stats["complete"]
    evidence = data.get("evidence")
    if not isinstance(evidence, list):
        return True if isinstance(failures, list) else None
    for receipt in evidence:
        if not isinstance(receipt, dict):
            return None
        if receipt.get("hasMore") is True or receipt.get("autoPageComplete") is False:
            return False
    return True


def load_catalog(path: Path) -> Catalog:
    text = path.read_text(encoding="utf-8")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        paths = _parse_markdown_tree(text)
        if not paths:
            raise ValueError("catalog is neither supported JSON nor a pasted Markdown directory tree")
        captured = re.search(r"(?:抓取时间|fetched_at|fetchedAt)\s*[：:]\s*([^\s]+)", text)
        generated_at = captured.group(1) if captured else None
        return Catalog("markdown-tree", generated_at, None, paths)

    if not isinstance(data, dict):
        raise ValueError("catalog JSON root must be an object")
    schema = data.get("schema")
    if schema == DIR_SNAPSHOT_SCHEMA:
        nodes = data.get("nodes")
        if not isinstance(nodes, list):
            raise ValueError("directory snapshot nodes must be a list")
        return Catalog(
            DIR_SNAPSHOT_SCHEMA,
            _capture_time(data),
            _snapshot_is_complete(data),
            tuple(sorted(set(_paths_from_snapshot_nodes(nodes)))),
        )
    if schema == KB_NODE_INDEX_SCHEMA:
        return Catalog(
            KB_NODE_INDEX_SCHEMA,
            _capture_time(data),
            _snapshot_is_complete(data),
            tuple(sorted(set(_paths_from_node_index(data, data.get("nodes"))))),
        )
    if schema == SNAPSHOT_SCHEMA:
        nodes = data.get("nodes")
        if not isinstance(nodes, list):
            raise ValueError("snapshot nodes must be a list")
        stats = data.get("stats") if isinstance(data.get("stats"), dict) else {}
        return Catalog(
            SNAPSHOT_SCHEMA,
            _capture_time(data, "generated_at", "generatedAt"),
            stats.get("complete") if isinstance(stats.get("complete"), bool) else None,
            tuple(sorted(set(_walk_snapshot(nodes)))),
        )
    if schema == NODE_INDEX_SCHEMA:
        return Catalog(
            NODE_INDEX_SCHEMA,
            _capture_time(data, "built_from_snapshot_at", "builtFromSnapshotAt", "fetched_at", "fetchedAt"),
            _snapshot_is_complete(data),
            tuple(sorted(set(_paths_from_node_index(data)))),
        )
    raise ValueError(f"unsupported catalog schema: {schema!r}")


def _table_cells(line: str) -> tuple[str, ...] | None:
    if "|" not in line:
        return None
    cells = []
    for cell in line.strip().strip("|").split("|"):
        value = cell.strip()
        inline = re.fullmatch(r"`([^`]*)`", value)
        cells.append((inline.group(1) if inline else value).strip())
    return tuple(cells)


def _is_separator(cells: tuple[str, ...]) -> bool:
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in cells)


def _read_registry(path: Path) -> list[RegistryRow]:
    if not path.is_file():
        return []
    rows: list[RegistryRow] = []
    in_table = False
    for line in path.read_text(encoding="utf-8").splitlines():
        cells = _table_cells(line)
        if cells is None:
            if in_table and rows:
                break
            continue
        lowered = tuple(cell.casefold() for cell in cells)
        if lowered == ("axis", "label", "skill", "status", "load behavior"):
            in_table = True
            continue
        if not in_table or len(cells) != 5 or _is_separator(cells):
            continue
        rows.append(RegistryRow(*cells))
    return rows


def _immediate_folder_children(paths: set[str], parent: str) -> list[str]:
    prefix = _normalize_path(parent, folder=True)
    children = []
    for path in paths:
        if not path.endswith("/") or not path.startswith(prefix) or path == prefix:
            continue
        remainder = path[len(prefix) :].rstrip("/")
        if remainder and "/" not in remainder:
            children.append(remainder)
    return sorted(children)


def _direct_docs(paths: set[str], parent: str) -> list[str]:
    prefix = _normalize_path(parent, folder=True)
    docs = []
    for path in paths:
        if path.endswith("/") or not path.startswith(prefix):
            continue
        remainder = path[len(prefix) :]
        if remainder and "/" not in remainder:
            docs.append(remainder)
    return sorted(docs)


def _find_named_folder(paths: set[str], parent: str, label: str) -> str | None:
    for child in _immediate_folder_children(paths, parent):
        if _label(child) == label:
            return f"{_normalize_path(parent, folder=True)}{child}/"
    return None


def _named_doc(paths: set[str], parent: str, label: str) -> str | None:
    """Exact library node name of a direct child document carrying `label`, or None."""
    for name in _direct_docs(paths, parent):
        if _label(name) == label:
            return name
    return None


def _has_named_doc(paths: set[str], parent: str, label: str) -> bool:
    return _named_doc(paths, parent, label) is not None


def _references_common_review(text: str, kb_root: str, doc_name: str) -> bool:
    """Does the skill positively address the shared review layer by its library path key?

    Naming the document is not enough: a leaf that says "一级根**未提供** `共同审核点`" mentions it
    too, and a plain `in` test would let that stale claim pass (the exact field bug this fixes).
    The reference must therefore carry the first-level root (`<kb_root><节点名>`). Both the catalog
    node name and the bare label are accepted, because older libraries prefix/suffix node names
    (`01-共同审核点.md`) while the current one ships `共同审核点` verbatim.
    """
    prefix = _normalize_path(kb_root, folder=True)
    candidates = {BUSINESS_COMMON_REVIEW_DOC, doc_name, _label(doc_name)}
    return any(f"{prefix}{candidate}" in text for candidate in candidates if candidate)


def _frontmatter_name(path: Path) -> str | None:
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    match = re.search(r"(?m)^name:\s*([^\s#]+)\s*$", text)
    return match.group(1).strip() if match else None


def _extract_kb_paths(text: str) -> list[str]:
    matches = re.findall(r"(?:01-业务路线|02-资产类型)/[^`\n|<]+", text)
    return sorted({_normalize_path(match.strip()) for match in matches if match.strip()})


def _first_level_root(path: str) -> str | None:
    normalized = _normalize_path(path, folder=path.endswith("/"))
    parts = normalized.rstrip("/").split("/")
    if len(parts) < 2 or parts[0] not in {"01-业务路线", "02-资产类型"}:
        return None
    return f"{parts[0]}/{parts[1]}/"


def _declared_first_level_roots(text: str) -> set[str]:
    """Every first-level knowledge root a skill's assembly references, directly or deeper."""
    roots = (_first_level_root(path) for path in _extract_kb_paths(text))
    return {root for root in roots if root}


# ---- 库内路径键存在性（公共轴也查）----
# Backticked spans are the skill convention for addressing keys; plain prose is not scanned.
_BACKTICKED_RE = re.compile(r"`([^`\n]+)`")
# Placeholders / globs / ellipses are examples, not addressing keys.
_PATH_PLACEHOLDER_RE = re.compile(r"[…*<>]|某|示例|待建|不存在|省略")
AUDIT_FAMILY_PREFIX = "crwu-audit"


def _catalog_top_levels(paths: set[str]) -> dict[str, str]:
    """Top-level library containers actually captured by this catalog."""
    top: dict[str, str] = {}
    for path in paths:
        if path.endswith("/"):
            name = path.rstrip("/")
            if "/" not in name:
                top[name] = "folder"
        elif "/" not in path:
            top[path] = "file"
    return top


def _addressing_keys(text: str, top_levels: dict[str, str]) -> list[str]:
    """Backticked library paths that address a captured top-level container."""
    keys: set[str] = set()
    for raw in _BACKTICKED_RE.findall(text):
        token = raw.strip()
        if not token or _PATH_PLACEHOLDER_RE.search(token):
            continue
        head = token.split("/")[0]
        if head not in top_levels:
            continue
        if "/" not in token and top_levels[head] == "folder":
            token = token + "/"  # bare container name = the folder itself
        keys.add(_normalize_path(token, folder=token.endswith("/")))
    return sorted(keys)


def inspect_path_keys(
    repo_root: Path,
    paths: set[str],
    add_finding,
) -> dict[str, object]:
    """Every library path key written in the audit family must exist in the latest catalog.

    Guards against the two drift classes seen in practice: an address key that still carries
    the export suffix (`.md`), and keys copied from a different/older library.
    """
    top_levels = _catalog_top_levels(paths)
    if not top_levels:
        return {"checked": 0, "issues": []}
    skills_root = repo_root / "skills"
    if not skills_root.is_dir():
        return {"checked": 0, "issues": []}

    checked = 0
    issues: list[dict[str, object]] = []
    for skill_dir in sorted(skills_root.iterdir()):
        if not skill_dir.is_dir() or not skill_dir.name.startswith(AUDIT_FAMILY_PREFIX):
            continue
        for document in sorted(skill_dir.rglob("*.md")):
            text = document.read_text(encoding="utf-8")
            source = str(document.relative_to(repo_root))
            for key in _addressing_keys(text, top_levels):
                # Only judge containers this catalog actually captured.
                if key.rstrip("/").split("/")[0] not in top_levels:
                    continue
                checked += 1
                if key in paths:
                    continue
                stripped = key[:-3] if key.endswith(".md") else None
                if stripped and stripped in paths:
                    add_finding(
                        "KB_PATH_KEY_HAS_EXPORT_SUFFIX",
                        "error",
                        (
                            "library path key carries the .md export suffix; addressing keys must "
                            "match the library node name verbatim (.md is only the local export name)"
                        ),
                        path=key,
                        skill=skill_dir.name,
                        source=source,
                    )
                elif not key.endswith("/") and f"{key}/" in paths:
                    add_finding(
                        "KB_PATH_KEY_FOLDER_NEEDS_SLASH",
                        "error",
                        "library path key addresses a folder but does not end with '/'",
                        path=key,
                        skill=skill_dir.name,
                        source=source,
                    )
                elif key.endswith("/") and key.rstrip("/") in paths:
                    add_finding(
                        "KB_PATH_KEY_HAS_EXPORT_SUFFIX",
                        "error",
                        "library path key addresses a file but is written as a directory",
                        path=key,
                        skill=skill_dir.name,
                        source=source,
                    )
                else:
                    add_finding(
                        "KB_PATH_KEY_NOT_IN_CATALOG",
                        "error",
                        "library path key does not exist in the latest catalog",
                        path=key,
                        skill=skill_dir.name,
                        source=source,
                    )
                issues.append({"skill": skill_dir.name, "key": key, "source": source})
    return {"checked": checked, "issues": issues}


def _suggested_skill(axis: str, label: str) -> str | None:
    suffix = KNOWN_SKILL_SUFFIXES.get((axis, label))
    if not suffix:
        return None
    prefix = "crwu-audit-asset" if axis == "asset" else "crwu-audit-biz"
    return f"{prefix}-{suffix}"


def _catalog_age_hours(catalog: "Catalog") -> float | None:
    """Age of the catalog snapshot, or None when it carries no readable timestamp."""
    if not catalog.generated_at:
        return None
    raw = catalog.generated_at.strip()
    try:
        stamp = datetime.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=datetime.timezone.utc)
    now = datetime.datetime.now(datetime.timezone.utc)
    return (now - stamp).total_seconds() / 3600.0


def inspect_routing_layer(
    repo_root: Path,
    first_level: dict[str, list[tuple[str, str]]],
    rows_by_skill: dict[str, list["RegistryRow"]],
    add_finding,
) -> None:
    """Compare the knowledge base against the router, its references, the registry
    and the real skill directories: routing mechanism, reference registration,
    skill existence and whether a skill still needs to be created."""
    audit_root = repo_root / "skills" / ROUTER_SKILL
    router_skill = audit_root / "SKILL.md"
    references_dir = audit_root / "references"

    if not router_skill.is_file():
        add_finding(
            "ROUTER_FILE_MISSING",
            "error",
            "the crwu-audit router entry point does not exist",
            path=str(router_skill),
        )
        return

    missing_references = [
        name for name in ROUTER_REFERENCES if not (references_dir / name).is_file()
    ]
    for name in missing_references:
        add_finding(
            "ROUTER_REFERENCE_MISSING",
            "error",
            "a routing reference the router depends on does not exist",
            path=str(references_dir / name),
        )

    router_text = router_skill.read_text(encoding="utf-8")
    dispatch_path = references_dir / "08-union-dispatch-rules.md"
    dispatch_text = dispatch_path.read_text(encoding="utf-8") if dispatch_path.is_file() else ""

    # R2: every NN-*.md the router names must resolve to a router-owned reference.
    named = set()
    for text in (router_text, dispatch_text):
        named.update(_REFERENCE_TOKEN_RE.findall(text))
    for name in sorted(named):
        if name in LEAF_OWNED_REFERENCES:
            continue
        if not (references_dir / name).is_file():
            add_finding(
                "ROUTER_REFERENCE_UNRESOLVED",
                "error",
                "the router names a reference file that does not exist under crwu-audit/references/",
                path=str(references_dir / name),
            )

    # R3: an axis present in the knowledge base must be dispatched by the union rules.
    for axis, key in AXIS_DISPATCH_INPUT.items():
        if not first_level[axis]:
            continue
        if not dispatch_text:
            continue  # missing dispatch rules already reported above
        if key not in dispatch_text:
            add_finding(
                "ROUTER_AXIS_UNDISPATCHED",
                "error",
                f"the knowledge base has {axis} first-level folders but the union rules never load {key}",
                axis=axis,
            )

    # R4: every concrete skill name the routing layer names must exist or be registered.
    # Resolution covers any real crwu-audit* directory (leaves *and* non-leaf skills such
    # as the optimizer or datacheck), plus every name the registry claims.
    skills_root = repo_root / "skills"
    on_disk = (
        {
            child.name
            for child in skills_root.iterdir()
            if child.is_dir() and child.name.startswith("crwu-audit")
        }
        if skills_root.is_dir()
        else set()
    )
    known = on_disk | set(rows_by_skill) | {ROUTER_SKILL}
    for source, text in (
        ("skills/crwu-audit/SKILL.md", router_text),
        ("skills/crwu-audit/references/08-union-dispatch-rules.md", dispatch_text),
    ):
        for token in sorted(set(_SKILL_TOKEN_RE.findall(text))):
            if token in known:
                continue
            add_finding(
                "ROUTER_SKILL_REFERENCE_UNRESOLVED",
                "error",
                "the routing layer names a skill that is neither a real directory nor a registry row",
                skill=token,
                path=source,
            )


def inspect_repository(
    repo_root: Path,
    catalog: Catalog,
    max_age_hours: float | None = None,
) -> dict[str, object]:
    paths = set(catalog.paths)
    findings: list[dict[str, object]] = []
    proposals: list[dict[str, object]] = []

    def add_finding(
        code: str,
        severity: str,
        message: str,
        *,
        axis: str | None = None,
        label: str | None = None,
        skill: str | None = None,
        path: str | None = None,
        source: str | None = None,
    ) -> None:
        findings.append(
            {
                "code": code,
                "severity": severity,
                "axis": axis,
                "label": label,
                "skill": skill,
                "path": path,
                "source": source,
                "message": message,
            }
        )

    def add_proposal(
        action: str,
        axis: str,
        label: str,
        *,
        skill_name: str | None,
        kb_root: str,
        name_review_required: bool | None = None,
    ) -> None:
        if name_review_required is None:
            name_review_required = action == "create_skill"
        proposals.append(
            {
                "action": action,
                "axis": axis,
                "label": label,
                "skill_name": skill_name,
                "kb_root": kb_root,
                "name_review_required": name_review_required,
            }
        )

    first_level: dict[str, list[tuple[str, str]]] = {"asset": [], "business": []}
    for axis, root in AXIS_ROOTS.items():
        for child in _immediate_folder_children(paths, root):
            if _is_ignored_label(child):
                continue
            first_level[axis].append((_label(child), f"{root}{child}/"))

    registry_path = (
        repo_root
        / "skills"
        / "crwu-audit"
        / "references"
        / "07-skill-registry.md"
    )
    registry_rows = _read_registry(registry_path)
    if not registry_path.is_file():
        add_finding(
            "REGISTRY_FILE_MISSING",
            "error",
            "crwu-audit skill registry does not exist",
            path=str(registry_path),
        )

    rows_by_key: dict[tuple[str, str], list[RegistryRow]] = {}
    rows_by_skill: dict[str, list[RegistryRow]] = {}
    for row in registry_rows:
        rows_by_key.setdefault((row.axis, row.label), []).append(row)
        if row.skill and row.skill != "—":
            rows_by_skill.setdefault(row.skill, []).append(row)

    # Every asset/business registry row is validated, including labels the supplied
    # catalog does not cover: a registry claim must hold on its own.
    audit_rows = [row for row in registry_rows if row.axis in AXIS_ROOTS]
    public_rows = [row for row in registry_rows if row.axis == PUBLIC_AXIS]
    for (axis, label), rows in sorted(rows_by_key.items()):
        if axis not in AXIS_ROOTS or len(rows) < 2:
            continue
        add_finding(
            "REGISTRY_LABEL_DUPLICATE",
            "error",
            f"first-level label is registered {len(rows)} times; keep exactly one registry row",
            axis=axis,
            label=label,
        )

    legacy_registry_skills = {
        row.skill
        for row in registry_rows
        if row.skill.startswith(LEGACY_BUSINESS_PREFIX)
    }
    for skill_name in sorted(legacy_registry_skills):
        add_finding(
            "LEGACY_BUSINESS_PREFIX",
            "error",
            "business registry entry must migrate to the crwu-audit-biz-* prefix",
            axis="business",
            skill=skill_name,
            path=str(registry_path),
        )

    skills_root = repo_root / "skills"
    skill_dirs: dict[str, Path] = {}
    if skills_root.is_dir():
        for child in skills_root.iterdir():
            if not child.is_dir():
                continue
            if child.name.startswith(
                (AXIS_SKILL_PREFIX["asset"], AXIS_SKILL_PREFIX["business"], LEGACY_BUSINESS_PREFIX)
            ):
                skill_dirs[child.name] = child

    assembly_roots_by_skill: dict[str, set[str]] = {}
    frontmatter_names: dict[str, str] = {}
    for skill_name, skill_dir in sorted(skill_dirs.items()):
        if skill_name.startswith(LEGACY_BUSINESS_PREFIX) and skill_name not in legacy_registry_skills:
            add_finding(
                "LEGACY_BUSINESS_PREFIX",
                "error",
                "business skill must use the crwu-audit-biz-* prefix",
                axis="business",
                skill=skill_name,
                path=str(skill_dir),
            )
        frontmatter_name = _frontmatter_name(skill_dir / "SKILL.md")
        frontmatter_names[skill_name] = frontmatter_name or ""
        if frontmatter_name != skill_name:
            add_finding(
                "SKILL_NAME_MISMATCH",
                "error",
                "skill directory and frontmatter name do not match",
                skill=skill_name,
                path=str(skill_dir / "SKILL.md"),
            )
        for reference in REQUIRED_REFERENCES:
            reference_path = skill_dir / "references" / reference
            if not reference_path.is_file():
                add_finding(
                    "SKILL_REFERENCE_MISSING",
                    "error",
                    f"required reference is missing: {reference}",
                    skill=skill_name,
                    path=str(reference_path),
                )
        assembly_path = skill_dir / "references" / "01-kb-assembly.md"
        if not assembly_path.is_file():
            continue
        assembly_text = assembly_path.read_text(encoding="utf-8")
        kb_paths = _extract_kb_paths(assembly_text)
        roots = {_first_level_root(path) for path in kb_paths}
        assembly_roots_by_skill[skill_name] = {root for root in roots if root}
        has_file_mapping = (
            re.search(r"(?i)\bfile\b", assembly_text) is not None
            or any(not path.endswith("/") for path in kb_paths)
        )
        if has_file_mapping:
            add_finding(
                "ASSEMBLY_FILE_MAPPING",
                "error",
                "assembly must use one recursive first-level directory root instead of file entries",
                skill=skill_name,
                path=str(assembly_path),
            )

    known_roots_to_skills: dict[str, list[str]] = {}
    for skill, roots in assembly_roots_by_skill.items():
        for root in roots:
            known_roots_to_skills.setdefault(root, []).append(skill)

    classification_files = {
        "asset": repo_root / "skills/crwu-audit/references/03-asset-classification.md",
        "business": repo_root / "skills/crwu-audit/references/04-business-classification.md",
    }

    catalog_labels: dict[str, dict[str, str]] = {"asset": {}, "business": {}}
    for axis, items in first_level.items():
        for label, kb_root in items:
            catalog_labels[axis].setdefault(label, kb_root)
    # A partial catalog must not be read as "this root was deleted": only judge root
    # existence for an axis whose own first-level container was actually captured.
    axis_captured = {axis: root in paths for axis, root in AXIS_ROOTS.items()}
    dir_by_frontmatter = {
        frontmatter: directory
        for directory, frontmatter in frontmatter_names.items()
        if frontmatter
    }

    # A duplicated registry row is already reported once by REGISTRY_LABEL_DUPLICATE,
    # so each distinct claim is validated exactly once here.
    unique_rows: dict[tuple[str, str, str, str], RegistryRow] = {}
    for row in audit_rows:
        unique_rows.setdefault((row.axis, row.label, row.skill, row.status), row)
    for row in [unique_rows[key] for key in sorted(unique_rows)]:
        skill_name = row.skill
        if not skill_name or skill_name == "—":
            continue
        # Legacy business names are already reported as LEGACY_BUSINESS_PREFIX.
        if (
            not skill_name.startswith(LEGACY_BUSINESS_PREFIX)
            and not skill_name.startswith(AXIS_SKILL_PREFIX[row.axis])
        ):
            add_finding(
                "AXIS_PREFIX_MISMATCH",
                "error",
                f"{row.axis} row must map a {AXIS_SKILL_PREFIX[row.axis]}* skill",
                axis=row.axis,
                label=row.label,
                skill=skill_name,
            )

        expected_root = catalog_labels[row.axis].get(row.label)
        if row.status != "available":
            continue

        if expected_root is None and axis_captured[row.axis]:
            add_finding(
                "REGISTRY_LABEL_NOT_IN_CATALOG",
                "warning",
                "available registry label has no first-level folder in the latest catalog",
                axis=row.axis,
                label=row.label,
                skill=skill_name,
            )

        skill_dir = skill_dirs.get(skill_name)
        if skill_dir is None:
            add_finding(
                "AVAILABLE_SKILL_DIRECTORY_MISSING",
                "error",
                "available registry skill directory does not exist",
                axis=row.axis,
                label=row.label,
                skill=skill_name,
            )
            drifted_dir = dir_by_frontmatter.get(skill_name)
            if drifted_dir is not None:
                add_finding(
                    "SKILL_NAME_MISMATCH",
                    "error",
                    "registry name matches a directory frontmatter name, but the directory itself is named differently",
                    axis=row.axis,
                    label=row.label,
                    skill=skill_name,
                    path=str(skills_root / drifted_dir),
                )
            add_proposal(
                "repair_skill",
                row.axis,
                row.label,
                skill_name=skill_name,
                kb_root=expected_root or f"{AXIS_ROOTS[row.axis]}<{row.label}>/",
            )
            continue

        assembly = skill_dir / "references" / "01-kb-assembly.md"
        assembly_text = assembly.read_text(encoding="utf-8") if assembly.is_file() else ""
        extracted = _extract_kb_paths(assembly_text)
        directory_contract = (
            re.search(r"(?i)\bdirectory\b", assembly_text) is not None
            and re.search(r"(?i)\btrue\b", assembly_text) is not None
        )
        if expected_root is not None:
            exact_root_present = f"`{expected_root}`" in assembly_text or expected_root in extracted
        else:
            # The catalog does not cover this label, so its root cannot be confirmed;
            # require only that a single well-formed recursive root is declared.
            exact_root_present = len(_declared_first_level_roots(assembly_text)) == 1
        if not exact_root_present or not directory_contract:
            add_finding(
                "ASSEMBLY_FIRST_LEVEL_ROOT_MISSING",
                "error",
                "available skill lacks its exact recursive first-level directory root",
                axis=row.axis,
                label=row.label,
                skill=skill_name,
                path=expected_root or str(assembly),
            )
            if expected_root is not None:
                add_proposal(
                    "remap_skill",
                    row.axis,
                    row.label,
                    skill_name=skill_name,
                    kb_root=expected_root,
                )

        if axis_captured[row.axis]:
            for declared_root in sorted(_declared_first_level_roots(assembly_text)):
                if not declared_root.startswith(AXIS_ROOTS[row.axis]):
                    add_finding(
                        "AXIS_ROOT_MISMATCH",
                        "error",
                        f"{row.axis} skill declares a root owned by another axis",
                        axis=row.axis,
                        label=row.label,
                        skill=skill_name,
                        path=declared_root,
                    )
                elif declared_root not in paths:
                    add_finding(
                        "MAPPING_ROOT_NOT_IN_CATALOG",
                        "error",
                        "declared first-level root no longer exists in the latest catalog",
                        axis=row.axis,
                        label=row.label,
                        skill=skill_name,
                        path=declared_root,
                    )

        if row.axis == "business" and expected_root is not None:
            common_review_doc = _named_doc(paths, expected_root, BUSINESS_COMMON_REVIEW_DOC)
            if common_review_doc is not None:
                focus = skill_dir / "references" / "02-review-focus.md"
                focus_text = focus.read_text(encoding="utf-8") if focus.is_file() else ""
                if not _references_common_review(
                    assembly_text + focus_text, expected_root, common_review_doc
                ):
                    add_finding(
                        "BUSINESS_COMMON_REVIEW_NOT_REFERENCED",
                        "warning",
                        (
                            f"the first-level business folder ships {common_review_doc}; "
                            "the business skill must address it by its library path key "
                            f"({expected_root}{common_review_doc}) as the shared review layer "
                            "— merely naming the document (e.g. claiming it is absent) does not count"
                        ),
                        axis=row.axis,
                        label=row.label,
                        skill=skill_name,
                        path=expected_root,
                    )

    for axis, items in first_level.items():
        classification_text = (
            classification_files[axis].read_text(encoding="utf-8")
            if classification_files[axis].is_file()
            else None
        )
        for label, kb_root in items:
            row = rows_by_key.get((axis, label), [None])[0]
            mapped_skills = sorted(known_roots_to_skills.get(kb_root, []))
            if row is None:
                action = "register_skill" if mapped_skills else "create_skill"
                skill_name = mapped_skills[0] if mapped_skills else _suggested_skill(axis, label)
                add_finding(
                    "FIRST_LEVEL_SKILL_MISSING",
                    "error",
                    "knowledge-base first-level folder has no registry skill",
                    axis=axis,
                    label=label,
                    skill=skill_name,
                    path=kb_root,
                )
                add_proposal(action, axis, label, skill_name=skill_name, kb_root=kb_root)
            elif row.status == "pending":
                add_finding(
                    "FIRST_LEVEL_SKILL_PENDING",
                    "warning",
                    "knowledge-base first-level folder is registered but its skill is pending",
                    axis=axis,
                    label=label,
                    skill=row.skill,
                    path=kb_root,
                )
                proposal_skill = (
                    _suggested_skill(axis, label)
                    if row.skill.startswith(LEGACY_BUSINESS_PREFIX)
                    else row.skill
                )
                add_proposal("create_skill", axis, label, skill_name=proposal_skill, kb_root=kb_root)
            if classification_text is not None and label not in classification_text:
                add_finding(
                    "CLASSIFICATION_LABEL_MISSING",
                    "warning",
                    "first-level knowledge label is absent from its classification reference",
                    axis=axis,
                    label=label,
                    path=str(classification_files[axis]),
                )

    # Public-axis rows carry report-shape-independent capabilities (report disclosure,
    # procedure/quality control, tabular reconciliation). They sit outside the asset/business
    # first-level-root model, so they are validated here instead of in the loop above:
    # the declared skill directory must exist, match its frontmatter name, and declare a KB
    # assembly table (either the standard `01-kb-assembly.md` or the cross-cutting
    # `00-KB装配表.md` used by `crwu-audit-datacheck`). Their assembly path keys are already
    # covered globally by inspect_path_keys(), which walks every crwu-audit* directory.
    for row in sorted(
        {(r.label, r.skill, r.status): r for r in public_rows}.values(),
        key=lambda r: (r.label, r.skill),
    ):
        if not row.skill or row.skill == "—" or row.status != "available":
            continue
        public_dir = skills_root / row.skill
        if not public_dir.is_dir():
            add_finding(
                "AVAILABLE_SKILL_DIRECTORY_MISSING",
                "error",
                "available public-axis registry skill directory does not exist",
                axis=row.axis,
                label=row.label,
                skill=row.skill,
            )
            add_proposal(
                "repair_skill",
                row.axis,
                row.label,
                skill_name=row.skill,
                kb_root="",
            )
            continue
        public_frontmatter = _frontmatter_name(public_dir / "SKILL.md")
        if public_frontmatter != row.skill:
            add_finding(
                "SKILL_NAME_MISMATCH",
                "error",
                "public-axis skill directory and frontmatter name do not match",
                axis=row.axis,
                label=row.label,
                skill=row.skill,
                path=str(public_dir / "SKILL.md"),
            )
        public_references = public_dir / "references"
        declared_assembly = [
            name
            for name in PUBLIC_ASSEMBLY_REFERENCES
            if (public_references / name).is_file()
        ]
        if not declared_assembly:
            add_finding(
                "SKILL_REFERENCE_MISSING",
                "error",
                "public-axis skill declares no KB assembly table: "
                + " or ".join(PUBLIC_ASSEMBLY_REFERENCES),
                axis=row.axis,
                label=row.label,
                skill=row.skill,
                path=str(public_references),
            )

    # A crwu-audit skill that is neither an axis leaf nor a known non-leaf skill is a
    # leftover combined/legacy skill; register it or migrate it onto a real axis prefix.
    registered_names = set(rows_by_skill)
    if skills_root.is_dir():
        for child in sorted(skills_root.iterdir()):
            name = child.name
            if not child.is_dir() or not name.startswith("crwu-audit"):
                continue
            if name in NON_LEAF_SKILLS or name in registered_names:
                continue
            if name.startswith((AXIS_SKILL_PREFIX["asset"], AXIS_SKILL_PREFIX["business"], LEGACY_BUSINESS_PREFIX)):
                continue
            add_finding(
                "LEGACY_COMBINED_SKILL",
                "error",
                "crwu-audit skill is neither a registered axis skill nor a known non-leaf skill; register it or migrate it to crwu-audit-asset-* / crwu-audit-biz-*",
                skill=name,
                path=str(child),
            )

    for skill_name, skill_dir in sorted(skill_dirs.items()):
        if skill_name not in rows_by_skill:
            add_finding(
                "ORPHAN_SKILL",
                "warning",
                "asset/business skill is not present in the registry",
                skill=skill_name,
                path=str(skill_dir),
            )

    inspect_routing_layer(repo_root, first_level, rows_by_skill, add_finding)

    path_key_issues = inspect_path_keys(repo_root, paths, add_finding)

    if max_age_hours is not None:
        age = _catalog_age_hours(catalog)
        if age is None:
            add_finding(
                "CATALOG_NOT_LIVE",
                "error",
                (
                    "catalog carries no readable capture time; refresh the directory through "
                    "crwu-dws before drawing routing conclusions"
                ),
            )
        elif age > max_age_hours:
            add_finding(
                "CATALOG_STALE",
                "error",
                (
                    f"catalog capture time is {age:.1f}h old (limit {max_age_hours}h); "
                    "refresh the directory through crwu-dws before drawing routing conclusions"
                ),
            )

    for label, asset_root in first_level["asset"]:
        common_root = _find_named_folder(paths, asset_root, "共性参考")
        if common_root is None:
            add_finding(
                "ASSET_COMMON_REFERENCE_MISSING",
                "error",
                "asset first-level folder has no common-reference directory",
                axis="asset",
                label=label,
                path=asset_root,
            )
        subobjects_root = _find_named_folder(paths, asset_root, "细分对象")
        if subobjects_root:
            for subobject in _immediate_folder_children(paths, subobjects_root):
                if _is_ignored_label(subobject):
                    continue
                subobject_root = f"{subobjects_root}{subobject}/"
                if not _has_named_doc(paths, subobject_root, "评估审核条目"):
                    add_finding(
                        "ASSET_SUBOBJECT_REVIEW_MISSING",
                        "warning",
                        "asset subobject has no 评估审核条目; keep it under the parent skill and record a content gap",
                        axis="asset",
                        label=_label(subobject),
                        path=subobject_root,
                    )

    for label, business_root in first_level["business"]:
        for subroute in _immediate_folder_children(paths, business_root):
            if _is_ignored_label(subroute):
                continue
            subroute_root = f"{business_root}{subroute}/"
            if not _has_named_doc(paths, subroute_root, "业务通用审核要点"):
                add_finding(
                    "BUSINESS_SUBROUTE_REVIEW_MISSING",
                    "warning",
                    "business subroute has no 01-业务通用审核要点; keep it under the parent skill and record a content gap",
                    axis="business",
                    label=_label(subroute),
                    path=subroute_root,
                )

    findings.sort(
        key=lambda item: (
            str(item["severity"]),
            str(item["axis"] or ""),
            str(item["label"] or ""),
            str(item["skill"] or ""),
            str(item["code"]),
            str(item["path"] or ""),
        )
    )
    proposals.sort(
        key=lambda item: (
            str(item["axis"]),
            str(item["label"]),
            str(item["action"]),
            str(item["skill_name"] or ""),
        )
    )
    summary = {
        "errors": sum(item["severity"] == "error" for item in findings),
        "warnings": sum(item["severity"] == "warning" for item in findings),
        "proposals": len(proposals),
        "first_level_assets": len(first_level["asset"]),
        "first_level_businesses": len(first_level["business"]),
    }
    calibration = _build_calibration(
        first_level, rows_by_key, skill_dirs, paths, findings, catalog
    )
    calibration["path_key_issues"] = path_key_issues
    return {
        "schema": REPORT_SCHEMA,
        "catalog": {
            "source_schema": catalog.source_schema,
            "generated_at": catalog.generated_at,
            "complete": catalog.complete,
            "paths": list(catalog.paths),
        },
        "summary": summary,
        "findings": findings,
        "proposals": proposals,
        "calibration": calibration,
    }


def _build_calibration(
    first_level: dict[str, list[tuple[str, str]]],
    rows_by_key: dict[tuple[str, str], list["RegistryRow"]],
    skill_dirs: dict[str, Path],
    paths: set[str],
    findings: list[dict[str, object]],
    catalog: "Catalog",
) -> dict[str, object]:
    """Human-readable 知识库 ↔ Skill 映射快照, derived only from this run's inputs."""
    rows: list[dict[str, object]] = []
    for axis in ("asset", "business"):
        for label, kb_root in first_level[axis]:
            registry = rows_by_key.get((axis, label), [])
            row = registry[0] if registry else None
            skill = row.skill if row is not None and row.skill not in ("", "—") else None
            status = row.status if row is not None else "unregistered"

            declared_root: str | None = None
            if skill is not None and skill in skill_dirs:
                assembly = skill_dirs[skill] / "references" / "01-kb-assembly.md"
                if assembly.is_file():
                    roots = sorted(
                        _declared_first_level_roots(assembly.read_text(encoding="utf-8"))
                    )
                    declared_root = roots[0] if len(roots) == 1 else (
                        " / ".join(roots) if roots else None
                    )

            detail: dict[str, object] = {}
            if axis == "asset":
                detail["common_reference"] = (
                    _find_named_folder(paths, kb_root, "共性参考") is not None
                )
                subobject_root = _find_named_folder(paths, kb_root, "细分对象")
                subobjects = (
                    [
                        child
                        for child in _immediate_folder_children(paths, subobject_root)
                        if not _is_ignored_label(child)
                    ]
                    if subobject_root
                    else []
                )
                with_review = [
                    child
                    for child in subobjects
                    if _has_named_doc(paths, f"{subobject_root}{child}/", "评估审核条目")
                ]
                detail["subobjects"] = len(subobjects)
                detail["subobjects_with_reference"] = len(with_review)
            else:
                detail["common_review"] = _has_named_doc(
                    paths, kb_root, BUSINESS_COMMON_REVIEW_DOC
                )
                subroutes = [
                    child
                    for child in _immediate_folder_children(paths, kb_root)
                    if not _is_ignored_label(child)
                ]
                with_reference = [
                    child
                    for child in subroutes
                    if _has_named_doc(paths, f"{kb_root}{child}/", "业务通用审核要点")
                ]
                detail["subroutes"] = len(subroutes)
                detail["subroutes_with_reference"] = len(with_reference)
                detail["subroutes_without_reference"] = [
                    _label(child) for child in subroutes if child not in with_reference
                ]

            row_findings = sorted(
                {
                    str(item["code"])
                    for item in findings
                    if item.get("axis") == axis and item.get("label") == label
                }
            )
            rows.append(
                {
                    "axis": axis,
                    "label": label,
                    "kb_root": kb_root,
                    "skill": skill,
                    "status": status,
                    "declared_root": declared_root,
                    "detail": detail,
                    "finding_codes": row_findings,
                }
            )

    unregistered_skills = sorted(
        {
            str(item["skill"])
            for item in findings
            if item["code"] in {"ORPHAN_SKILL", "LEGACY_COMBINED_SKILL"} and item.get("skill")
        }
    )
    return {
        "catalog": {
            "source_schema": catalog.source_schema,
            "fetched_at": catalog.generated_at,
            "complete": catalog.complete,
            "node_paths": len(catalog.paths),
        },
        "rows": rows,
        "unregistered_skills": unregistered_skills,
    }


CALIBRATION_NOTES_BEGIN = "<!-- CALIBRATION-NOTES:BEGIN -->"
CALIBRATION_NOTES_END = "<!-- CALIBRATION-NOTES:END -->"
CALIBRATION_HISTORY_BEGIN = "<!-- CALIBRATION-HISTORY:BEGIN -->"
CALIBRATION_HISTORY_END = "<!-- CALIBRATION-HISTORY:END -->"


def _preserved_block(text: str | None, begin: str, end: str) -> str:
    """Keep a hand-maintained block (notes) or an append-only log (history) across runs."""
    if not text:
        return ""
    start = text.find(begin)
    stop = text.find(end)
    if start < 0 or stop < 0 or stop < start:
        return ""
    return text[start + len(begin) : stop].strip("\n")


def render_calibration(report: dict[str, object], previous: str | None = None) -> str:
    calibration = report.get("calibration")
    assert isinstance(calibration, dict)
    catalog = calibration["catalog"]
    assert isinstance(catalog, dict)
    summary = report["summary"]
    assert isinstance(summary, dict)
    rows = calibration["rows"]
    assert isinstance(rows, list)

    stamp = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    complete = catalog.get("complete")
    complete_text = {True: "complete=true", False: "**complete=false（不可作路径事实）**"}.get(
        complete, "complete 未知"
    )
    if catalog.get("fetched_at") is None:
        complete_text += " · **无抓取时间（未能证明是最新）**"

    lines = [
        "# 知识库 ↔ Skill 映射校准表",
        "",
        "> 本表由 `crwu-audit-skill-maintainer` 在每次 `audit` 后重新生成，供人工一眼查看映射现状。",
        "> **事实源**：知识库最新目录（经 `crwu-dws` 实时拉取）+ `crwu-audit/references/07-skill-registry.md` + `skills/` 真实目录。",
        "> 本表是**只读派生视图**：不要手工改状态列；不一致时重新校准，不要手改。",
        "",
        "| 校准项 | 值 |",
        "| --- | --- |",
        f"| 校准时间 | {stamp} |",
        f"| 知识库目录抓取时间 | {catalog.get('fetched_at') or '（无）'} |",
        f"| 目录输入形态 | `{catalog.get('source_schema')}` |",
        f"| 抓取完整性 | {complete_text} |",
        f"| 目录节点数 | {catalog.get('node_paths')} |",
        f"| 一级资产 / 一级业务 | {summary['first_level_assets']} / {summary['first_level_businesses']} |",
        f"| 本次 error / warning / 建议 | {summary['errors']} / {summary['warnings']} / {summary['proposals']} |",
        "",
    ]

    for axis, title in (("asset", "资产轴"), ("business", "业务轴")):
        axis_rows = [row for row in rows if row["axis"] == axis]
        lines += [f"## {title}（{len(axis_rows)}）", ""]
        if not axis_rows:
            lines += ["（知识库本次无该轴一级目录）", ""]
            continue
        if axis == "asset":
            lines += [
                "| 知识库一级目录 | 一级标签 | Skill | registry | 声明的一级根 | 共性参考 | 细分对象(有审核条目) | 本次问题 |",
                "| --- | --- | --- | --- | --- | --- | --- | --- |",
            ]
        else:
            lines += [
                "| 知识库一级目录 | 一级标签 | Skill | registry | 声明的一级根 | 共同审核点 | 子业务(有要点) | 本次问题 |",
                "| --- | --- | --- | --- | --- | --- | --- | --- |",
            ]
        for row in axis_rows:
            detail = row["detail"]
            assert isinstance(detail, dict)
            if axis == "asset":
                extra_a = "有" if detail.get("common_reference") else "**无（gap）**"
                total = int(detail.get("subobjects") or 0)
                have = int(detail.get("subobjects_with_reference") or 0)
                extra_b = f"{total}（{have}）" if total else "—"
            else:
                extra_a = "有" if detail.get("common_review") else "无（不记缺口）"
                total = int(detail.get("subroutes") or 0)
                have = int(detail.get("subroutes_with_reference") or 0)
                missing = detail.get("subroutes_without_reference") or []
                extra_b = f"{total}（{have}）" if total else "—"
                if missing:
                    extra_b += " 缺：" + "、".join(str(m) for m in missing)
            codes = row["finding_codes"]
            codes_text = "、".join(f"`{code}`" for code in codes) if codes else "—"
            skill_text = f"`{row['skill']}`" if row["skill"] else "**（无）**"
            root_text = f"`{row['declared_root']}`" if row["declared_root"] else "—"
            lines.append(
                f"| `{row['kb_root']}` | {row['label']} | {skill_text} | {row['status']} | "
                f"{root_text} | {extra_a} | {extra_b} | {codes_text} |"
            )
        lines.append("")

    path_keys = calibration.get("path_key_issues") or {}
    assert isinstance(path_keys, dict)
    key_issues = path_keys.get("issues") or []
    lines += [
        "## 库内路径键健康（公共轴也查）",
        "",
        (
            f"检查 {path_keys.get('checked', 0)} 个寻址键（扫描 audit 族技能目录内全部 .md 的反引号库内路径）："
            + ("**全部命中本次目录**" if not key_issues else f"**{len(key_issues)} 个未命中**")
        ),
        "",
    ]
    if key_issues:
        lines += [
            "| Skill | 路径键 |",
            "| --- | --- |",
            # Deliberately NOT backticked: this calibration table is itself inside the scanned
            # audit-family skill tree, so backticking a missing key here would make the next
            # run report the diagnostic table as fresh drift of this very file (non-idempotent).
            *[f"| `{i['skill']}` | {i['key']} |" for i in key_issues],
            "",
            "> 未命中键在此**不加反引号**：本文件自身也在扫描范围内，写成寻址键会把这张诊断表当成本文件的新漂移。",
            "",
        ]

    unregistered = calibration["unregistered_skills"]
    assert isinstance(unregistered, list)
    lines += ["## 未登记 / 待处理 Skill", ""]
    if unregistered:
        lines += ["| Skill 目录 | 处置 |", "| --- | --- |"]
        lines += [
            f"| `{name}` | {'遗留组合 Skill，迁移到 `crwu-audit-asset-*` / `crwu-audit-biz-*`' if not name.startswith(('crwu-audit-asset-', 'crwu-audit-biz-')) else '未登记，补 registry 行或删除'} |"
            for name in unregistered
        ]
    else:
        lines.append("（无）")
    lines.append("")

    notes = _preserved_block(previous, CALIBRATION_NOTES_BEGIN, CALIBRATION_NOTES_END)
    lines += [
        "## 内容级校准备注（人工维护，工具不覆盖）",
        "",
        "> 目录级事实由上表自动同步；**内容级状态**（必检项是否「待补」、文档是否为空、是否占位）需在下载正文核对后写在这里。",
        "> 空表示本次未下载正文核对，不代表内容合格。",
        "",
        CALIBRATION_NOTES_BEGIN,
        notes if notes else "",
        CALIBRATION_NOTES_END,
        "",
    ]

    history_prev = _preserved_block(previous, CALIBRATION_HISTORY_BEGIN, CALIBRATION_HISTORY_END)
    entry = (
        f"| {stamp} | {catalog.get('fetched_at') or '—'} | {catalog.get('node_paths')} | "
        f"{summary['errors']} | {summary['warnings']} | {summary['proposals']} |"
    )
    history_lines = [line for line in history_prev.splitlines() if line.strip()]
    if not history_lines:
        history_lines = [
            "| 校准时间 | 目录抓取时间 | 节点数 | error | warning | 建议 |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    if entry not in history_lines:
        history_lines.append(entry)
    # Header rows stay on top; data rows are stored oldest-first but shown newest-first.
    header_rows = history_lines[:2]
    data_rows = history_lines[2:]
    lines += [
        "## 校准历史（新→旧，工具追加）",
        "",
        CALIBRATION_HISTORY_BEGIN,
        "\n".join(header_rows + list(reversed(data_rows))),
        CALIBRATION_HISTORY_END,
        "",
    ]
    return "\n".join(lines)


def render_text(report: dict[str, object]) -> str:
    summary = report["summary"]
    assert isinstance(summary, dict)
    lines = [
        "crwu-audit Skill 映射盘点",
        (
            f"一级资产 {summary['first_level_assets']} / 一级业务 "
            f"{summary['first_level_businesses']} / 错误 {summary['errors']} / "
            f"警告 {summary['warnings']} / 建议 {summary['proposals']}"
        ),
        "",
        "发现：",
    ]
    findings = report["findings"]
    assert isinstance(findings, list)
    if not findings:
        lines.append("- 无")
    for item in findings:
        assert isinstance(item, dict)
        target = item.get("label") or item.get("skill") or item.get("path") or "全局"
        lines.append(f"- [{item['severity']}] {item['code']} · {target}：{item['message']}")
    lines.extend(["", "建议："])
    proposals = report["proposals"]
    assert isinstance(proposals, list)
    if not proposals:
        lines.append("- 无")
    for item in proposals:
        assert isinstance(item, dict)
        skill = item.get("skill_name") or "名称待人工确认"
        lines.append(
            f"- {item['action']} · {item['axis']}:{item['label']} · {skill} · {item['kb_root']}"
        )
    return "\n".join(lines) + "\n"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect crwu-audit asset/business skill mappings without modifying files."
    )
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="exit 1 when error-severity findings are present",
    )
    parser.add_argument(
        "--emit-map",
        type=Path,
        default=None,
        metavar="PATH",
        help=(
            "write/refresh the human-readable knowledge-base <-> skill calibration table at PATH; "
            "the hand-maintained notes and the append-only history block are preserved"
        ),
    )
    parser.add_argument(
        "--max-age-hours",
        type=float,
        default=None,
        metavar="H",
        help=(
            "require the catalog to come from a fresh crwu-dws refresh no older than H hours; "
            "a missing or older capture time is reported as CATALOG_NOT_LIVE / CATALOG_STALE"
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        catalog = load_catalog(args.catalog)
        report = inspect_repository(
            args.repo_root.resolve(), catalog, max_age_hours=args.max_age_hours
        )
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.emit_map is not None:
        try:
            previous = (
                args.emit_map.read_text(encoding="utf-8") if args.emit_map.is_file() else None
            )
            args.emit_map.parent.mkdir(parents=True, exist_ok=True)
            args.emit_map.write_text(render_calibration(report, previous), encoding="utf-8")
        except OSError as exc:
            print(f"error: cannot write calibration map: {exc}", file=sys.stderr)
            return 2
        # `--format json` must keep stdout parseable as the single report object, so the notice
        # goes to stderr in that mode (callers pipe stdout straight into a JSON parser).
        print(
            f"校准表已更新：{args.emit_map}",
            file=sys.stderr if args.format == "json" else sys.stdout,
        )
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(render_text(report), end="")
    summary = report["summary"]
    assert isinstance(summary, dict)
    return 1 if args.strict and int(summary["errors"]) > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
