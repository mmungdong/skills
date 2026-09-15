#!/usr/bin/env python3
"""connector_probe 的单元测试（纯标准库；用临时目录造假宿主配置，不触碰真实凭据）。

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
    declare_wind: bool = True,
    wind_disabled: bool | None = None,
    enabled: list | None = None,
    stored_auth: list | None = None,
    ever: list | None = None,
) -> None:
    servers = {}
    if declare_ifind:
        servers["connector:ifind-mcp"] = {
            "url": "https://api-mcp.51ifind.com:8643/ds-mcp-servers/hexin-ifind-financial-mcp"
        }
    if declare_wind:
        entry = {"url": "https://api.wind.example.com/mcp?token=%s" % FAKE_TOKEN}
        if wind_disabled is not None:
            entry["disabled"] = wind_disabled
        servers["connector:wind-finance"] = entry
    write_json(root / "mcp.json", {"mcpServers": servers})

    state_dir = root / "connectors" / "00000000-1111-2222-3333-444444444444"
    write_json(
        state_dir / "connector-states.v3.json",
        {
            "enabled": enabled if enabled is not None else ["ifind-mcp", "wind-finance"],
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
                {"id": "wind-finance", "name_zh": "Wind Alice 万得金融数据", "auth_mode": "token"},
            ]
        },
    )


class ProbeTest(unittest.TestCase):
    def test_available_when_declared_enabled_and_has_stored_authorization(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_root(root)
            result = probe.probe(root)
            ifind = result["targets"]["ifind"]
            self.assertEqual("available", ifind["state"])
            self.assertEqual("ifind-mcp", ifind["connectorId"])
            self.assertEqual("api-mcp.51ifind.com", ifind["endpointHost"])
            self.assertTrue(ifind["hostDeclared"])
            self.assertEqual("stored_authorization", ifind["authEvidence"])

    def test_catalog_only_connector_is_not_declared(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_root(root, declare_wind=False, enabled=["ifind-mcp"], stored_auth=["ifind-mcp"])
            wind = probe.probe(root)["targets"]["wind"]
            self.assertEqual("not_declared", wind["state"])
            self.assertFalse(wind["hostDeclared"])
            self.assertIn("目录", wind["reason"])

    def test_wind_declared_but_disabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_root(root, wind_disabled=True, enabled=["ifind-mcp"], stored_auth=["ifind-mcp"])
            self.assertEqual("declared_disabled", probe.probe(root)["targets"]["wind"]["state"])

    def test_wind_not_in_enabled_list_is_disabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_root(root, enabled=["ifind-mcp"], stored_auth=["ifind-mcp"])
            self.assertEqual("declared_disabled", probe.probe(root)["targets"]["wind"]["state"])

    def test_token_source_never_connected_is_likely_unauthenticated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_root(root, stored_auth=["ifind-mcp"], ever=["ifind-mcp"])
            wind = probe.probe(root)["targets"]["wind"]
            self.assertEqual("likely_unauthenticated", wind["state"])
            self.assertEqual("none", wind["authEvidence"])

    def test_ever_connected_token_source_is_available_with_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_root(root, stored_auth=["ifind-mcp"], ever=["ifind-mcp", "wind-finance"])
            wind = probe.probe(root)["targets"]["wind"]
            self.assertEqual("available", wind["state"])
            self.assertEqual("ever_connected", wind["authEvidence"])

    def test_other_account_state_disabled_does_not_override_active_state(self):
        """真实场景：connectors/default 把 wind 标为 disabled=true，但当前账号态已启用且连过。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_root(root, stored_auth=["ifind-mcp"], ever=["ifind-mcp", "wind-finance"])
            write_json(
                root / "connectors" / "default" / "mcp.json",
                {
                    "mcpServers": {
                        "connector:wind-finance": {
                            "url": "https://api.wind.example.com/mcp",
                            "disabled": True,
                        }
                    }
                },
            )
            result = probe.probe(root)
            self.assertEqual("connectors/00000000-1111-2222-3333-444444444444", result["activeStateScope"])
            wind = result["targets"]["wind"]
            self.assertEqual("available", wind["state"])
            self.assertEqual("ever_connected", wind["authEvidence"])

    def test_missing_root_is_reported_not_guessed(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "nope"
            result = probe.probe(missing)
            self.assertFalse(result["rootExists"])
            for name in ("ifind", "wind"):
                self.assertEqual("not_declared", result["targets"][name]["state"])
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                code = probe.main(["--root", str(missing), "--format", "json"])
            self.assertEqual(2, code)
            self.assertEqual([], json.loads(buffer.getvalue())["connectors"])

    def test_never_leaks_credentials(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_root(root)
            result = probe.probe(root)
            payload = json.dumps(result, ensure_ascii=False)
            self.assertNotIn(FAKE_TOKEN, payload)
            self.assertNotIn('"Authorization"', payload)
            self.assertNotIn(FAKE_TOKEN, probe.render_text(result))

    def test_text_format_lists_both_targets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_root(root)
            text = probe.render_text(probe.probe(root))
            self.assertIn("同花顺 iFinD", text)
            self.assertIn("万得", text)

    def test_env_var_supplies_default_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_root(root)
            buffer = io.StringIO()
            old = probe.os.environ.get(probe.DEFAULT_ROOT_ENV)
            probe.os.environ[probe.DEFAULT_ROOT_ENV] = str(root)
            try:
                with contextlib.redirect_stdout(buffer):
                    code = probe.main(["--format", "json"])
            finally:
                if old is None:
                    probe.os.environ.pop(probe.DEFAULT_ROOT_ENV, None)
                else:
                    probe.os.environ[probe.DEFAULT_ROOT_ENV] = old
            self.assertEqual(0, code)
            self.assertEqual("available", json.loads(buffer.getvalue())["targets"]["ifind"]["state"])


if __name__ == "__main__":
    unittest.main()
