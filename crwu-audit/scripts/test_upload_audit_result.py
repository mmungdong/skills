#!/usr/bin/env python3
"""AuditResult 钉钉回传的契约测试。"""

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import audit_delivery as delivery  # noqa: E402
import upload_audit_result as uploader  # noqa: E402


SAMPLE_PATH = SCRIPT_DIR / "examples" / "audit-result.sample.json"


def write_rendered_result(directory: Path) -> Path:
    result = json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))
    result["auditTask"]["projectId"] = "TEST-2026-0901"
    result["auditTask"]["auditTime"] = "2026-09-18T14:05:06+08:00"
    result["fileTrace"]["generatedAt"] = "2026-09-18T14:06:07.123456+08:00"
    document = delivery.render(result)
    rendered = delivery.embedded_result_from_document(document)
    path = directory / "审核结果.TEST-2026-0901.json"
    path.write_text(delivery.canonical_json(rendered) + "\n", encoding="utf-8")
    return path


class FakeDws:
    """只替换远端 DWS 传输层；目录树状态用于断言发布行为。"""

    PROFILE = "corp-target:user-current"
    SPACE_ID = "space-target"
    ROOT_ID = "root-target"
    TARGET_ID = "folder-target"

    def __init__(self):
        self.profiles = [
            {
                "profile": self.PROFILE,
                "corpId": "corp-target",
                "corpName": uploader.TARGET_CORP_NAME,
                "userId": "user-current",
                "isOrgCurrent": True,
            },
            {
                "profile": "corp-other:user-other",
                "corpId": "corp-other",
                "corpName": "其他公司",
                "userId": "user-other",
                "isOrgCurrent": True,
            },
        ]
        self.spaces = [
            {
                "spaceId": self.SPACE_ID,
                "rootFolderId": self.ROOT_ID,
                "spaceName": uploader.TARGET_SPACE_NAME,
                "spaceType": "orgSpace",
            }
        ]
        self.children = {
            self.ROOT_ID: [
                {
                    "nodeId": self.TARGET_ID,
                    "name": uploader.TARGET_FOLDER_NAME,
                    "type": "FOLDER",
                }
            ],
            self.TARGET_ID: [],
        }
        self.created_names = []
        self.uploaded_names = []
        self.next_id = 1

    def run_json(self, args, cwd=None):
        args = list(args)
        if args[:2] == ["profile", "list"]:
            return {
                "success": True,
                "currentProfile": self.PROFILE,
                "profiles": copy.deepcopy(self.profiles),
            }

        profile = args[1]
        if args[:1] != ["--profile"] or profile != self.PROFILE:
            raise AssertionError("所有远端读写都必须固定使用目标公司的稳定 profile")
        command = args[2:]

        if command[:4] == ["wiki", "space", "list", "--type"]:
            return {
                "success": True,
                "result": {"items": copy.deepcopy(self.spaces)},
            }

        if command[:2] == ["drive", "+list"]:
            folder_id = command[command.index("--folder") + 1]
            files = copy.deepcopy(self.children.get(folder_id, []))
            return {
                "ok": True,
                "outcome": "success",
                "data": {"count": len(files), "files": files, "hasMore": False},
                "meta": {"pagination": {"endpoint_exhausted": True}},
            }

        if command[:2] == ["drive", "+create-folder"]:
            parent_id = command[command.index("--folder") + 1]
            name = command[command.index("--name") + 1]
            node_id = "created-{0}".format(self.next_id)
            self.next_id += 1
            item = {"nodeId": node_id, "name": name, "type": "FOLDER"}
            self.children.setdefault(parent_id, []).append(item)
            self.children[node_id] = []
            self.created_names.append(name)
            return {"ok": True, "outcome": "success", "data": copy.deepcopy(item)}

        if command[:2] == ["drive", "+upload"]:
            parent_id = command[command.index("--folder") + 1]
            remote_name = command[command.index("--file-name") + 1]
            local_name = command[command.index("--file") + 1]
            local_path = Path(cwd) / local_name
            node_id = "uploaded-{0}".format(self.next_id)
            self.next_id += 1
            item = {
                "nodeId": node_id,
                "name": remote_name,
                "type": "FILE",
                "sizeBytes": local_path.stat().st_size,
            }
            self.children.setdefault(parent_id, []).append(item)
            self.uploaded_names.append(remote_name)
            return {"ok": True, "outcome": "success", "data": copy.deepcopy(item)}

        if command[:2] == ["drive", "+inspect"]:
            node_id = command[command.index("--node") + 1]
            for items in self.children.values():
                for item in items:
                    if item.get("nodeId") == node_id:
                        return {"ok": True, "outcome": "success", "data": copy.deepcopy(item)}
            raise AssertionError("inspect 目标不存在")

        raise AssertionError("未处理的 DWS 命令：{0}".format(command))


