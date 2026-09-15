#!/usr/bin/env python3
"""外部数据源只读探测：同花顺 iFinD 的两条取数路径（crwu-audit-external-data）。

背景：本技能的唯一外部数据源是同花顺 iFinD，但不同宿主的取数路径不同——

- **WorkBuddy**：宿主把同花顺 iFinD 做成内置连接器（MCP，连接器 id `ifind-mcp`，服务端授权）；
  会话可能直接暴露对应 MCP 工具；未暴露时读宿主连接器声明。
- **DeepSeek Harness**：没有 WorkBuddy 连接器，同花顺 iFinD 以**技能** `ifind-finance-data` 提供
  （该技能自带 `call.py` / `call-node.js`，直连同花顺 MCP HTTP 服务，凭据在技能自身的
  `mcp_config.json`）；用该技能取数，不读宿主连接器目录。

本脚本在会话未直接暴露取数入口时，读这两类**声明**，回答"同花顺 iFinD 是否存在、是否启用、
有没有可核实的授权证据"。万得不在本技能范围内，不探测、不作为数据源。

只读纪律：
- 只读连接器声明的**键名与启用状态**、技能目录结构与文件是否存在；
- 不读取、不输出任何令牌 / Authorization 值，也**不解析 `mcp_config.json` 的内容**；
  URL 只输出主机名（去掉路径与查询串）；
- 不发起任何网络请求。

判定口径（重要）：
- **只有宿主声明（`mcp.json` / `connectors/*/mcp.json`）才算"已声明"**；连接器市场目录
  （`connectors-marketplace/.../connectors.json`）列出全部可安装连接器，**不作为已声明依据**。
- Harness 技能路径只按"技能目录存在 + 调用脚本 + 凭据文件存在"给预检结论，**不断言凭据有效**；
  真正的判据是**运行时调用是否返回授权错误**。
- 若运行时调用失败，按知识库表 D 降级并在交付件中声明（见 references/01-connector-access.md §4）。

宿主侧外部工具说明：WorkBuddy 连接器与 `ifind-finance-data` 技能均由宿主 / 第三方提供，
本仓库不提供、不随本技能安装。

用法：
  python3 scripts/connector_probe.py [--root <dir>] [--skills-root <dir>]... [--format json|text]

退出码：0 = 至少一条取数路径预检可用；2 = 未发现可用取数路径（仍输出 JSON 说明）。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

SCHEMA = "crwu.external-data.connector-probe.v2"
DEFAULT_ROOT_ENV = "CRWU_CONNECTOR_ROOT"
DEFAULT_ROOT = "~/.workbuddy"
SKILLS_ROOT_ENV = "CRWU_SKILLS_ROOT"
HARNESS_SKILL_ID = "ifind-finance-data"
# Harness 技能安装位置：显式环境变量 → 本技能所在 skills 根的同级 → 常见 skills 根。
DEFAULT_SKILLS_ROOTS = ("~/.agents/skills", "~/.dsh/skills", "~/.codebuddy/skills", "~/.claude/skills")

IFIND_LABEL = "同花顺 iFinD"
# 只在宿主已声明的连接器里匹配；id 命中权重高于名称。
IFIND_ID_KEYS = ("ifind",)
IFIND_NAME_KEYS = ("ifind", "同花顺")
TOKEN_AUTH_MODES = ("token", "oauth", "apikey")

# 状态优劣排序：available 最优，用于在两条路径间取"更可用"的一条。
_STATE_RANK = {
    "available": 5,
    "likely_unauthenticated": 4,
    "declared_disabled": 3,
    "incomplete": 2,
    "not_declared": 1,
    "not_found": 0,
}

_SECRET_KEY = re.compile(r"(?i)(authorization|token|secret|password|cookie|api[_-]?key)")
# 宿主 mcp.json 用带命名空间前缀的 id（connector:ifind-mcp），状态文件用裸 id（ifind-mcp）——
# 必须归一化，否则会误判为"未启用"。
_ID_PREFIX = re.compile(r"^(?:connector|custom-mcp):")
_URL_HOST = re.compile(r"^[a-z][a-z0-9+.-]*://([^/?#]+)")
_TOKEN_QUERY = re.compile(r"(?i)([?&](?:token|access_token|api_key|apikey|key)=)[^&\s]+")
CATALOG_REL = "connectors-marketplace/.codebuddy-connector/connectors.json"


def normalize_id(name) -> str:
    """去掉宿主的命名空间前缀，使 `connector:ifind-mcp` 与 `ifind-mcp` 归一到同一连接器。"""
    return _ID_PREFIX.sub("", str(name or "").strip())


def declaration_scope(rel: str) -> str:
    """声明文件所属作用域：`connectors/<账号态>/…` → `connectors/<账号态>`；顶层文件 → ``。"""
    parts = str(rel).split("/")
    if len(parts) >= 2 and parts[0] == "connectors":
        return parts[0] + "/" + parts[1]
    return ""


def redact_url(value: str) -> str:
    """只保留主机名；去掉路径、查询串与任何 token。"""
    if not isinstance(value, str) or not value:
        return ""
    match = _URL_HOST.match(value.strip())
    host = match.group(1) if match else ""
    host = host.rsplit("@", 1)[-1]  # 去掉 user:pass@
    return host.split(":", 1)[0]


def redact_text(value: str) -> str:
    return _TOKEN_QUERY.sub(r"\1***", str(value))


def load_json(path: Path):
    try:
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None


def _blank_entry(connector_id: str) -> dict:
    return {
        "connectorId": connector_id,
        "displayName": connector_id,
        "declaredAs": [],
        "declaredIn": [],
        "hostDeclared": False,
        "catalogListed": False,
        "endpointHost": "",
        "disabledScopes": {},
        "enabled": None,
        "userDisabled": None,
        "everConnected": None,
        "authMode": None,
        "hasStoredAuthorization": False,
    }


def collect(root: Path):
    """返回 (connectors, declarations, active_scope)。只读键名与状态，不读取任何凭据值。

    active_scope = 提供 `enabled` 列表的那个账号态目录（优先 connector-states.v3.json）；
    只有该作用域的 disabled / enabled 事实参与判定，避免多账号态互相覆盖。
    """
    connectors: dict[str, dict] = {}
    declarations: list[str] = []
    active_scope = ""

    def entry_for(connector_id: str) -> dict:
        return connectors.setdefault(connector_id, _blank_entry(connector_id))

    def note_declaration(connector_id, rel, raw):
        entry = entry_for(normalize_id(connector_id))
        entry["hostDeclared"] = True
        if str(connector_id) not in entry["declaredAs"]:
            entry["declaredAs"].append(str(connector_id))
        if rel not in entry["declaredIn"]:
            entry["declaredIn"].append(rel)
        if isinstance(raw, dict):
            url = raw.get("url") or raw.get("endpoint") or ""
            if url:
                entry["endpointHost"] = redact_url(url)
            if isinstance(raw.get("disabled"), bool):
                # disabled 是**账号态作用域**内的事实：connectors/<态>/mcp.json 与顶层 mcp.json 分开记，
                # 否则另一账号态的 disabled=true 会覆盖当前态。
                entry["disabledScopes"][declaration_scope(rel)] = raw["disabled"]
            for key in raw:
                if _SECRET_KEY.search(str(key)):
                    entry["hasStoredAuthorization"] = True

    # 1) 宿主 MCP 清单（顶层）
    top = root / "mcp.json"
    data = load_json(top)
    if isinstance(data, dict) and isinstance(data.get("mcpServers"), dict):
        declarations.append("mcp.json")
        for name, raw in data["mcpServers"].items():
            note_declaration(str(name), "mcp.json", raw)

    # 2) 按账号态分目录的声明与状态
    connectors_dir = root / "connectors"
    if connectors_dir.is_dir():
        for child in sorted(p for p in connectors_dir.iterdir() if p.is_dir()):
            manifest = child / "mcp.json"
            data = load_json(manifest)
            if isinstance(data, dict) and isinstance(data.get("mcpServers"), dict):
                rel = str(manifest.relative_to(root))
                declarations.append(rel)
                for name, raw in data["mcpServers"].items():
                    note_declaration(str(name), rel, raw)
            for state_name in ("connector-states.v3.json", "connector-states.json"):
                state_path = child / state_name
                state = load_json(state_path)
                if not isinstance(state, dict):
                    continue
                rel = str(state_path.relative_to(root))
                if rel not in declarations:
                    declarations.append(rel)
                enabled_list = state.get("enabled")
                if active_scope == "" and isinstance(enabled_list, list):
                    # 当前生效账号态 = 提供 enabled 列表的那个目录；只认第一个（v3 优先）。
                    active_scope = declaration_scope(rel)
                user_disabled = state.get("userDisabled") if isinstance(state.get("userDisabled"), dict) else {}
                ever_list = state.get("everConnected") if isinstance(state.get("everConnected"), list) else []
                overrides = state.get("headerOverrides") if isinstance(state.get("headerOverrides"), dict) else {}
                names = {
                    normalize_id(item)
                    for item in list(connectors)
                    + list(enabled_list or [])
                    + list(user_disabled)
                    + list(overrides)
                    + list(ever_list)
                }
                for name in names:
                    entry = entry_for(name)
                    if isinstance(enabled_list, list):
                        entry["enabled"] = name in enabled_list
                    elif name in user_disabled:
                        entry["enabled"] = not bool(user_disabled.get(name))
                    if name in user_disabled:
                        entry["userDisabled"] = bool(user_disabled.get(name))
                    if ever_list:
                        entry["everConnected"] = name in ever_list
                    if name in overrides:
                        entry["hasStoredAuthorization"] = True

    # 3) 连接器市场目录（仅补名称与授权形态，不作为"已声明"依据）
    catalog = load_json(root / CATALOG_REL)
    if catalog is not None:
        declarations.append(CATALOG_REL)
        items = catalog.get("connectors") if isinstance(catalog, dict) else catalog
        if isinstance(items, list):
            for item in items:
                if not isinstance(item, dict):
                    continue
                cid = str(item.get("id") or "")
                if not cid:
                    continue
                entry = entry_for(cid)
                entry["catalogListed"] = True
                if CATALOG_REL not in entry["declaredIn"]:
                    entry["declaredIn"].append(CATALOG_REL)
                entry["displayName"] = str(item.get("name_zh") or item.get("name") or entry["displayName"])
                if item.get("auth_mode"):
                    entry["authMode"] = str(item["auth_mode"])

    for entry in connectors.values():
        if not entry.get("displayName"):
            entry["displayName"] = entry["connectorId"]
        entry["authEvidence"] = _auth_evidence(entry)
    return list(connectors.values()), declarations, active_scope


def _auth_evidence(entry) -> str:
    if entry.get("hasStoredAuthorization"):
        return "stored_authorization"
    if (entry.get("authMode") or "").lower() == "server-side":
        return "server_side"
    if entry.get("everConnected"):
        return "ever_connected"
    return "none"


def match_target(connectors, id_keys, name_keys):
    """只在宿主已声明的连接器里匹配；目录条目仅作后备名称信息。"""
    best, best_score, best_declared = None, 0, False
    for entry in connectors:
        cid = (entry.get("connectorId") or "").lower()
        name = (entry.get("displayName") or "").lower()
        score = 0
        for key in id_keys:
            if key in cid:
                score += 3
        for key in name_keys:
            if key.lower() in name:
                score += 2
        if score == 0:
            continue
        declared = bool(entry.get("hostDeclared"))
        if (declared, score) > (best_declared, best_score):
            best, best_score, best_declared = entry, score, declared
    return best


def scoped_disabled(entry, active_scope: str):
    """取当前账号态作用域的 disabled 事实；当前态没有该键时退回顶层 mcp.json。"""
    scopes = entry.get("disabledScopes") or {}
    if active_scope and active_scope in scopes:
        return scopes[active_scope]
    return scopes.get("")


def classify_connector(entry, active_scope: str = ""):
    """由宿主声明事实推连接器状态；不断言凭据有效性（见模块 docstring 判定口径）。"""
    if entry is None:
        return {"state": "not_declared", "reason": "宿主未声明同花顺 iFinD 连接器"}
    if not entry.get("hostDeclared"):
        return {
            "state": "not_declared",
            "reason": "同花顺 iFinD 仅出现在连接器市场目录中，宿主未声明该连接器",
        }
    if (
        entry.get("userDisabled") is True
        or entry.get("enabled") is False
        or scoped_disabled(entry, active_scope) is True
    ):
        return {"state": "declared_disabled", "reason": "宿主已声明同花顺 iFinD 连接器但未启用"}
    evidence = entry.get("authEvidence")
    if (entry.get("authMode") or "").lower() in TOKEN_AUTH_MODES and evidence == "none":
        return {
            "state": "likely_unauthenticated",
            "reason": "已声明且启用，但未见授权证据且从未连接成功；需在宿主侧完成授权",
        }
    return {
        "state": "available",
        "reason": "已声明且启用" + ("（授权证据：%s）" % evidence if evidence != "none" else ""),
    }


def resolve_skills_roots(explicit) -> list:
    """解析要扫描的 skills 根：显式参数优先；否则环境变量 → 本技能所在 skills 根 → 常见位置。"""
    if explicit:
        candidates = [str(item) for item in explicit]
    else:
        candidates = []
        env = os.environ.get(SKILLS_ROOT_ENV)
        if env:
            candidates.append(env)
        # 本技能被安装到某个 skills 根时，同花顺 iFinD 技能通常是它的同级副本。
        candidates.append(str(Path(__file__).resolve().parents[2]))
        candidates.extend(DEFAULT_SKILLS_ROOTS)
    roots: list[Path] = []
    for item in candidates:
        path = Path(os.path.expanduser(str(item)))
        if path not in roots:
            roots.append(path)
    return roots


def find_harness_skill(skills_roots) -> dict | None:
    """在 skills 根下查找同花顺 iFinD 技能；只读目录结构与文件是否存在。"""
    for root in skills_roots:
        skill_dir = root / HARNESS_SKILL_ID
        if not skill_dir.is_dir():
            continue
        config = skill_dir / "mcp_config.json"
        return {
            "skillId": HARNESS_SKILL_ID,
            "skillRoot": str(root),
            "path": str(skill_dir),
            "hasSkillManifest": (skill_dir / "SKILL.md").is_file(),
            "callScripts": [name for name in ("call.py", "call-node.js") if (skill_dir / name).is_file()],
            "configFile": config.name,
            "configPresent": config.is_file() and config.stat().st_size > 0,
        }
    return None


def classify_skill(info) -> dict:
    """由技能目录事实推 Harness 取数路径状态；不解析 `mcp_config.json`，不断言密钥有效。"""
    if info is None:
        return {"state": "not_found", "reason": "未在已扫描的 skills 根发现 %s 技能" % HARNESS_SKILL_ID}
    if not info.get("hasSkillManifest") or not info.get("callScripts"):
        return {
            "state": "incomplete",
            "reason": "发现 %s 技能目录但缺少 SKILL.md 或调用脚本（call.py / call-node.js）" % HARNESS_SKILL_ID,
        }
    if not info.get("configPresent"):
        return {
            "state": "likely_unauthenticated",
            "reason": "发现 %s 技能但 %s 缺失或为空，需先写入 iFinD MCP 密钥" % (HARNESS_SKILL_ID, info.get("configFile")),
        }
    return {
        "state": "available",
        "reason": "发现 %s 技能且凭据文件存在（不校验密钥有效性，以运行时调用为准）" % HARNESS_SKILL_ID,
    }


def combine(connector_verdict: dict, skill_verdict: dict):
    """合并两条取数路径：任一路径 available 即取数可用；否则取更接近可用的状态。"""
    if connector_verdict["state"] == "available":
        return "available", "host_connector", "WorkBuddy 宿主连接器可用：%s" % connector_verdict["reason"]
    if skill_verdict["state"] == "available":
        return (
            "available",
            "harness_skill",
            "DeepSeek Harness 的 %s 技能可用：%s" % (HARNESS_SKILL_ID, skill_verdict["reason"]),
        )
    best = skill_verdict if _STATE_RANK[skill_verdict["state"]] > _STATE_RANK[connector_verdict["state"]] else connector_verdict
    reason = "宿主连接器：%s；Harness 技能：%s" % (connector_verdict["reason"], skill_verdict["reason"])
    return best["state"], "", reason


def probe(root: Path, skills_roots=None) -> dict:
    if skills_roots:
        roots: list[Path] = []
        for item in skills_roots:
            path = Path(os.path.expanduser(str(item)))
            if path not in roots:
                roots.append(path)
    else:
        roots = resolve_skills_roots(None)
    root_exists = root.is_dir()
    if root_exists:
        connectors, declarations, active_scope = collect(root)
        entry = match_target(connectors, IFIND_ID_KEYS, IFIND_NAME_KEYS)
        connector_verdict = classify_connector(entry, active_scope)
    else:
        connectors, declarations, active_scope = [], [], ""
        entry = None
        connector_verdict = {"state": "not_declared", "reason": "宿主连接器根目录不存在"}

    skill_info = find_harness_skill(roots)
    skill_verdict = classify_skill(skill_info)
    state, access_path, reason = combine(connector_verdict, skill_verdict)

    target = {
        "label": IFIND_LABEL,
        "state": state,
        "reason": reason,
        "accessPath": access_path,
        "connectorId": entry.get("connectorId") if entry else None,
        "displayName": entry.get("displayName") if entry else None,
        "enabled": entry.get("enabled") if entry else None,
        "userDisabled": entry.get("userDisabled") if entry else None,
        "everConnected": entry.get("everConnected") if entry else None,
        "authMode": entry.get("authMode") if entry else None,
        "authEvidence": entry.get("authEvidence") if entry else None,
        "endpointHost": entry.get("endpointHost") if entry else None,
        "declaredIn": entry.get("declaredIn") if entry else [],
        "connectorVerdict": connector_verdict,
        "harnessSkill": skill_info,
        "harnessSkillVerdict": skill_verdict,
    }

    notes = []
    if not root_exists:
        notes.append("宿主连接器根目录不存在：未从宿主侧发现同花顺 iFinD 连接器")
    if skill_info is None:
        notes.append("未在已扫描的 skills 根发现 %s 技能" % HARNESS_SKILL_ID)
    return {
        "schema": SCHEMA,
        "root": str(root),
        "rootExists": root_exists,
        "skillsRoots": [str(item) for item in roots],
        "activeStateScope": active_scope,
        "declarations": declarations,
        "connectors": connectors,
        "targets": {"ifind": target},
        "notes": notes,
    }


def render_text(result: dict) -> str:
    lines = ["外部数据源探测（只读）· 同花顺 iFinD", "宿主连接器根：" + redact_text(result["root"])]
    lines.append("Harness 技能根：" + ("、".join(redact_text(item) for item in result.get("skillsRoots") or []) or "无"))
    if result.get("rootExists"):
        lines.append("声明文件：" + ("、".join(redact_text(d) for d in result["declarations"]) or "无"))
    else:
        lines.append("声明文件：无（宿主连接器根目录不存在）")
    info = result["targets"]["ifind"]
    lines.append("")
    lines.append("状态：%s（取数路径：%s）" % (info.get("state") or "", info.get("accessPath") or "无可用路径"))
    lines.append("说明：%s" % (info.get("reason") or ""))
    skill = info.get("harnessSkill")
    if skill:
        lines.append(
            "Harness 技能：%s（根 %s；调用脚本 %s；凭据文件 %s）"
            % (
                skill.get("skillId"),
                skill.get("skillRoot"),
                "、".join(skill.get("callScripts") or []) or "无",
                "存在" if skill.get("configPresent") else "缺失",
            )
        )
    for note in result.get("notes") or []:
        lines.append("· " + note)
    lines.append("提示：预检结论只作可用性提示；最终以运行时调用结果为准，失败时按表 D 降级并在交付件中声明。")
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="同花顺 iFinD 取数路径只读探测（不读取凭据值）")
    parser.add_argument(
        "--root",
        default=os.environ.get(DEFAULT_ROOT_ENV) or DEFAULT_ROOT,
        help="宿主连接器根目录（默认 $%s 或 %s）" % (DEFAULT_ROOT_ENV, DEFAULT_ROOT),
    )
    parser.add_argument(
        "--skills-root",
        action="append",
        default=None,
        help="skills 根目录（可重复；默认 $%s、本技能所在 skills 根与常见位置）" % SKILLS_ROOT_ENV,
    )
    parser.add_argument("--format", choices=("json", "text"), default="json")
    args = parser.parse_args(argv)

    root = Path(os.path.expanduser(args.root))
    result = probe(root, args.skills_root)
    if args.format == "text":
        print(render_text(result))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["targets"]["ifind"]["state"] == "available" else 2


if __name__ == "__main__":
    sys.exit(main())
