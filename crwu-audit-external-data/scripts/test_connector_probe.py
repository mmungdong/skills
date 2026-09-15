#!/usr/bin/env python3
"""connector_probe 的单元测试（纯标准库；用临时目录造假宿主配置，不触碰真实凭据）。

覆盖同花顺 iFinD 的两条取数路径：WorkBuddy 宿主连接器声明、DeepSeek Harness 的
`ifind-finance-data` 技能目录。所有用例都显式传 `--skills-root` / `skills_roots`，
避免读到开发机真实 skills 根。

本测试只依赖同目录的 connector_probe.py —— 本技能单独安装时也能通过。
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import connector_probe as probe  # noqa: E402

FAKE_TOKEN = "FAKE-SECRET-TOKEN-1234567890"


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def build_root(
    root: Path,
    *,
    declare_ifind: bool = True,
    ifind_disabled: bool | None = None,
    enabled: list | None = None,
    stored_auth: list | None = None,
    ever: list | None = None,
) -> None:
    """造一个 WorkBuddy 风格的宿主连接器根目录。"""
    servers = {}
    if declare_ifind:
        entry = {"url": "https://api-mcp.51ifind.com:8643/ds-mcp-servers/hexin-ifind-mcp?token=%s" % FAKE_TOKEN}
        if ifind_disabled is not None:
            entry["disabled"] = ifind_disabled
        servers["connector:ifind-mcp"] = entry
    write_json(root / "mcp.json", {"mcpServers": servers})

    state_dir = root / "connectors" / "00000000-1111-2222-3333-444444444444"
    write_json(
        state_dir / "connector-states.v3.json",
        {
            "enabled": enabled if enabled is not None else ["ifind-mcp"],
            "userDisabled": {},
            "everConnected": ever if ever is not None else ["ifind-mcp"],
            "headerOverrides": {
                name: {"Authorization": {"iv": "x", "ct": FAKE_TOKEN}}
                for name in (stored_auth if stored_auth is not None else ["ifind-mcp"])
            },
        },
    )
    write_json(
        root / "connectors-marketplace" / ".codebuddy-connector" / "connectors.json",
        {
            "connectors": [
                {"id": "ifind-mcp", "name_zh": "同花顺iFinD金融数据查询", "auth_mode": "server-side"},
            ]
        },
    )


def build_skill(skills_root: Path, *, manifest: bool = True, call_script: str = "call-node.js", config: bool = True) -> None:
    """造一个 DeepSeek Harness 风格的 `ifind-finance-data` 技能目录。"""
    skill_dir = skills_root / probe.HARNESS_SKILL_ID
    skill_dir.mkdir(parents=True, exist_ok=True)
    if manifest:
        (skill_dir / "SKILL.md").write_text("# ifind-finance-data\n", encoding="utf-8")
    if call_script:
        (skill_dir / call_script).write_text("// stub\n", encoding="utf-8")
    if config:
        (skill_dir / "mcp_config.json").write_text('{"auth_token": "%s"}' % FAKE_TOKEN, encoding="utf-8")


def empty_skills_root(tmp: str) -> Path:
    return Path(tmp) / "no-skills"


class ProbeTest(unittest.TestCase):
    def test_host_connector_available(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "workbuddy"
            build_root(root)
            result = probe.probe(root, [empty_skills_root(tmp)])
            ifind = result["targets"]["ifind"]
            self.assertEqual("available", ifind["state"])
            self.assertEqual("host_connector", ifind["accessPath"])
            self.assertEqual("ifind-mcp", ifind["connectorId"])
            self.assertEqual("api-mcp.51ifind.com", ifind["endpointHost"])
            self.assertEqual("stored_authorization", ifind["authEvidence"])

    def test_harness_skill_available_without_host_connector(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "nope"
            skills_root = Path(tmp) / "skills"
            build_skill(skills_root)
            result = probe.probe(root, [skills_root])
            ifind = result["targets"]["ifind"]
            self.assertEqual("available", ifind["state"])
            self.assertEqual("harness_skill", ifind["accessPath"])
            self.assertFalse(result["rootExists"])
            self.assertEqual(probe.HARNESS_SKILL_ID, ifind["harnessSkill"]["skillId"])
            self.assertTrue(ifind["harnessSkill"]["configPresent"])

    def test_harness_skill_missing_call_script_is_incomplete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "nope"
            skills_root = Path(tmp) / "skills"
            build_skill(skills_root, call_script="")
            ifind = probe.probe(root, [skills_root])["targets"]["ifind"]
            self.assertEqual("incomplete", ifind["state"])
            self.assertEqual("", ifind["accessPath"])

    def test_harness_skill_without_config_is_likely_unauthenticated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "nope"
            skills_root = Path(tmp) / "skills"
            build_skill(skills_root, config=False)
            ifind = probe.probe(root, [skills_root])["targets"]["ifind"]
            self.assertEqual("likely_unauthenticated", ifind["state"])

    def test_catalog_only_connector_is_not_declared(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "workbuddy"
            build_root(root, declare_ifind=False, enabled=[], stored_auth=[])
            ifind = probe.probe(root, [empty_skills_root(tmp)])["targets"]["ifind"]
            self.assertEqual("not_declared", ifind["state"])
            self.assertIn("目录", ifind["reason"])

    def test_connector_declared_but_disabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "workbuddy"
            build_root(root, ifind_disabled=True, enabled=[], stored_auth=[])
            self.assertEqual("declared_disabled", probe.probe(root, [empty_skills_root(tmp)])["targets"]["ifind"]["state"])

    def test_connector_not_in_enabled_list_is_disabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "workbuddy"
            build_root(root, enabled=[], stored_auth=["ifind-mcp"])
            self.assertEqual("declared_disabled", probe.probe(root, [empty_skills_root(tmp)])["targets"]["ifind"]["state"])

    def test_other_account_state_disabled_does_not_override_active_state(self):
        """真实场景：connectors/default 把 ifind 标为 disabled=true，但当前账号态已启用且连过。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "workbuddy"
            build_root(root)
            write_json(
                root / "connectors" / "default" / "mcp.json",
                {
                    "mcpServers": {
                        "connector:ifind-mcp": {
                            "url": "https://api-mcp.51ifind.com:8643/ds-mcp-servers/hexin-ifind-mcp",
                            "disabled": True,
                        }
                    }
                },
            )
            result = probe.probe(root, [empty_skills_root(tmp)])
            self.assertEqual("connectors/00000000-1111-2222-3333-444444444444", result["activeStateScope"])
            self.assertEqual("available", result["targets"]["ifind"]["state"])

    def test_missing_everything_is_reported_not_guessed(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "nope"
            result = probe.probe(missing, [empty_skills_root(tmp)])
            self.assertFalse(result["rootExists"])
            self.assertEqual("not_declared", result["targets"]["ifind"]["state"])
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                code = probe.main(["--root", str(missing), "--skills-root", str(empty_skills_root(tmp)), "--format", "json"])
            self.assertEqual(2, code)
            self.assertEqual([], json.loads(buffer.getvalue())["connectors"])

    def test_main_returns_zero_when_skill_path_available(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "nope"
            skills_root = Path(tmp) / "skills"
            build_skill(skills_root)
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                code = probe.main(["--root", str(missing), "--skills-root", str(skills_root), "--format", "json"])
            self.assertEqual(0, code)
            self.assertEqual("harness_skill", json.loads(buffer.getvalue())["targets"]["ifind"]["accessPath"])

    def test_never_leaks_credentials(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "workbuddy"
            build_root(root)
            skills_root = Path(tmp) / "skills"
            build_skill(skills_root)
            result = probe.probe(root, [skills_root])
            payload = json.dumps(result, ensure_ascii=False)
            self.assertNotIn(FAKE_TOKEN, payload)
            self.assertNotIn('"Authorization"', payload)
            self.assertNotIn(FAKE_TOKEN, probe.render_text(result))

    def test_text_format_excludes_wind(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "workbuddy"
            build_root(root)
            text = probe.render_text(probe.probe(root, [empty_skills_root(tmp)]))
            self.assertIn("同花顺 iFinD", text)
            self.assertNotIn("万得", text)
            self.assertNotIn("wind", text.lower())

    def test_env_var_supplies_default_connector_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "workbuddy"
            build_root(root)
            buffer = io.StringIO()
            old = probe.os.environ.get(probe.DEFAULT_ROOT_ENV)
            probe.os.environ[probe.DEFAULT_ROOT_ENV] = str(root)
            try:
                with contextlib.redirect_stdout(buffer):
                    code = probe.main(["--skills-root", str(empty_skills_root(tmp)), "--format", "json"])
            finally:
                if old is None:
                    probe.os.environ.pop(probe.DEFAULT_ROOT_ENV, None)
                else:
                    probe.os.environ[probe.DEFAULT_ROOT_ENV] = old
            self.assertEqual(0, code)
            self.assertEqual("available", json.loads(buffer.getvalue())["targets"]["ifind"]["state"])

    def test_env_var_supplies_default_skills_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            skills_root = Path(tmp) / "skills"
            build_skill(skills_root)
            buffer = io.StringIO()
            old = probe.os.environ.get(probe.SKILLS_ROOT_ENV)
            probe.os.environ[probe.SKILLS_ROOT_ENV] = str(skills_root)
            try:
                with contextlib.redirect_stdout(buffer):
                    code = probe.main(["--root", str(Path(tmp) / "nope"), "--format", "json"])
            finally:
                if old is None:
                    probe.os.environ.pop(probe.SKILLS_ROOT_ENV, None)
                else:
                    probe.os.environ[probe.SKILLS_ROOT_ENV] = old
            self.assertEqual(0, code)
            self.assertEqual("harness_skill", json.loads(buffer.getvalue())["targets"]["ifind"]["accessPath"])


if __name__ == "__main__":
    unittest.main()
