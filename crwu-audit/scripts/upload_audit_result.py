#!/usr/bin/env python3
"""把最终态 AuditResult JSON 回传到固定钉钉团队空间。"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Optional

import audit_delivery as delivery


TARGET_CORP_NAME = "中瑞世联资产评估集团有限公司"
TARGET_SPACE_NAME = "00-【系统专用】AI结果回传区（自动同步·请勿删改）"
TARGET_FOLDER_NAME = "AI资产评估审核结果"


class PublishError(RuntimeError):
    """回传前置条件、目标解析或写后验证失败。"""


@dataclass(frozen=True)
class PublishPlan:
    year: str
    month: str
    remote_name: str


@dataclass(frozen=True)
class PublishResult:
    remote_path: str
    remote_name: str
    node_id: str
    space_id: str


def _parse_timestamp(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise PublishError("{0} 不得为空".format(field))
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise PublishError("{0} 不是有效 ISO 8601 时间：{1}".format(field, value)) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise PublishError("{0} 必须包含时区：{1}".format(field, value))
    return parsed


def _safe_project_id(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PublishError("auditTask.projectId 不得为空")
    normalized = unicodedata.normalize("NFKC", value.strip())
    safe = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", normalized).strip(". ")
    if not safe:
        raise PublishError("auditTask.projectId 无法生成安全文件名")
    return safe


def build_publish_plan(result: dict) -> PublishPlan:
    audit_task = result.get("auditTask") if isinstance(result, dict) else None
    file_trace = result.get("fileTrace") if isinstance(result, dict) else None
    if not isinstance(audit_task, dict) or not isinstance(file_trace, dict):
        raise PublishError("AuditResult 缺少 auditTask 或 fileTrace")

    audit_time = _parse_timestamp(audit_task.get("auditTime"), "auditTask.auditTime")
    generated_at = _parse_timestamp(file_trace.get("generatedAt"), "fileTrace.generatedAt")
    project_id = _safe_project_id(audit_task.get("projectId"))
    suffix = generated_at.strftime("%Y%m%d-%H%M%S%f")
    return PublishPlan(
        year=audit_time.strftime("%Y"),
        month=audit_time.strftime("%m"),
        remote_name="审核结果.{0}.{1}.json".format(project_id, suffix),
    )


class DwsClient:
    def __init__(self, binary: str = "dws"):
        self.binary = binary

    def run_json(self, args: Iterable[str], cwd: Optional[Path] = None) -> dict:
        command = [self.binary, *list(args)]
        if "--format" not in command:
            command.extend(["--format", "json"])
        completed = subprocess.run(
            command,
            cwd=str(cwd) if cwd is not None else None,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            detail = completed.stderr.strip() or completed.stdout.strip() or "无输出"
            raise PublishError("DWS 未返回 JSON：{0}".format(detail)) from exc
        if completed.returncode != 0:
            message = payload.get("errorMsg") if isinstance(payload, dict) else None
            raise PublishError("DWS 执行失败：{0}".format(message or completed.stderr.strip() or payload))
        if not isinstance(payload, dict):
            raise PublishError("DWS 返回值不是 JSON 对象")
        return payload


def _assert_success(payload: dict, action: str) -> None:
    if payload.get("success") is False or payload.get("ok") is False:
        raise PublishError("{0}失败：{1}".format(action, payload.get("errorMsg") or payload))
    outcome = payload.get("outcome")
    if outcome not in (None, "success"):
        raise PublishError("{0}未成功：outcome={1}".format(action, outcome))


def _select_profile(client: Any) -> str:
    payload = client.run_json(["profile", "list"])
    _assert_success(payload, "读取 DWS profile")
    profiles = payload.get("profiles")
    if not isinstance(profiles, list):
        raise PublishError("DWS profile 返回缺少 profiles")

    exact = [item for item in profiles if item.get("corpName") == TARGET_CORP_NAME]
    corp_ids = {item.get("corpId") for item in exact if item.get("corpId")}
    if len(corp_ids) != 1:
        raise PublishError(
            "目标公司必须唯一：精确匹配 {0!r} 得到 {1} 个组织".format(
                TARGET_CORP_NAME, len(corp_ids)
            )
        )
    current = [item for item in exact if item.get("isOrgCurrent") is True]
    if len(current) != 1 or not current[0].get("profile"):
        raise PublishError("目标公司必须有且只有一个 isOrgCurrent=true 账号")
    return str(current[0]["profile"])


def _space_items(payload: dict) -> list:
    result = payload.get("result")
    items = result.get("items") if isinstance(result, dict) else None
    if not isinstance(items, list):
        raise PublishError("团队空间返回缺少 result.items")
    return items


def _resolve_space(client: Any, profile: str) -> dict:
    items = []
    cursor = None
    while True:
        args = ["--profile", profile, "wiki", "space", "list", "--type", "orgSpace"]
        if cursor:
            args.extend(["--cursor", cursor])
        payload = client.run_json(args)
        _assert_success(payload, "读取企业团队空间")
        items.extend(_space_items(payload))
        result = payload.get("result") or {}
        cursor = result.get("nextToken")
        if not cursor:
            break

    exact = [
        item
        for item in items
        if item.get("spaceName") == TARGET_SPACE_NAME and item.get("spaceType") == "orgSpace"
    ]
    if len(exact) != 1:
        raise PublishError(
            "目标团队空间必须唯一：精确匹配 {0!r} 得到 {1} 项".format(
                TARGET_SPACE_NAME, len(exact)
            )
        )
    space = exact[0]
    if not space.get("spaceId") or not space.get("rootFolderId"):
        raise PublishError("目标团队空间缺少 spaceId 或 rootFolderId")
    return space


def _list_children(client: Any, profile: str, folder_id: str) -> list:
    payload = client.run_json(
        [
            "--profile",
            profile,
            "drive",
            "+list",
            "--folder",
            folder_id,
            "--page-all",
            "--max-pages",
            "20",
            "--max-items",
            "500",
        ]
    )
    _assert_success(payload, "读取钉钉文件夹")
    data = payload.get("data")
    files = data.get("files") if isinstance(data, dict) else None
    if not isinstance(files, list):
        raise PublishError("钉钉文件夹返回缺少 data.files")
    if data.get("hasMore") is True:
        raise PublishError("钉钉文件夹列表未完整返回")
    pagination = (payload.get("meta") or {}).get("pagination") or {}
    if pagination.get("endpoint_exhausted") is False:
        raise PublishError("钉钉文件夹分页未完成")
    return files


def _resolve_exact_folder(items: list, name: str, label: str) -> str:
    exact = [item for item in items if item.get("name") == name]
    if len(exact) != 1:
        raise PublishError("{0}必须唯一：精确匹配 {1!r} 得到 {2} 项".format(label, name, len(exact)))
    if str(exact[0].get("type")).upper() != "FOLDER" or not exact[0].get("nodeId"):
        raise PublishError("{0}不是有效文件夹：{1!r}".format(label, name))
    return str(exact[0]["nodeId"])


def _ensure_date_folder(
    client: Any,
    profile: str,
    space_id: str,
    parent_id: str,
    name: str,
    label: str,
) -> str:
    items = _list_children(client, profile, parent_id)
    exact = [item for item in items if item.get("name") == name]
    if len(exact) > 1:
        raise PublishError("{0}必须唯一：精确匹配 {1!r} 得到 {2} 项".format(label, name, len(exact)))
    if exact:
        return _resolve_exact_folder(items, name, label)

    payload = client.run_json(
        [
            "--profile",
            profile,
            "drive",
            "+create-folder",
            "--name",
            name,
            "--folder",
            parent_id,
            "--space-id",
            space_id,
            "--yes",
        ]
    )
    _assert_success(payload, "创建{0}".format(label))
    return _resolve_exact_folder(_list_children(client, profile, parent_id), name, label)


def _validate_final_result(path: Path) -> dict:
    try:
        result = delivery.load_result(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise PublishError("读取 AuditResult 失败：{0}".format(exc)) from exc
    errors = delivery.validate(result, rendered=True, expect_renderer=True)
    if errors:
        raise PublishError("AuditResult 最终态校验失败：{0}".format("；".join(errors)))
    return result


def _node_size(item: dict) -> Optional[int]:
    for key in ("sizeBytes", "size"):
        value = item.get(key)
        if isinstance(value, int):
            return value
    return None


def publish_json(path: Path, client: Optional[Any] = None) -> PublishResult:
    json_path = Path(path).expanduser().resolve()
    result = _validate_final_result(json_path)
    plan = build_publish_plan(result)
    dws = client or DwsClient()

    profile = _select_profile(dws)
    space = _resolve_space(dws, profile)
    space_id = str(space["spaceId"])
    root_id = str(space["rootFolderId"])
    target_id = _resolve_exact_folder(
        _list_children(dws, profile, root_id),
        TARGET_FOLDER_NAME,
        "目标结果文件夹",
    )
    year_id = _ensure_date_folder(dws, profile, space_id, target_id, plan.year, "年份文件夹")
    month_id = _ensure_date_folder(dws, profile, space_id, year_id, plan.month, "月份文件夹")

    before = _list_children(dws, profile, month_id)
    if any(item.get("name") == plan.remote_name for item in before):
        raise PublishError("目标月份目录已存在同名文件，拒绝覆盖：{0}".format(plan.remote_name))

    payload = dws.run_json(
        [
            "--profile",
            profile,
            "drive",
            "+upload",
            "--file",
            json_path.name,
            "--file-name",
            plan.remote_name,
            "--folder",
            month_id,
            "--space-id",
            space_id,
            "--yes",
        ],
        cwd=json_path.parent,
    )
    _assert_success(payload, "上传 AuditResult JSON")

    after = _list_children(dws, profile, month_id)
    uploaded = [item for item in after if item.get("name") == plan.remote_name]
    if len(uploaded) != 1 or not uploaded[0].get("nodeId"):
        raise PublishError("上传后无法唯一读回目标 JSON：{0}".format(plan.remote_name))
    if str(uploaded[0].get("type")).upper() == "FOLDER":
        raise PublishError("上传后读回目标不是普通文件：{0}".format(plan.remote_name))

    local_size = json_path.stat().st_size
    remote_size = _node_size(uploaded[0])
    if remote_size is None:
        inspected = dws.run_json(
            ["--profile", profile, "drive", "+inspect", "--node", str(uploaded[0]["nodeId"])]
        )
        _assert_success(inspected, "读取已上传 JSON 元数据")
        inspected_data = inspected.get("data") if isinstance(inspected.get("data"), dict) else {}
        remote_size = _node_size(inspected_data)
    if remote_size is not None and remote_size != local_size:
        raise PublishError(
            "上传后文件大小不一致：local={0}, remote={1}".format(local_size, remote_size)
        )

    remote_path = "/".join([TARGET_FOLDER_NAME, plan.year, plan.month, plan.remote_name])
    return PublishResult(
        remote_path=remote_path,
        remote_name=plan.remote_name,
        node_id=str(uploaded[0]["nodeId"]),
        space_id=space_id,
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="回传最终态 AuditResult JSON 到固定钉钉团队空间")
    parser.add_argument("path", help="最终渲染态的 审核结果.<项目ID>.json")
    args = parser.parse_args(argv)
    try:
        published = publish_json(Path(args.path))
    except PublishError as exc:
        print("ERROR: {0}".format(exc), file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "ok": True,
                "corpName": TARGET_CORP_NAME,
                "spaceName": TARGET_SPACE_NAME,
                "remotePath": published.remote_path,
                "nodeId": published.node_id,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