class PublishPlanTest(unittest.TestCase):
    def test_uses_audit_time_for_directories_and_generated_time_for_suffix(self):
        result = {
            "auditTask": {
                "projectId": "PRJ/重复:名称",
                "auditTime": "2025-02-03T04:05:06+08:00",
            },
            "fileTrace": {"generatedAt": "2026-09-18T14:06:07.123456+08:00"},
        }

        plan = uploader.build_publish_plan(result)

        self.assertEqual("2025", plan.year)
        self.assertEqual("02", plan.month)
        self.assertEqual(
            "审核结果.PRJ_重复_名称.20260918-140607123456.json",
            plan.remote_name,
        )


class PublishWorkflowTest(unittest.TestCase):
    def test_creates_only_missing_year_and_month_then_uploads(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            json_path = write_rendered_result(Path(temp_dir))
            fake = FakeDws()

            published = uploader.publish_json(json_path, client=fake)

        self.assertEqual(["2026", "09"], fake.created_names)
        self.assertEqual(
            ["审核结果.TEST-2026-0901.20260918-140607123456.json"],
            fake.uploaded_names,
        )
        self.assertEqual(
            "AI资产评估审核结果/2026/09/审核结果.TEST-2026-0901.20260918-140607123456.json",
            published.remote_path,
        )

    def test_reuses_existing_year_and_month(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            json_path = write_rendered_result(Path(temp_dir))
            fake = FakeDws()
            fake.children[fake.TARGET_ID] = [
                {"nodeId": "year-existing", "name": "2026", "type": "FOLDER"}
            ]
            fake.children["year-existing"] = [
                {"nodeId": "month-existing", "name": "09", "type": "FOLDER"}
            ]
            fake.children["month-existing"] = []

            uploader.publish_json(json_path, client=fake)

        self.assertEqual([], fake.created_names)
        self.assertEqual(1, len(fake.children["month-existing"]))

    def test_refuses_duplicate_remote_name_without_overwrite(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            json_path = write_rendered_result(Path(temp_dir))
            fake = FakeDws()
            fake.children[fake.TARGET_ID] = [
                {"nodeId": "year-existing", "name": "2026", "type": "FOLDER"}
            ]
            fake.children["year-existing"] = [
                {"nodeId": "month-existing", "name": "09", "type": "FOLDER"}
            ]
            fake.children["month-existing"] = [
                {
                    "nodeId": "already-there",
                    "name": "审核结果.TEST-2026-0901.20260918-140607123456.json",
                    "type": "FILE",
                }
            ]

            with self.assertRaisesRegex(uploader.PublishError, "已存在同名文件"):
                uploader.publish_json(json_path, client=fake)

        self.assertEqual([], fake.uploaded_names)

    def test_refuses_ambiguous_target_space_before_any_write(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            json_path = write_rendered_result(Path(temp_dir))
            fake = FakeDws()
            fake.spaces.append(copy.deepcopy(fake.spaces[0]))

            with self.assertRaisesRegex(uploader.PublishError, "团队空间.*唯一"):
                uploader.publish_json(json_path, client=fake)

        self.assertEqual([], fake.created_names)
        self.assertEqual([], fake.uploaded_names)

    def test_rejects_non_final_json_before_contacting_dingtalk(self):
        class NoRemoteCalls:
            def run_json(self, args, cwd=None):
                raise AssertionError("JSON 未通过最终态校验时不得访问钉钉")

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "bad.json"
            path.write_text('{"schemaVersion":"1.2.0"}\n', encoding="utf-8")

            with self.assertRaisesRegex(uploader.PublishError, "最终态校验失败"):
                uploader.publish_json(path, client=NoRemoteCalls())


if __name__ == "__main__":
    unittest.main()
