import datetime
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest


# 源仓契约测试：据本文件位置上溯定位 skills 根与源仓根（不硬编码仓库布局）。
# 校验对象是本技能脚本 + 完整技能树，运行时不需要本测试。
SKILLS_ROOT = Path(__file__).resolve().parents[2]  # skills/<skill>/scripts/<file> → skills 根
REPO_ROOT = SKILLS_ROOT.parent                     # 源仓根（--repo-root / 真实仓库回归用）
SCRIPTS_DIR = Path(__file__).resolve().parent
CHECKER = SCRIPTS_DIR / "check_audit_skill_mappings.py"
MAINTAINER_SKILL = SCRIPTS_DIR.parent

COMPLETE_TREE = """
- 📁 01-业务路线/
  - 📁 01-资产经营/
    - 📁 租赁与租金评估/
      - 📄 01-业务通用审核要点
- 📁 02-资产类型/
  - 📁 01-房地产/
    - 📁 01-共性参考/
      - 📄 02-评估审核条目
    - 📁 02-细分对象/
      - 📁 01-土地使用权/
        - 📄 评估审核条目
""".strip()


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text).lstrip(), encoding="utf-8")


def _registry(asset_skill: str, business_skill: str) -> str:
    return f"""
    # 多轴技能注册表

    | axis | label | skill | status | load behavior |
    | --- | --- | --- | --- | --- |
    | asset | 房地产 | {asset_skill} | available | load |
    | business | 资产经营 | {business_skill} | available | load |
    """


def _create_leaf(repo: Path, name: str, root: str) -> None:
    leaf = repo / "skills" / name
    _write(
        leaf / "SKILL.md",
        f"""
        ---
        name: {name}
        description: Use when the matching crwu-audit axis label is selected.
        ---

        # {name}
        """,
    )
    _write(leaf / "references" / "00-applicability.md", "# Applicability\n")
    _write(
        leaf / "references" / "01-kb-assembly.md",
        f"""
        # KB assembly

        | source_key | owner_axis | canonical_label | kb_root | request_kind | recursive | required |
        | --- | --- | --- | --- | --- | --- | --- |
        | ROOT | test | test | `{root}` | directory | true | true |
        """,
    )
    _write(leaf / "references" / "02-review-focus.md", "# Review focus\n")


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


def _create_router(repo: Path) -> None:
    """Minimal router layer, so routing-consistency checks have something to compare."""
    refs = repo / "skills" / "crwu-audit" / "references"
    _write(
        repo / "skills" / "crwu-audit" / "SKILL.md",
        """
        # 总路由

        按 `00-input-and-route-profile.md` 画像，经 `08-union-dispatch-rules.md` 稳定并集加载。
        """,
    )
    for name in ROUTER_REFERENCES:
        target = refs / name
        if target.is_file():
            continue
        _write(target, "# reference\n")
    _write(
        refs / "08-union-dispatch-rules.md",
        """
        # 稳定并集

        skills_to_load = stable_unique(scope_skills, asset_skills, business_skills, method_skills, overlay_skills, public_skills)
        """,
    )


def _create_valid_repo(repo: Path) -> None:
    _write(
        repo / "skills" / "crwu-audit" / "references" / "07-skill-registry.md",
        _registry("crwu-audit-asset-realestate", "crwu-audit-biz-asset-operation"),
    )
    _write(
        repo / "skills" / "crwu-audit" / "references" / "03-asset-classification.md",
        "| canonical 资产类型 | 主要信号 | 目标技能 |\n| --- | --- | --- |\n| 房地产 | 房建类 | `crwu-audit-asset-realestate` |\n",
    )
    _write(
        repo / "skills" / "crwu-audit" / "references" / "04-business-classification.md",
        "| 一级业务 | 子业务 | 目标技能 |\n| --- | --- | --- |\n| 资产经营 | 租赁与租金评估 | `crwu-audit-biz-asset-operation` |\n",
    )
    _create_router(repo)
    _create_leaf(
        repo,
        "crwu-audit-asset-realestate",
        "02-资产类型/01-房地产/",
    )
    _create_leaf(
        repo,
        "crwu-audit-biz-asset-operation",
        "01-业务路线/01-资产经营/",
    )



# 源仓契约测试所需的完整技能族：安装副本里缺任何一个 → 显式 skip（不失败、不静默通过）。
_REQUIRED_SIBLINGS = (
    "crwu-audit",
    "crwu-audit-asset-realestate",
    "crwu-audit-biz-asset-operation",
    "crwu-audit-public-general-standards",
    "crwu-audit-datacheck",
    "crwu-audit-optimize",
    "crwu-audit-skill-maintainer",
    "crwu-dws",
)


def _requires_skill_tree(test):
    """源仓契约测试前提：同级技能与源仓文档齐备。

    技能以副本安装时这些内容可能不在（例如只装了单个技能）——此时**显式 skip**，
    既不当成失败，也不静默通过。运行时不需要本测试。
    """

    def wrapper(self, *args, **kwargs):
        missing = [name for name in _REQUIRED_SIBLINGS if not (SKILLS_ROOT / name).is_dir()]
        if missing:
            self.skipTest(f"非完整技能树（缺少同级技能 {', '.join(missing)}）：跳过源仓契约测试")
        return test(self, *args, **kwargs)

    return wrapper


class AuditSkillMaintainerCheckerTest(unittest.TestCase):
    def run_checker(
        self,
        repo: Path,
        catalog: Path,
        *extra: str,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(CHECKER),
                "--repo-root",
                str(repo),
                "--catalog",
                str(catalog),
                "--format",
                "json",
                *extra,
            ],
            text=True,
            capture_output=True,
            check=False,
        )

    def test_markdown_tree_proposes_only_missing_first_level_skills(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "repo"
            tree = root / "tree.md"
            tree.write_text(COMPLETE_TREE, encoding="utf-8")

            result = self.run_checker(repo, tree)

            self.assertEqual(0, result.returncode, result.stderr)
            report = json.loads(result.stdout)
            create_proposals = {
                (item["axis"], item["label"])
                for item in report["proposals"]
                if item["action"] == "create_skill"
            }
            self.assertEqual(
                {("asset", "房地产"), ("business", "资产经营")},
                create_proposals,
            )
            proposed_labels = {item["label"] for item in report["proposals"]}
            self.assertNotIn("土地使用权", proposed_labels)
            self.assertNotIn("租赁与租金评估", proposed_labels)
            self.assertTrue(
                all(item["name_review_required"] for item in report["proposals"]),
                report["proposals"],
            )

    def test_valid_parent_skills_and_directory_roots_are_clean(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "repo"
            tree = root / "tree.md"
            tree.write_text(COMPLETE_TREE, encoding="utf-8")
            _create_valid_repo(repo)

            result = self.run_checker(repo, tree, "--strict")

            self.assertEqual(0, result.returncode, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual([], report["findings"])
            self.assertEqual([], report["proposals"])

    def test_distinguishes_naming_mapping_and_knowledge_content_gaps(self):
        incomplete_tree = """
        - 📁 01-业务路线/
          - 📁 01-资产经营/
            - 📁 租赁与租金评估/
        - 📁 02-资产类型/
          - 📁 01-房地产/
            - 📁 02-细分对象/
              - 📁 01-土地使用权/
        """
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "repo"
            tree = root / "tree.md"
            tree.write_text(textwrap.dedent(incomplete_tree).strip(), encoding="utf-8")
            _write(
                repo / "skills" / "crwu-audit" / "references" / "07-skill-registry.md",
                _registry(
                    "crwu-audit-asset-realestate",
                    "crwu-audit-business-asset-operation",
                ),
            )
            asset = repo / "skills" / "crwu-audit-asset-realestate"
            _write(asset / "SKILL.md", "---\nname: crwu-audit-asset-realestate\ndescription: Use when selected.\n---\n")
            _write(asset / "references" / "00-applicability.md", "# A\n")
            _write(asset / "references" / "02-review-focus.md", "# R\n")
            _write(
                asset / "references" / "01-kb-assembly.md",
                "| source_key | kb_root | request_kind | recursive |\n| --- | --- | --- | --- |\n| OLD | `02-资产类型/01-房地产/01-共性参考/02-评估审核条目` | file | false |\n",
            )
            _create_leaf(
                repo,
                "crwu-audit-business-asset-operation",
                "01-业务路线/01-资产经营/",
            )

            result = self.run_checker(repo, tree)

            self.assertEqual(0, result.returncode, result.stderr)
            codes = {item["code"] for item in json.loads(result.stdout)["findings"]}
            self.assertTrue(
                {
                    "LEGACY_BUSINESS_PREFIX",
                    "ASSEMBLY_FIRST_LEVEL_ROOT_MISSING",
                    "ASSEMBLY_FILE_MAPPING",
                    "ASSET_COMMON_REFERENCE_MISSING",
                    "ASSET_SUBOBJECT_REVIEW_MISSING",
                    "BUSINESS_SUBROUTE_REVIEW_MISSING",
                }.issubset(codes),
                codes,
            )

    def test_snapshot_and_node_index_normalize_to_same_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "repo"
            _create_valid_repo(repo)
            snapshot = root / "snapshot.json"
            node_index = root / "node-index.json"
            snapshot.write_text(
                json.dumps(
                    {
                        "schema": "crwu.kb-catalog.snapshot.v1",
                        "generated_at": "2026-09-10T10:59:30+08:00",
                        "stats": {"complete": True},
                        "nodes": [
                            {
                                "nodeId": "business",
                                "name": "01-业务路线",
                                "type": "folder",
                                "children": [
                                    {
                                        "nodeId": "biz-parent",
                                        "name": "01-资产经营",
                                        "type": "folder",
                                        "children": [
                                            {
                                                "nodeId": "biz-child",
                                                "name": "租赁与租金评估",
                                                "type": "folder",
                                                "children": [
                                                    {
                                                        "nodeId": "biz-review",
                                                        "name": "01-业务通用审核要点",
                                                        "type": "adoc",
                                                        "children": [],
                                                    }
                                                ],
                                            }
                                        ],
                                    }
                                ],
                            },
                            {
                                "nodeId": "asset",
                                "name": "02-资产类型",
                                "type": "folder",
                                "children": [
                                    {
                                        "nodeId": "asset-parent",
                                        "name": "01-房地产",
                                        "type": "folder",
                                        "children": [
                                            {
                                                "nodeId": "common",
                                                "name": "01-共性参考",
                                                "type": "folder",
                                                "children": [
                                                    {
                                                        "nodeId": "common-review",
                                                        "name": "02-评估审核条目",
                                                        "type": "adoc",
                                                        "children": [],
                                                    }
                                                ],
                                            },
                                            {
                                                "nodeId": "subobjects",
                                                "name": "02-细分对象",
                                                "type": "folder",
                                                "children": [
                                                    {
                                                        "nodeId": "land",
                                                        "name": "01-土地使用权",
                                                        "type": "folder",
                                                        "children": [
                                                            {
                                                                "nodeId": "land-review",
                                                                "name": "评估审核条目",
                                                                "type": "adoc",
                                                                "children": [],
                                                            }
                                                        ],
                                                    }
                                                ],
                                            },
                                        ],
                                    }
                                ],
                            },
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            by_path = {
                "01-业务路线/": ["business"],
                "01-业务路线/01-资产经营/": ["biz-parent"],
                "01-业务路线/01-资产经营/租赁与租金评估/": ["biz-child"],
                "01-业务路线/01-资产经营/租赁与租金评估/01-业务通用审核要点": ["biz-review"],
                "02-资产类型/": ["asset"],
                "02-资产类型/01-房地产/": ["asset-parent"],
                "02-资产类型/01-房地产/01-共性参考/": ["common"],
                "02-资产类型/01-房地产/01-共性参考/02-评估审核条目": ["common-review"],
                "02-资产类型/01-房地产/02-细分对象/": ["subobjects"],
                "02-资产类型/01-房地产/02-细分对象/01-土地使用权/": ["land"],
                "02-资产类型/01-房地产/02-细分对象/01-土地使用权/评估审核条目": ["land-review"],
            }
            node_index.write_text(
                json.dumps(
                    {
                        "schema": "crwu.kb-dir-cache.nodeindex.v1",
                        "built_from_snapshot_at": "2026-09-10T10:59:30+08:00",
                        "by_path": by_path,
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            snapshot_result = self.run_checker(repo, snapshot)
            index_result = self.run_checker(repo, node_index)

            self.assertEqual(0, snapshot_result.returncode, snapshot_result.stderr)
            self.assertEqual(0, index_result.returncode, index_result.stderr)
            snapshot_report = json.loads(snapshot_result.stdout)
            index_report = json.loads(index_result.stdout)
            self.assertEqual(
                snapshot_report["catalog"]["paths"],
                index_report["catalog"]["paths"],
            )

    def test_strict_mode_exits_nonzero_when_errors_exist(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "repo"
            tree = root / "tree.md"
            tree.write_text(COMPLETE_TREE, encoding="utf-8")

            result = self.run_checker(repo, tree, "--strict")

            self.assertEqual(1, result.returncode)
            report = json.loads(result.stdout)
            self.assertGreater(report["summary"]["errors"], 0)

    def test_pending_legacy_registry_name_is_replaced_by_biz_proposal(self):
        business_tree = """
        - 📁 01-业务路线/
          - 📁 01-资产经营/
            - 📁 租赁与租金评估/
              - 📄 01-业务通用审核要点
        """
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "repo"
            tree = root / "tree.md"
            tree.write_text(textwrap.dedent(business_tree).strip(), encoding="utf-8")
            _write(
                repo / "skills/crwu-audit/references/07-skill-registry.md",
                """
                | axis | label | skill | status | load behavior |
                | --- | --- | --- | --- | --- |
                | business | 资产经营 | crwu-audit-business-rent | pending | record gap |
                """,
            )

            result = self.run_checker(repo, tree)

            self.assertEqual(0, result.returncode, result.stderr)
            report = json.loads(result.stdout)
            self.assertIn(
                "LEGACY_BUSINESS_PREFIX",
                {item["code"] for item in report["findings"]},
            )
            proposal = next(
                item
                for item in report["proposals"]
                if item["axis"] == "business" and item["label"] == "资产经营"
            )
            self.assertEqual("crwu-audit-biz-asset-operation", proposal["skill_name"])
            self.assertTrue(proposal["name_review_required"])

    def test_markdown_tree_preserves_declared_capture_time(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "repo"
            tree = root / "tree.md"
            tree.write_text(
                "# 目录树\n- 抓取时间：2026-09-10T10:59:30+08:00\n" + COMPLETE_TREE,
                encoding="utf-8",
            )

            result = self.run_checker(repo, tree)

            self.assertEqual(0, result.returncode, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(
                "2026-09-10T10:59:30+08:00",
                report["catalog"]["generated_at"],
            )

    def _kb_tool(self):
        module_path = SCRIPTS_DIR / "kb_tool.py"
        spec = importlib.util.spec_from_file_location("kb_tool_for_selfcontainment", module_path)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_repo_reference_lint_flags_repo_directories_in_skill_content(self):
        """技能正文不得引用代码仓库目录：技能以副本安装时这些路径不存在。"""
        cases = [
            ("docs", "参考 `docs/design-crwu-dws.md` 的设计口径。"),
            ("tools", "运行 `tools/kb/kb_tool.py validate`。"),
            ("bin", "用 `./bin/darwin/crwu` 登录。"),
            ("docs", "见 `../docs/x.md`。"),
            ("cmd", "源码在 `cmd/crwu` 下。"),
            ("internal", "实现见 `internal/platform`。"),
            ("Makefile", "构建走 `Makefile`。"),
            ("skills/<skill>/", "调用 `skills/crwu-dws/scripts/x.py`。"),
        ]
        module = self._kb_tool()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "skills"
            for index, (_label, body) in enumerate(cases):
                skill = root / f"crwu-demo-{index}"
                _write(skill / "SKILL.md", f"---\nname: crwu-demo-{index}\n---\n\n{body}\n")

            errors, _warnings = module.repo_reference_lint(str(root))

            self.assertEqual(len(cases), len(errors), errors)
            for label, _body in cases:
                self.assertTrue(
                    any(label in error for error in errors),
                    f"{label} 未被 lint 拦下：{errors}",
                )

    def test_repo_reference_lint_ignores_system_paths_and_urls(self):
        """shebang 的 /usr/bin/env 与外部文档 URL 不是仓库目录，不得误报。"""
        module = self._kb_tool()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "skills"
            skill = root / "crwu-demo"
            _write(
                skill / "SKILL.md",
                "---\nname: crwu-demo\n---\n\n# demo\n"
                "外部文档：https://www.example.com/docs/cli/skills\n",
            )
            _write(skill / "scripts" / "tool.py", '#!/usr/bin/env python3\nprint("ok")\n')

            errors, _warnings = module.repo_reference_lint(str(root))

            self.assertEqual([], errors)

    def test_repo_reference_lint_flags_links_escaping_the_skill_directory(self):
        module = self._kb_tool()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "skills"
            _write(
                root / "crwu-demo/SKILL.md",
                "---\nname: crwu-demo\n---\n\n见 [手册](../../docs/cli-manual.md)。\n",
            )

            errors, _warnings = module.repo_reference_lint(str(root))

            self.assertEqual(1, len(errors), errors)
            self.assertIn("逃出技能目录", errors[0])

    def test_repo_reference_lint_exempts_declared_source_repo_tests(self):
        """声明为源仓契约测试/源仓维护工具的脚本可定位源仓（运行时不需要它们）。"""
        module = self._kb_tool()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "skills"
            skill = root / "crwu-demo"
            _write(skill / "SKILL.md", "---\nname: crwu-demo\n---\n\n# demo\n")
            _write(
                skill / "scripts" / "test_contract.py",
                '"""源仓契约测试：只在源仓维护时运行。"""\n'
                'REPO_ROOT = 1\n'
                'DOC = "docs/design-x.md"\n',
            )
            _write(skill / "scripts" / "tool.py", '"""源仓维护工具。"""\nDOC = "docs/x.md"\n')

            errors, _warnings = module.repo_reference_lint(str(root))

            self.assertEqual([], errors)

    def test_repo_reference_lint_skips_skill_root_documents(self):
        """skills 根的 AGENTS.md / README.md 是源仓文档，不是技能。"""
        module = self._kb_tool()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "skills"
            _write(root / "README.md", "见 `docs/design-x.md`。\n")
            _write(root / "AGENTS.md", "见 `skills/crwu-demo/SKILL.md`。\n")
            _write(root / "crwu-demo/SKILL.md", "---\nname: crwu-demo\n---\n\n# demo\n")

            errors, _warnings = module.repo_reference_lint(str(root))

            self.assertEqual([], errors)

    @_requires_skill_tree
    def test_every_skill_is_self_contained(self):
        """真实仓库回归：每个技能都不得引用代码仓库目录。"""
        module = self._kb_tool()

        errors, _warnings = module.repo_reference_lint(str(SKILLS_ROOT))

        self.assertEqual([], errors)

    @_requires_skill_tree
    def test_maintainer_skill_passes_live_source_protocol_lint(self):
        module_path = SCRIPTS_DIR / "kb_tool.py"
        spec = importlib.util.spec_from_file_location("kb_tool_for_test", module_path)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        errors, _warnings = module.live_protocol_lint(str(MAINTAINER_SKILL), [])

        self.assertEqual([], errors)


def _codes(report: dict) -> set[str]:
    return {item["code"] for item in report["findings"]}


def _findings(report: dict, code: str) -> list[dict]:
    return [item for item in report["findings"] if item["code"] == code]


# ---- 真实 crwu-dws 产物（不是探针自造的 fixture） ----
DWS_CACHE_ROOT = Path.home() / ".crwu" / "knowledge" / "dws-dir-cache"
LIVE_CATALOG_FORMS = ("目录快照.json", "node-index.json", "目录树.md")
AUDIT_FAMILY_ROOTS = ("01-业务路线/", "02-资产类型/")
# `crwu-dws` declares this as its default target knowledge base; the audit skills deliberately
# never name it, so the identity binding lives here (test-side only) instead of in a skill.
AUDIT_KB_NAME = "中瑞世联评估审核知识库"


def _cache_capture_time(directory: Path) -> str:
    """`last_successful_at` from the cache identity file; empty when unreadable."""
    try:
        meta = json.loads((directory / ".cache-meta.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    value = meta.get("last_successful_at")
    return value if isinstance(value, str) else ""


def _cache_space_name(directory: Path) -> str:
    """`space.name` from the cache identity file; empty when unreadable."""
    try:
        meta = json.loads((directory / ".cache-meta.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    space = meta.get("space")
    if not isinstance(space, dict):
        return ""
    name = space.get("name")
    return name if isinstance(name, str) else ""


def _live_cache_dirs() -> list[Path]:
    """Real crwu-dws directory caches of the audit knowledge base, newest capture first.

    An explicit `CRWU_DWS_CACHE_DIR` (one cache directory) or `CRWU_DWS_SNAPSHOT` (one snapshot
    file, whose directory is used) is honoured as given — pointing it at another knowledge base
    is a real failure, not something to skip. Automatic discovery only accepts caches whose
    `.cache-meta.json` identifies the audit knowledge base, and never returns a directory
    without a `目录快照.json`, so a stale or unrelated cache makes the live regressions skip
    cleanly instead of failing or erroring.
    """
    override_dir = os.environ.get("CRWU_DWS_CACHE_DIR")
    if override_dir:
        candidates = [Path(override_dir).expanduser()]
    else:
        override_file = os.environ.get("CRWU_DWS_SNAPSHOT")
        if override_file:
            candidates = [Path(override_file).expanduser().parent]
        elif DWS_CACHE_ROOT.is_dir():
            candidates = [
                entry
                for entry in DWS_CACHE_ROOT.iterdir()
                if entry.is_dir() and _cache_space_name(entry) == AUDIT_KB_NAME
            ]
        else:
            candidates = []
    dirs = [entry for entry in candidates if (entry / "目录快照.json").is_file()]
    return sorted(dirs, key=_cache_capture_time, reverse=True)


def _is_audit_family_catalog(paths: tuple[str, ...]) -> bool:
    """True when the parsed catalog actually carries the audit family's first-level roots."""
    return all(any(path.startswith(root) for path in paths) for root in AUDIT_FAMILY_ROOTS)


def run_checker(repo: Path, catalog: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(CHECKER),
            "--repo-root",
            str(repo),
            "--catalog",
            str(catalog),
            "--format",
            "json",
            *extra,
        ],
        text=True,
        capture_output=True,
        check=False,
    )


class AuditSkillMaintainerFindingCoverageTest(unittest.TestCase):
    """One fixture per detection the maintainer contract requires."""

    def _tree(self, root: Path, text: str = COMPLETE_TREE) -> Path:
        tree = root / "tree.md"
        tree.write_text(textwrap.dedent(text).strip(), encoding="utf-8")
        return tree

    def test_available_registry_skill_directory_missing_is_reported(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "repo"
            tree = self._tree(root)
            _write(
                repo / "skills/crwu-audit/references/07-skill-registry.md",
                _registry("crwu-audit-asset-realestate", "crwu-audit-biz-asset-operation"),
            )

            report = json.loads(run_checker(repo, tree).stdout)

            self.assertEqual(
                {"crwu-audit-asset-realestate", "crwu-audit-biz-asset-operation"},
                {item["skill"] for item in _findings(report, "AVAILABLE_SKILL_DIRECTORY_MISSING")},
            )

    def test_registry_row_absent_from_catalog_is_still_validated(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "repo"
            tree = self._tree(root)
            _write(
                repo / "skills/crwu-audit/references/07-skill-registry.md",
                """
                | axis | label | skill | status | load behavior |
                | --- | --- | --- | --- | --- |
                | asset | 房地产 | crwu-audit-asset-realestate | available | load |
                | asset | 机器设备 | crwu-audit-asset-equipment | available | load |
                | business | 资产经营 | crwu-audit-biz-asset-operation | available | load |
                """,
            )
            _create_leaf(repo, "crwu-audit-asset-realestate", "02-资产类型/01-房地产/")
            _create_leaf(repo, "crwu-audit-biz-asset-operation", "01-业务路线/01-资产经营/")

            report = json.loads(run_checker(repo, tree).stdout)

            self.assertEqual(
                ["机器设备"],
                [item["label"] for item in _findings(report, "AVAILABLE_SKILL_DIRECTORY_MISSING")],
            )
            self.assertEqual(
                ["机器设备"],
                [item["label"] for item in _findings(report, "REGISTRY_LABEL_NOT_IN_CATALOG")],
            )

    def test_directory_and_frontmatter_name_mismatch_is_reported(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "repo"
            tree = self._tree(root)
            _write(
                repo / "skills/crwu-audit/references/07-skill-registry.md",
                _registry("crwu-audit-asset-realestate", "crwu-audit-biz-asset-operation"),
            )
            _create_leaf(repo, "crwu-audit-asset-realestate", "02-资产类型/01-房地产/")
            _create_leaf(repo, "crwu-audit-biz-asset-operation", "01-业务路线/01-资产经营/")
            _write(
                repo / "skills/crwu-audit-asset-realestate/SKILL.md",
                "---\nname: crwu-audit-asset-realty\ndescription: Use when selected.\n---\n",
            )

            report = json.loads(run_checker(repo, tree).stdout)

            self.assertIn("crwu-audit-asset-realestate", {i["skill"] for i in _findings(report, "SKILL_NAME_MISMATCH")})

    def test_registry_name_held_by_a_differently_named_directory_is_reported(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "repo"
            tree = self._tree(root)
            _write(
                repo / "skills/crwu-audit/references/07-skill-registry.md",
                """
                | axis | label | skill | status | load behavior |
                | --- | --- | --- | --- | --- |
                | asset | 房地产 | crwu-audit-asset-realestate | available | load |
                """,
            )
            # Directory renamed, frontmatter kept: registry name and directory disagree.
            _create_leaf(repo, "crwu-audit-asset-realty", "02-资产类型/01-房地产/")
            _write(
                repo / "skills/crwu-audit-asset-realty/SKILL.md",
                "---\nname: crwu-audit-asset-realestate\ndescription: Use when selected.\n---\n",
            )

            report = json.loads(run_checker(repo, tree).stdout)

            self.assertIn("AVAILABLE_SKILL_DIRECTORY_MISSING", _codes(report))
            self.assertIn(
                "crwu-audit-asset-realestate",
                {i["skill"] for i in _findings(report, "SKILL_NAME_MISMATCH")},
            )
            self.assertIn("crwu-audit-asset-realty", {i["skill"] for i in _findings(report, "ORPHAN_SKILL")})

    def test_missing_required_reference_and_orphan_skill_are_reported(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "repo"
            tree = self._tree(root)
            _write(
                repo / "skills/crwu-audit/references/07-skill-registry.md",
                _registry("crwu-audit-asset-realestate", "crwu-audit-biz-asset-operation"),
            )
            _create_leaf(repo, "crwu-audit-asset-realestate", "02-资产类型/01-房地产/")
            _create_leaf(repo, "crwu-audit-biz-asset-operation", "01-业务路线/01-资产经营/")
            (repo / "skills/crwu-audit-asset-realestate/references/02-review-focus.md").unlink()
            _create_leaf(repo, "crwu-audit-asset-unregistered", "02-资产类型/02-未登记资产/")

            report = json.loads(run_checker(repo, tree).stdout)

            missing = _findings(report, "SKILL_REFERENCE_MISSING")
            self.assertEqual(["02-review-focus.md"], [Path(i["path"]).name for i in missing])
            self.assertIn(
                "crwu-audit-asset-unregistered",
                {i["skill"] for i in _findings(report, "ORPHAN_SKILL")},
            )

    def test_duplicate_and_unclassified_labels_are_reported(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "repo"
            tree = self._tree(root)
            _write(
                repo / "skills/crwu-audit/references/07-skill-registry.md",
                """
                | axis | label | skill | status | load behavior |
                | --- | --- | --- | --- | --- |
                | asset | 房地产 | crwu-audit-asset-realestate | available | load |
                | asset | 机器设备 | crwu-audit-asset-equipment | available | load |
                | asset | 机器设备 | crwu-audit-asset-equipment | available | load |
                | business | 资产经营 | crwu-audit-biz-asset-operation | available | load |
                """,
            )
            _create_leaf(repo, "crwu-audit-asset-realestate", "02-资产类型/01-房地产/")
            _create_leaf(repo, "crwu-audit-biz-asset-operation", "01-业务路线/01-资产经营/")
            _write(
                repo / "skills/crwu-audit/references/03-asset-classification.md",
                "| canonical 资产类型 | 目标技能 |\n| --- | --- |\n| 存货 | `crwu-audit-asset-inventory` |\n",
            )
            _write(
                repo / "skills/crwu-audit/references/04-business-classification.md",
                "| 一级业务 | 目标技能 |\n| --- | --- |\n| 计税 | `crwu-audit-biz-tax-history` |\n",
            )

            report = json.loads(run_checker(repo, tree).stdout)

            self.assertEqual(
                [("asset", "机器设备")],
                [(i["axis"], i["label"]) for i in _findings(report, "REGISTRY_LABEL_DUPLICATE")],
            )
            self.assertEqual(
                {("asset", "房地产"), ("business", "资产经营")},
                {(i["axis"], i["label"]) for i in _findings(report, "CLASSIFICATION_LABEL_MISSING")},
            )
            # The duplicated row is one claim, so its missing directory is reported once.
            self.assertEqual(
                ["crwu-audit-asset-equipment"],
                [i["skill"] for i in _findings(report, "AVAILABLE_SKILL_DIRECTORY_MISSING")],
            )

    def test_declared_root_absent_from_catalog_is_reported(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "repo"
            tree = self._tree(root)
            _write(
                repo / "skills/crwu-audit/references/07-skill-registry.md",
                _registry("crwu-audit-asset-realestate", "crwu-audit-biz-asset-operation"),
            )
            _create_leaf(repo, "crwu-audit-asset-realestate", "02-资产类型/09-已归档资产/")
            _create_leaf(repo, "crwu-audit-biz-asset-operation", "01-业务路线/01-资产经营/")

            report = json.loads(run_checker(repo, tree).stdout)

            self.assertEqual(
                ["02-资产类型/09-已归档资产/"],
                [i["path"] for i in _findings(report, "MAPPING_ROOT_NOT_IN_CATALOG")],
            )

    def test_axis_root_and_skill_prefix_mismatches_are_reported(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "repo"
            tree = self._tree(root)
            _write(
                repo / "skills/crwu-audit/references/07-skill-registry.md",
                """
                | axis | label | skill | status | load behavior |
                | --- | --- | --- | --- | --- |
                | asset | 房地产 | crwu-audit-asset-realestate | available | load |
                | business | 资产经营 | crwu-audit-asset-asset-operation | available | load |
                """,
            )
            _create_leaf(repo, "crwu-audit-asset-realestate", "01-业务路线/01-资产经营/")
            _create_leaf(repo, "crwu-audit-asset-asset-operation", "01-业务路线/01-资产经营/")

            report = json.loads(run_checker(repo, tree).stdout)

            self.assertEqual(
                ["01-业务路线/01-资产经营/"],
                [i["path"] for i in _findings(report, "AXIS_ROOT_MISMATCH")],
            )
            self.assertEqual(
                ["crwu-audit-asset-asset-operation"],
                [i["skill"] for i in _findings(report, "AXIS_PREFIX_MISMATCH")],
            )
            # The business root exists, so it is not reported as a stale mapping.
            self.assertEqual([], _findings(report, "MAPPING_ROOT_NOT_IN_CATALOG"))

    def test_partial_catalog_does_not_claim_roots_were_deleted(self):
        business_only = """
        - 📁 01-业务路线/
          - 📁 01-资产经营/
            - 📁 租赁与租金评估/
              - 📄 01-业务通用审核要点
        """
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "repo"
            tree = self._tree(root, business_only)
            _write(
                repo / "skills/crwu-audit/references/07-skill-registry.md",
                """
                | axis | label | skill | status | load behavior |
                | --- | --- | --- | --- | --- |
                | asset | 房地产 | crwu-audit-asset-realestate | available | load |
                | business | 资产经营 | crwu-audit-biz-asset-operation | available | load |
                """,
            )
            _create_leaf(repo, "crwu-audit-asset-realestate", "02-资产类型/01-房地产/")
            _create_leaf(repo, "crwu-audit-biz-asset-operation", "01-业务路线/01-资产经营/")

            report = json.loads(run_checker(repo, tree).stdout)

            self.assertEqual([], _findings(report, "MAPPING_ROOT_NOT_IN_CATALOG"))
            self.assertEqual([], _findings(report, "AXIS_ROOT_MISMATCH"))
            self.assertEqual([], _findings(report, "ASSEMBLY_FIRST_LEVEL_ROOT_MISSING"))

    def test_legacy_business_directory_is_reported_as_pending_migration(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "repo"
            tree = self._tree(root)
            _write(
                repo / "skills/crwu-audit/references/07-skill-registry.md",
                _registry("crwu-audit-asset-realestate", "crwu-audit-biz-asset-operation"),
            )
            _create_leaf(repo, "crwu-audit-asset-realestate", "02-资产类型/01-房地产/")
            _create_leaf(repo, "crwu-audit-biz-asset-operation", "01-业务路线/01-资产经营/")
            _create_leaf(repo, "crwu-audit-business-rent", "01-业务路线/02-租赁/")

            report = json.loads(run_checker(repo, tree).stdout)

            self.assertEqual(
                ["crwu-audit-business-rent"],
                [i["skill"] for i in _findings(report, "LEGACY_BUSINESS_PREFIX")],
            )

    def test_catalog_and_repository_paths_agree_across_input_formats(self):
        node_index = {
            "schema": "crwu.kb-dir-cache.nodeindex.v1",
            "by_path": {
                "01-业务路线/": ["b"],
                "01-业务路线/01-资产经营/": ["b1"],
                "01-业务路线/01-资产经营/租赁与租金评估/": ["b2"],
                "01-业务路线/01-资产经营/租赁与租金评估/01-业务通用审核要点": ["b3"],
                "02-资产类型/": ["a"],
                "02-资产类型/01-房地产/": ["a1"],
                "02-资产类型/01-房地产/01-共性参考/": ["a2"],
                "02-资产类型/01-房地产/01-共性参考/02-评估审核条目": ["a3"],
                "02-资产类型/01-房地产/02-细分对象/": ["a4"],
                "02-资产类型/01-房地产/02-细分对象/01-土地使用权/": ["a5"],
                "02-资产类型/01-房地产/02-细分对象/01-土地使用权/评估审核条目": ["a6"],
            },
        }
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "repo"
            tree = self._tree(root)
            index = root / "node-index.json"
            index.write_text(json.dumps(node_index, ensure_ascii=False), encoding="utf-8")
            _create_valid_repo(repo)

            tree_report = json.loads(run_checker(repo, tree, "--strict").stdout)
            index_report = json.loads(run_checker(repo, index, "--strict").stdout)

            self.assertEqual([], tree_report["findings"])
            self.assertEqual([], index_report["findings"])

    @_requires_skill_tree
    def test_maintainer_documents_treat_the_legacy_prefix_as_migration_only(self):
        offenders = []
        for document in sorted(MAINTAINER_SKILL.rglob("*.md")):
            for lineno, line in enumerate(document.read_text(encoding="utf-8").splitlines(), start=1):
                if "crwu-audit-business-" not in line:
                    continue
                if not any(word in line for word in ("遗留", "待迁移", "legacy", "deprecated")):
                    offenders.append(f"{document.name}:{lineno}")
        self.assertEqual([], offenders, "legacy prefix must only be described as pending migration")


    def test_legacy_combined_skill_directory_is_reported(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "repo"
            tree = self._tree(root)
            _write(
                repo / "skills/crwu-audit/references/07-skill-registry.md",
                _registry("crwu-audit-asset-realestate", "crwu-audit-biz-asset-operation"),
            )
            _create_valid_repo(repo)
            # Legacy combined asset x business skill left over from the pre-axis layout.
            _write(
                repo / "skills/crwu-audit-realestate-rent/SKILL.md",
                "---\nname: crwu-audit-realestate-rent\ndescription: Use when selected.\n---\n",
            )
            # Infrastructure skills are not axis leaves and must stay exempt.
            _write(
                repo / "skills/crwu-audit-datacheck/SKILL.md",
                "---\nname: crwu-audit-datacheck\ndescription: Use when tabular.\n---\n",
            )

            report = json.loads(run_checker(repo, tree).stdout)

            self.assertEqual(
                ["crwu-audit-realestate-rent"],
                [i["skill"] for i in _findings(report, "LEGACY_COMBINED_SKILL")],
            )
            self.assertNotIn(
                "crwu-audit-datacheck",
                {i["skill"] for i in report["findings"]},
            )

    def test_business_common_review_document_must_be_referenced(self):
        """A first-level business folder's 共同审核点 must be downloaded and referenced."""
        tree_with_common = """
        - 📁 01-业务路线/
          - 📁 01-资产经营/
            - 📄 共同审核点.md
            - 📁 租赁与租金评估/
              - 📄 01-业务通用审核要点
        """
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "repo"
            tree = self._tree(root, tree_with_common)
            _create_valid_repo(repo)

            report = json.loads(run_checker(repo, tree).stdout)

            self.assertEqual(
                ["资产经营"],
                [i["label"] for i in _findings(report, "BUSINESS_COMMON_REVIEW_NOT_REFERENCED")],
            )

    def test_business_common_review_reference_is_satisfied_by_either_reference(self):
        tree_with_common = """
        - 📁 01-业务路线/
          - 📁 01-资产经营/
            - 📄 01-共同审核点.md
            - 📁 租赁与租金评估/
              - 📄 01-业务通用审核要点
        """
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "repo"
            tree = self._tree(root, tree_with_common)
            _create_valid_repo(repo)
            _write(
                repo / "skills/crwu-audit-biz-asset-operation/references/02-review-focus.md",
                "# Review focus\n\n一级共用层：`01-业务路线/01-资产经营/共同审核点`。\n",
            )

            report = json.loads(run_checker(repo, tree).stdout)

            self.assertEqual([], _findings(report, "BUSINESS_COMMON_REVIEW_NOT_REFERENCED"))

    def test_absent_business_common_review_document_is_not_a_gap(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "repo"
            tree = self._tree(root)
            _create_valid_repo(repo)

            report = json.loads(run_checker(repo, tree).stdout)

            self.assertEqual([], _findings(report, "BUSINESS_COMMON_REVIEW_NOT_REFERENCED"))
            self.assertEqual([], report["findings"])

    def test_negative_common_review_claim_does_not_satisfy_the_reference(self):
        """Naming the document while denying it exists is not a reference.

        Regression for the field bug this check was written against: a leaf that still said
        "一级根未提供 `共同审核点`" mentioned the document, so a plain substring test passed
        while the shared review layer was in fact never referenced.
        """
        tree_with_common = """
        - 📁 01-业务路线/
          - 📁 01-资产经营/
            - 📄 共同审核点
            - 📁 租赁与租金评估/
              - 📄 01-业务通用审核要点
        """
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "repo"
            tree = self._tree(root, tree_with_common)
            _create_valid_repo(repo)
            _write(
                repo / "skills/crwu-audit-biz-asset-operation/references/02-review-focus.md",
                "# Review focus\n\n## 一级共用层\n\n"
                "- 路径：库内未提供（无此前缀路径）\n"
                "- 状态：一级根未提供 `共同审核点`（条件性约定，**不记缺口**）。\n",
            )

            report = json.loads(run_checker(repo, tree).stdout)

            self.assertEqual(
                ["资产经营"],
                [
                    i["label"]
                    for i in _findings(report, "BUSINESS_COMMON_REVIEW_NOT_REFERENCED")
                ],
            )

    def test_emitted_calibration_table_does_not_become_drift(self):
        """`--emit-map` writes its diagnostic table into a scanned file: it must stay idempotent.

        The table lists missing keys; backticking them there made the next run report the
        calibration file itself as drifted (and re-attributed another skill's drift to it).
        """
        tree = """
        - 📁 00-总纲/
          - 📁 治理/
            - 📄 标签词典
        - 📁 01-业务路线/
          - 📁 01-资产经营/
            - 📄 共同审核点
            - 📁 租赁与租金评估/
              - 📄 01-业务通用审核要点
        """
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "repo"
            tree_path = self._tree(root, tree)
            _create_valid_repo(repo)
            _write(
                repo / "skills/crwu-audit/references/00-input-and-route-profile.md",
                "# profile\n\n- 库内没有的键：`00-总纲/治理/术语对照总表`\n",
            )
            calibration = (
                repo
                / "skills/crwu-audit-skill-maintainer/references/07-kb-skill-map.md"
            )

            first = json.loads(
                run_checker(repo, tree_path, "--emit-map", str(calibration)).stdout
            )
            self.assertEqual(
                ["00-总纲/治理/术语对照总表"],
                [i["path"] for i in _findings(first, "KB_PATH_KEY_NOT_IN_CATALOG")],
            )
            self.assertIn("术语对照总表", calibration.read_text(encoding="utf-8"))

            second = json.loads(run_checker(repo, tree_path).stdout)

            self.assertEqual(
                [],
                [
                    i
                    for i in _findings(second, "KB_PATH_KEY_NOT_IN_CATALOG")
                    if str(calibration) in (i["source"] or "")
                ],
                "the emitted calibration table must not report itself as drift",
            )
            self.assertEqual(
                ["00-总纲/治理/术语对照总表"],
                [i["path"] for i in _findings(second, "KB_PATH_KEY_NOT_IN_CATALOG")],
            )

    def test_missing_router_entry_point_is_reported(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "repo"
            tree = self._tree(root)
            _write(
                repo / "skills/crwu-audit/references/07-skill-registry.md",
                _registry("crwu-audit-asset-realestate", "crwu-audit-biz-asset-operation"),
            )
            _create_leaf(repo, "crwu-audit-asset-realestate", "02-资产类型/01-房地产/")
            _create_leaf(repo, "crwu-audit-biz-asset-operation", "01-业务路线/01-资产经营/")

            report = json.loads(run_checker(repo, tree).stdout)

            self.assertIn("ROUTER_FILE_MISSING", _codes(report))

    def test_missing_and_unresolved_router_references_are_reported(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "repo"
            tree = self._tree(root)
            _create_valid_repo(repo)
            (repo / "skills/crwu-audit/references/05-method-classification.md").unlink()
            _write(
                repo / "skills/crwu-audit/SKILL.md",
                "# 总路由\n\n并集见 `08-union-dispatch-rules.md`，另见 `12-nonexistent.md`。\n",
            )

            report = json.loads(run_checker(repo, tree).stdout)

            self.assertEqual(
                ["05-method-classification.md"],
                [Path(i["path"]).name for i in _findings(report, "ROUTER_REFERENCE_MISSING")],
            )
            self.assertEqual(
                ["12-nonexistent.md"],
                [Path(i["path"]).name for i in _findings(report, "ROUTER_REFERENCE_UNRESOLVED")],
            )

    def test_axis_present_in_catalog_must_be_dispatched(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "repo"
            tree = self._tree(root)
            _create_valid_repo(repo)
            _write(
                repo / "skills/crwu-audit/references/08-union-dispatch-rules.md",
                "skills_to_load = stable_unique(asset_skills, method_skills, overlay_skills)\n",
            )

            report = json.loads(run_checker(repo, tree).stdout)

            self.assertEqual(
                ["business"],
                [i["axis"] for i in _findings(report, "ROUTER_AXIS_UNDISPATCHED")],
            )

    def test_routing_layer_must_not_name_unresolvable_skills(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "repo"
            tree = self._tree(root)
            _create_valid_repo(repo)
            _write(
                repo / "skills/crwu-audit/references/08-union-dispatch-rules.md",
                (
                    "# 稳定并集\n\n"
                    "skills_to_load = stable_unique(scope_skills, asset_skills, business_skills, "
                    "method_skills, overlay_skills, public_skills)\n\n"
                    "命中房地产时并入 crwu-audit-asset-realestate；"
                    "清算场景并入 crwu-audit-biz-liquidation。\n"
                    "通配写法 crwu-audit-asset-* 与占位 crwu-audit-<axis>-<label> 不算具体技能名。\n"
                ),
            )

            report = json.loads(run_checker(repo, tree).stdout)

            self.assertEqual(
                ["crwu-audit-biz-liquidation"],
                [i["skill"] for i in _findings(report, "ROUTER_SKILL_REFERENCE_UNRESOLVED")],
            )

    def test_stale_or_untimed_catalog_is_reported_when_freshness_is_required(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "repo"
            _create_valid_repo(repo)
            # Timestamped but old.
            stale = root / "node-index.json"
            stale.write_text(
                json.dumps(
                    {
                        "schema": "crwu.kb-node-index.v1",
                        "fetchedAt": "2020-01-01T00:00:00+08:00",
                        "nodes": {
                            "a": {"nodeId": "a", "name": "02-资产类型", "type": "folder", "path": "02-资产类型"}
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            # No capture time at all.
            untimed = root / "tree.md"
            untimed.write_text("- 📁 02-资产类型/\n  - 📁 01-房地产/\n", encoding="utf-8")

            fresh_report = json.loads(run_checker(repo, stale, "--max-age-hours", "1").stdout)
            untimed_report = json.loads(run_checker(repo, untimed, "--max-age-hours", "1").stdout)
            unchecked_report = json.loads(run_checker(repo, stale).stdout)

            self.assertIn("CATALOG_STALE", _codes(fresh_report))
            self.assertIn("CATALOG_NOT_LIVE", _codes(untimed_report))
            self.assertEqual([], _findings(unchecked_report, "CATALOG_STALE"))
            self.assertEqual([], _findings(unchecked_report, "CATALOG_NOT_LIVE"))

    @_requires_skill_tree
    def test_real_repository_routing_layer_is_consistent(self):
        """The live repo's router, references, registry and skill dirs must agree."""
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            catalog = root / "tree.md"
            catalog.write_text(COMPLETE_TREE, encoding="utf-8")

            report = json.loads(run_checker(REPO_ROOT, catalog).stdout)

            routing_codes = sorted(
                {
                    item["code"]
                    for item in report["findings"]
                    if item["code"].startswith("ROUTER_")
                }
            )
            self.assertEqual([], routing_codes)

    def test_emit_map_writes_and_preserves_calibration_document(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "repo"
            tree = self._tree(root)
            _create_valid_repo(repo)
            out = root / "map.md"

            first = run_checker(repo, tree, "--emit-map", str(out))
            self.assertEqual(0, first.returncode, first.stderr)
            text = out.read_text(encoding="utf-8")
            self.assertIn("知识库 ↔ Skill 映射校准表", text)
            self.assertIn("`02-资产类型/01-房地产/`", text)
            self.assertIn("`crwu-audit-asset-realestate`", text)
            self.assertIn("`01-业务路线/01-资产经营/`", text)
            self.assertIn("`crwu-audit-biz-asset-operation`", text)
            self.assertIn("CALIBRATION-HISTORY:BEGIN", text)

            # Hand-maintained notes must survive a re-run; history must gain exactly one row.
            # The first run's own row is dropped first: identical stamps are deduplicated, so
            # keeping it would make the expected row count depend on whether the two runs happen
            # to land in the same wall-clock second (a real flake this test used to have).
            begin = "<!-- CALIBRATION-HISTORY:BEGIN -->"
            finish = "<!-- CALIBRATION-HISTORY:END -->"
            before, rest = text.split(begin)
            history_block, after = rest.split(finish)
            kept = [l for l in history_block.splitlines() if not l.startswith("| 20")]
            text = before + begin + "\n" + "\n".join(kept).strip("\n") + "\n" + finish + after
            text = text.replace(
                "<!-- CALIBRATION-NOTES:BEGIN -->",
                "<!-- CALIBRATION-NOTES:BEGIN -->\n人工备注：必检项待补。",
            )
            text = text.replace(
                "<!-- CALIBRATION-HISTORY:END -->",
                "| 2020-01-01T00:00:00+08:00 | 2020-01-01T00:00:00+08:00 | 1 | 9 | 9 | 9 |\n<!-- CALIBRATION-HISTORY:END -->",
            )
            out.write_text(text, encoding="utf-8")
            second = run_checker(repo, tree, "--emit-map", str(out))
            self.assertEqual(0, second.returncode, second.stderr)
            refreshed = out.read_text(encoding="utf-8")
            self.assertIn("人工备注：必检项待补。", refreshed)
            history = refreshed.split("CALIBRATION-HISTORY:BEGIN")[1].split("CALIBRATION-HISTORY:END")[0]
            data_rows = [l for l in history.splitlines() if l.startswith("| 20")]
            # Older row preserved, exactly one new row appended, newest shown first.
            self.assertEqual(2, len(data_rows))
            self.assertIn("2020-01-01", data_rows[-1])
            self.assertNotIn("2020-01-01", data_rows[0])

    def test_calibration_flags_missing_common_layer_and_subroute_coverage(self):
        tree = """
        - 📁 01-业务路线/
          - 📁 01-资产经营/
            - 📄 共同审核点.md
            - 📁 持有价值管理/
              - 📄 01-业务通用审核要点
            - 📁 空子业务/
        """
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "repo"
            tree_path = self._tree(root, tree)
            _write(
                repo / "skills/crwu-audit/references/07-skill-registry.md",
                _registry("crwu-audit-asset-realestate", "crwu-audit-biz-asset-operation"),
            )
            _create_router(repo)
            _create_leaf(repo, "crwu-audit-biz-asset-operation", "01-业务路线/01-资产经营/")
            out = root / "map.md"

            run_checker(repo, tree_path, "--emit-map", str(out))
            text = out.read_text(encoding="utf-8")

            self.assertIn("2（1）", text, text)
            self.assertIn("缺：空子业务", text)
            self.assertIn("有", text)

    def test_library_path_keys_must_match_the_latest_catalog(self):
        """Address keys are checked for the whole audit family, not just first-level roots."""
        tree = """
        - 📁 00-总纲/
          - 📁 治理/
            - 📄 标签词典
        - 📁 01-业务路线/
          - 📁 01-资产经营/
            - 📄 01-业务通用审核要点
        - 📁 02-资产类型/
          - 📁 01-房地产/
            - 📁 01-共性参考/
              - 📄 02-评估审核条目
        """
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "repo"
            tree_path = self._tree(root, tree)
            _create_valid_repo(repo)
            _write(
                repo / "skills/crwu-audit/references/00-input-and-route-profile.md",
                textwrap.dedent(
                    """
                    # profile

                    - 词表：`00-总纲/治理/标签词典`
                    - 主语料：`01-业务路线/01-资产经营/`
                    - 库内没有的键：`00-总纲/治理/术语对照总表`
                    """
                ).lstrip(),
            )

            report = json.loads(run_checker(repo, tree_path).stdout)

            codes = _codes(report)
            self.assertIn("KB_PATH_KEY_NOT_IN_CATALOG", codes)
            self.assertEqual(
                ["00-总纲/治理/术语对照总表"],
                [i["path"] for i in _findings(report, "KB_PATH_KEY_NOT_IN_CATALOG")],
            )
            self.assertTrue(
                all(
                    i["path"].startswith("00-总纲/")
                    for i in _findings(report, "KB_PATH_KEY_NOT_IN_CATALOG")
                )
            )

    def test_export_suffix_and_folder_slash_drift_is_reported(self):
        tree = """
        - 📁 00-总纲/
          - 📁 治理/
            - 📄 标签词典
        - 📁 02-资产类型/
          - 📁 01-房地产/
            - 📁 01-共性参考/
              - 📄 02-评估审核条目
        """
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "repo"
            tree_path = self._tree(root, tree)
            _create_valid_repo(repo)
            _write(
                repo / "skills/crwu-audit/references/00-input-and-route-profile.md",
                textwrap.dedent(
                    """
                    # profile

                    - 旧库残留后缀：`00-总纲/治理/标签词典.md`
                    - 目录漏尾斜杠：`02-资产类型/01-房地产`
                    - 占位与省略号不算键：`00-总纲/治理/某文件`、`00-总纲/…`
                    """
                ).lstrip(),
            )

            report = json.loads(run_checker(repo, tree_path).stdout)

            self.assertEqual(
                ["00-总纲/治理/标签词典.md"],
                [i["path"] for i in _findings(report, "KB_PATH_KEY_HAS_EXPORT_SUFFIX")],
            )
            self.assertEqual(
                ["02-资产类型/01-房地产"],
                [i["path"] for i in _findings(report, "KB_PATH_KEY_FOLDER_NEEDS_SLASH")],
            )
            self.assertEqual([], _findings(report, "KB_PATH_KEY_NOT_IN_CATALOG"))

    def test_uncaptured_containers_are_not_judged(self):
        """A partial catalog must not make every out-of-scope key look like drift."""
        business_only = """
        - 📁 01-业务路线/
          - 📁 01-资产经营/
            - 📄 01-业务通用审核要点
        """
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "repo"
            tree_path = self._tree(root, business_only)
            _create_valid_repo(repo)
            _write(
                repo / "skills/crwu-audit/references/00-input-and-route-profile.md",
                "- 规则库：`06-规则库/02-通用准则-报告与披露/报告准则-精编条目/报告准则-总则与基本遵循`\n",
            )

            report = json.loads(run_checker(repo, tree_path).stdout)

            self.assertEqual([], _findings(report, "KB_PATH_KEY_NOT_IN_CATALOG"))

    @_requires_skill_tree
    def test_real_repository_library_path_keys_exist(self):
        """Regression: this repo's audit-family address keys must resolve in the live catalog.

        Reads the real `crwu-dws` directory cache; a hand-made probe snapshot is not accepted
        as evidence (that is what hid the authoritative-schema drift). A cache belonging to a
        different knowledge base is skipped, not reported as a skill drift.
        """
        for directory in _live_cache_dirs():
            catalog = directory / "目录快照.json"
            report = json.loads(run_checker(REPO_ROOT, catalog).stdout)
            if not _is_audit_family_catalog(tuple(report["catalog"]["paths"])):
                continue

            path_codes = sorted(
                {
                    item["code"]
                    for item in report["findings"]
                    if item["code"].startswith("KB_PATH_KEY")
                }
            )
            self.assertEqual([], path_codes, str(_findings(report, "KB_PATH_KEY_NOT_IN_CATALOG")))
            return
        self.skipTest("no live DWS cache for the audit knowledge base is available")

    @_requires_skill_tree
    def test_live_cache_artifact_forms_agree_on_the_same_tree(self):
        """Every artifact crwu-dws writes for one cache must parse to the same path set.

        Regression for the field-shape drift class: `目录快照.json` (flat + `parentFolderId`,
        snake_case capture time, top-level `complete`), `node-index.json` (camelCase `byPath`
        typed per entry) and `目录树.md` (slash/dash indented tree) must all yield one tree.
        """
        for directory in _live_cache_dirs():
            forms = [
                directory / name
                for name in LIVE_CATALOG_FORMS
                if (directory / name).is_file()
            ]
            if len(forms) < 2:
                continue
            parsed: dict[str, tuple[str, ...]] = {}
            for form in forms:
                report = json.loads(run_checker(REPO_ROOT, form).stdout)
                parsed[form.name] = tuple(report["catalog"]["paths"])
            if not _is_audit_family_catalog(parsed[forms[0].name]):
                continue

            self.assertEqual(
                1,
                len(set(parsed.values())),
                {name: len(paths) for name, paths in parsed.items()},
            )
            # The mandated freshness gate must also pass on the authoritative snapshot.
            live = forms[0]
            report = json.loads(run_checker(REPO_ROOT, live, "--max-age-hours", "24").stdout)
            self.assertNotIn("CATALOG_NOT_LIVE", _codes(report))
            return
        self.skipTest("no live DWS cache with multiple artifact forms is available")

    def test_real_dws_artifact_shapes_normalize_identically(self):
        """The three shapes crwu-dws actually emits must agree on the same knowledge tree."""
        markdown = """
        - 📁 01-业务路线/
          - 📁 01-资产经营/
            - 📁 租赁与租金评估/
              - 📄 01-业务通用审核要点
        - 📁 02-资产类型/
          - 📁 01-房地产/
            - 📁 01-共性参考/
              - 📄 02-评估审核条目
        """
        # Authoritative shape per crwu-dws/references/00-目录快照schema.md:
        # nested `children` + `parentFolderId`, completeness on `stats.complete`.
        # Business/asset names carry no `.md` — that is only the local export suffix.
        snapshot = {
            "schema": "crwu.kb-dir-snapshot.v1",
            "space": {"name": "space", "workspaceId": "ws"},
            "fetchedAt": "2026-09-09T14:54:05+08:00",
            "stats": {"total_nodes": 8, "folders": 6, "docs": 2, "max_depth": 3, "complete": True},
            "failures": [],
            "nodes": [
                {
                    "nodeId": "b", "name": "01-业务路线", "type": "folder",
                    "parentFolderId": None, "depth": 0,
                    "children": [
                        {
                            "nodeId": "b1", "name": "01-资产经营", "type": "folder",
                            "parentFolderId": "b", "depth": 1,
                            "children": [
                                {
                                    "nodeId": "b2", "name": "租赁与租金评估", "type": "folder",
                                    "parentFolderId": "b1", "depth": 2,
                                    "children": [
                                        {"nodeId": "b3", "name": "01-业务通用审核要点", "type": "adoc",
                                         "parentFolderId": "b2", "depth": 3, "children": []}
                                    ],
                                }
                            ],
                        }
                    ],
                },
                {
                    "nodeId": "a", "name": "02-资产类型", "type": "folder",
                    "parentFolderId": None, "depth": 0,
                    "children": [
                        {
                            "nodeId": "a1", "name": "01-房地产", "type": "folder",
                            "parentFolderId": "a", "depth": 1,
                            "children": [
                                {
                                    "nodeId": "a2", "name": "01-共性参考", "type": "folder",
                                    "parentFolderId": "a1", "depth": 2,
                                    "children": [
                                        {"nodeId": "a3", "name": "02-评估审核条目", "type": "adoc",
                                         "parentFolderId": "a2", "depth": 3, "children": []}
                                    ],
                                }
                            ],
                        }
                    ],
                },
            ],
        }
        flat = [("b", "01-业务路线", "folder", None), ("b1", "01-资产经营", "folder", "b"),
                ("b2", "租赁与租金评估", "folder", "b1"), ("b3", "01-业务通用审核要点", "adoc", "b2"),
                ("a", "02-资产类型", "folder", None), ("a1", "01-房地产", "folder", "a"),
                ("a2", "01-共性参考", "folder", "a1"), ("a3", "02-评估审核条目", "adoc", "a2")]
        paths = {
            "b": "01-业务路线",
            "b1": "01-业务路线/01-资产经营",
            "b2": "01-业务路线/01-资产经营/租赁与租金评估",
            "b3": "01-业务路线/01-资产经营/租赁与租金评估/01-业务通用审核要点",
            "a": "02-资产类型",
            "a1": "02-资产类型/01-房地产",
            "a2": "02-资产类型/01-房地产/01-共性参考",
            "a3": "02-资产类型/01-房地产/01-共性参考/02-评估审核条目",
        }
        node_index = {
            "schema": "crwu.kb-node-index.v1",
            "fetchedAt": "2026-09-09T14:54:05+08:00",
            "nodes": {
                nid: {"nodeId": nid, "name": name, "type": kind, "path": paths[nid]}
                for nid, name, kind, _parent in flat
            },
        }

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "repo"
            tree = self._tree(root, markdown)
            snapshot_file = root / "目录快照.json"
            index_file = root / "node-index.json"
            snapshot_file.write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")
            index_file.write_text(json.dumps(node_index, ensure_ascii=False), encoding="utf-8")
            _create_valid_repo(repo)

            reports = [
                json.loads(run_checker(repo, source, "--strict").stdout)
                for source in (tree, snapshot_file, index_file)
            ]

            self.assertEqual(
                reports[0]["catalog"]["paths"],
                reports[1]["catalog"]["paths"],
            )
            self.assertEqual(
                reports[0]["catalog"]["paths"],
                reports[2]["catalog"]["paths"],
            )
            self.assertEqual(8, len(reports[0]["catalog"]["paths"]))
            for report in reports:
                self.assertEqual([], report["findings"])
            self.assertEqual("crwu.kb-dir-snapshot.v1", reports[1]["catalog"]["source_schema"])
            self.assertEqual("crwu.kb-node-index.v1", reports[2]["catalog"]["source_schema"])
            self.assertIs(True, reports[1]["catalog"]["complete"])

    def test_legacy_flat_snapshot_uses_parent_folder_id_authoritatively(self):
        """The flat legacy form must link on `parentFolderId`, with `parentId` as alias only."""
        flat_nodes = [
            {"nodeId": "a", "name": "02-资产类型", "type": "folder", "parentFolderId": None},
            {"nodeId": "a1", "name": "01-房地产", "type": "folder", "parentFolderId": "a"},
            {"nodeId": "a2", "name": "01-共性参考", "type": "folder", "parentFolderId": "a1"},
            {"nodeId": "a3", "name": "02-评估审核条目", "type": "adoc", "parentFolderId": "a2"},
        ]
        alias_nodes = [
            {**node, "parentId": node["parentFolderId"]} for node in flat_nodes
        ]
        for key in ("parentFolderId",):
            for node in alias_nodes:
                node.pop(key, None)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "repo"
            _create_valid_repo(repo)
            for name, nodes in (("authoritative.json", flat_nodes), ("alias.json", alias_nodes)):
                catalog = root / name
                catalog.write_text(
                    json.dumps(
                        {
                            "schema": "crwu.kb-dir-snapshot.v1",
                            "fetchedAt": "2026-09-09T14:54:05+08:00",
                            "stats": {"total_nodes": len(nodes), "complete": True},
                            "failures": [],
                            "nodes": nodes,
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
                report = json.loads(run_checker(repo, catalog).stdout)
                self.assertEqual(
                    [
                        "02-资产类型/",
                        "02-资产类型/01-房地产/",
                        "02-资产类型/01-房地产/01-共性参考/",
                        "02-资产类型/01-房地产/01-共性参考/02-评估审核条目",
                    ],
                    report["catalog"]["paths"],
                    name,
                )

    def test_incomplete_dws_snapshot_is_reported_as_incomplete(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "repo"
            tree = self._tree(root)
            snapshot_file = root / "目录快照.json"
            snapshot_file.write_text(
                json.dumps(
                    {
                        "schema": "crwu.kb-dir-snapshot.v1",
                        "fetchedAt": "2026-09-09T14:54:05+08:00",
                        "stats": {"total_nodes": 1, "folders": 1, "docs": 0,
                                  "max_depth": 0, "complete": False},
                        "failures": [{"nodeId": "a", "step": "node-list", "error": "timeout"}],
                        "nodes": [{"nodeId": "a", "name": "02-资产类型", "type": "folder",
                                   "parentFolderId": None, "depth": 0, "children": []}],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            report = json.loads(run_checker(repo, snapshot_file).stdout)

            self.assertIs(False, report["catalog"]["complete"])
            self.assertEqual(["02-资产类型/"], report["catalog"]["paths"])


class CrwuDwsArtifactShapeTest(unittest.TestCase):
    """Every shape `crwu-dws` actually writes must load with the same 263-path-equivalent tree.

    Regression: the checker previously read only camelCase capture time (`fetchedAt`), only
    `stats.complete`, and inferred folder-ness from a trailing `/` on node-index keys. Real
    crwu-dws artifacts use `fetched_at` / top-level `complete` / `byPath` entries typed as
    `folder`, so a schema-conformant fixture passed while the live artifact was rejected.
    """

    def setUp(self):
        self.now = datetime.datetime.now(datetime.timezone.utc).astimezone().isoformat()

    def test_dir_snapshot_snake_case_time_and_top_level_complete(self):
        with tempfile.TemporaryDirectory() as temp:
            catalog = Path(temp) / "目录快照.json"
            catalog.write_text(
                json.dumps(
                    {
                        "schema": "crwu.kb-dir-snapshot.v1",
                        "fetched_at": self.now,
                        "complete": True,
                        "truncated": False,
                        "stats": {"total": 3, "folders": 2, "docs": 1, "maxDepth": 3},
                        "evidence": {"foldersVisited": 2, "pages": []},
                        "nodes": [
                            {"nodeId": "r", "name": "02-资产类型", "type": "folder", "parentFolderId": None},
                            {"nodeId": "c", "name": "01-房地产", "type": "folder", "parentFolderId": "r"},
                            {
                                "nodeId": "d",
                                "name": "02-评估审核条目",
                                "type": "file",
                                "parentFolderId": "c",
                            },
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            report = json.loads(run_checker(REPO_ROOT, catalog, "--max-age-hours", "1").stdout)

            self.assertEqual(
                ["02-资产类型/", "02-资产类型/01-房地产/", "02-资产类型/01-房地产/02-评估审核条目"],
                report["catalog"]["paths"],
            )
            self.assertIs(True, report["catalog"]["complete"])
            self.assertNotIn("CATALOG_NOT_LIVE", _codes(report))
            self.assertNotIn("CATALOG_STALE", _codes(report))

    def test_truncated_snapshot_is_incomplete(self):
        with tempfile.TemporaryDirectory() as temp:
            catalog = Path(temp) / "目录快照.json"
            catalog.write_text(
                json.dumps(
                    {
                        "schema": "crwu.kb-dir-snapshot.v1",
                        "fetched_at": self.now,
                        "complete": True,
                        "truncated": True,
                        "nodes": [{"nodeId": "r", "name": "02-资产类型", "type": "folder"}],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            report = json.loads(run_checker(REPO_ROOT, catalog).stdout)

            self.assertIs(False, report["catalog"]["complete"])

    def test_node_index_by_path_uses_entry_type_for_folder_ness(self):
        with tempfile.TemporaryDirectory() as temp:
            catalog = Path(temp) / "node-index.json"
            catalog.write_text(
                json.dumps(
                    {
                        "schema": "crwu.kb-node-index.v1",
                        "fetched_at": self.now,
                        "byNodeId": {},
                        "byPath": {
                            "02-资产类型": {"nodeId": "r", "type": "folder", "depth": 1},
                            "02-资产类型/01-房地产": {"nodeId": "c", "type": "folder", "depth": 2},
                            "02-资产类型/01-房地产/02-评估审核条目": {
                                "nodeId": "d",
                                "type": "file",
                                "depth": 3,
                            },
                        },
                        "byName": {},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            report = json.loads(run_checker(REPO_ROOT, catalog, "--max-age-hours", "1").stdout)

            self.assertEqual(
                ["02-资产类型/", "02-资产类型/01-房地产/", "02-资产类型/01-房地产/02-评估审核条目"],
                report["catalog"]["paths"],
            )
            self.assertNotIn("CATALOG_NOT_LIVE", _codes(report))
            # A folder key written without a trailing slash must not become a file.
            self.assertEqual([], _findings(report, "KB_PATH_KEY_HAS_EXPORT_SUFFIX"))

    def test_slash_form_directory_tree_is_parsed(self):
        with tempfile.TemporaryDirectory() as temp:
            catalog = Path(temp) / "目录树.md"
            catalog.write_text(
                textwrap.dedent(
                    f"""\
                    # 中瑞世联评估审核知识库 · 目录树

                    - fetched_at: {self.now}
                    - workspaceId: dN0G7aREV8l6MXWY
                    - 节点 3（folder 2 / doc 1）· 最大深度 3

                    / 02-资产类型
                      / 01-房地产
                        - 02-评估审核条目
                    """
                ),
                encoding="utf-8",
            )

            report = json.loads(run_checker(REPO_ROOT, catalog, "--max-age-hours", "1").stdout)

            self.assertEqual(
                ["02-资产类型/", "02-资产类型/01-房地产/", "02-资产类型/01-房地产/02-评估审核条目"],
                report["catalog"]["paths"],
            )
            self.assertNotIn("CATALOG_NOT_LIVE", _codes(report))


PUBLIC_AXIS_TREE = """
- 📁 01-业务路线/
  - 📁 01-资产经营/
    - 📁 租赁与租金评估/
      - 📄 01-业务通用审核要点
- 📁 02-资产类型/
  - 📁 01-房地产/
    - 📁 01-共性参考/
      - 📄 02-评估审核条目
- 📁 06-规则库/
  - 📁 02-通用准则-报告与披露/
    - 📁 报告准则-精编条目/
      - 📄 报告准则-总则与基本遵循
  - 📁 03-通用准则-程序与档案/
    - 📁 程序准则2026-精编条目/
      - 📄 程序准则2026-第一章总则与第二章基本遵循
""".strip()


def _registry_with_public(public_skill: str, public_status: str = "available") -> str:
    return f"""
    # 多轴技能注册表

    | axis | label | skill | status | load behavior |
    | --- | --- | --- | --- | --- |
    | asset | 房地产 | crwu-audit-asset-realestate | available | load |
    | business | 资产经营 | crwu-audit-biz-asset-operation | available | load |
    | public | 通用准则 | {public_skill} | {public_status} | load always |
    """


def _create_public_skill(repo: Path, name: str, roots, *, frontmatter=None) -> None:
    """Public-axis capability fixture: one entry plus the two standard references.

    Kept Python 3.9 compatible on purpose (this module has no `from __future__ import
    annotations`), so no PEP 604 unions in the signature.
    """
    skill = repo / "skills" / name
    _write(
        skill / "SKILL.md",
        f"""
        ---
        name: {frontmatter or name}
        description: Use when crwu-audit selects the public capability.
        ---

        # {name}
        """,
    )
    _write(skill / "references" / "00-applicability.md", "# Applicability\n")
    root_rows = "\n        ".join(
        f"| KEY{i} | public | 通用准则 | `{root}` | directory | true | true |"
        for i, root in enumerate(roots)
    )
    _write(
        skill / "references" / "01-kb-assembly.md",
        f"""
        # KB assembly

        | source_key | owner_axis | canonical_label | kb_root | request_kind | recursive | required |
        | --- | --- | --- | --- | --- | --- | --- |
        {root_rows}
        """,
    )
    _write(skill / "references" / "02-review-focus.md", "# Review focus\n")


class PublicAxisMappingTest(unittest.TestCase):
    """Public-axis capabilities sit outside the asset/business first-level-root model.

    Regression guard: `audit_rows` filters registry rows by `AXIS_ROOTS`, so before this
    coverage existed an `available` public skill could be missing entirely, or ship without
    its references, and no mapping finding would fire.
    """

    PUBLIC_SKILL = "crwu-audit-public-general-standards"
    PUBLIC_ROOTS = ("06-规则库/02-通用准则-报告与披露/", "06-规则库/03-通用准则-程序与档案/")

    def _repo_with_public_row(self, root: Path) -> Path:
        repo = root / "repo"
        _create_valid_repo(repo)
        _write(
            repo / "skills/crwu-audit/references/07-skill-registry.md",
            _registry_with_public(self.PUBLIC_SKILL),
        )
        return repo

    def _tree(self, root: Path) -> Path:
        tree = root / "tree.md"
        tree.write_text(PUBLIC_AXIS_TREE, encoding="utf-8")
        return tree

    def test_available_public_skill_directory_missing_is_reported(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = self._repo_with_public_row(root)
            tree = self._tree(root)

            report = json.loads(run_checker(repo, tree).stdout)

            self.assertEqual(
                [self.PUBLIC_SKILL],
                [item["skill"] for item in _findings(report, "AVAILABLE_SKILL_DIRECTORY_MISSING")],
            )

    def test_available_public_skill_requires_a_kb_assembly_table(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = self._repo_with_public_row(root)
            tree = self._tree(root)
            skill = repo / "skills" / self.PUBLIC_SKILL
            _write(
                skill / "SKILL.md",
                f"---\nname: {self.PUBLIC_SKILL}\ndescription: public\n---\n\n# entry\n",
            )
            _write(skill / "references" / "00-applicability.md", "# Applicability\n")

            report = json.loads(run_checker(repo, tree).stdout)

            self.assertNotIn("AVAILABLE_SKILL_DIRECTORY_MISSING", _codes(report))
            self.assertEqual(
                [self.PUBLIC_SKILL],
                [item["skill"] for item in _findings(report, "SKILL_REFERENCE_MISSING")],
            )

    def test_public_skill_cross_cutting_assembly_table_name_is_accepted(self):
        """`crwu-audit-datacheck` ships `00-KB装配表.md`; that naming must not be an error."""
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = self._repo_with_public_row(root)
            tree = self._tree(root)
            skill = repo / "skills" / self.PUBLIC_SKILL
            _write(
                skill / "SKILL.md",
                f"---\nname: {self.PUBLIC_SKILL}\ndescription: public\n---\n\n# entry\n",
            )
            _write(
                skill / "references" / "00-KB装配表.md",
                "| 需要 | 库内层级路径 |\n| --- | --- |\n"
                "| 规则 | `06-规则库/02-通用准则-报告与披露/` |\n",
            )

            report = json.loads(run_checker(repo, tree).stdout)

            self.assertEqual(
                set(),
                _codes(report) & {"SKILL_REFERENCE_MISSING", "AVAILABLE_SKILL_DIRECTORY_MISSING"},
            )

    def test_public_skill_frontmatter_mismatch_is_reported(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = self._repo_with_public_row(root)
            tree = self._tree(root)
            _create_public_skill(
                repo,
                self.PUBLIC_SKILL,
                self.PUBLIC_ROOTS,
                frontmatter="crwu-audit-public-something-else",
            )

            report = json.loads(run_checker(repo, tree).stdout)

            mismatches = _findings(report, "SKILL_NAME_MISMATCH")
            self.assertEqual([self.PUBLIC_SKILL], [item["skill"] for item in mismatches])

    def test_public_skill_multi_root_assembly_is_not_forced_into_the_axis_root_model(self):
        """Public assembly keys live under `06-规则库/`；no `02-资产类型/`-style root applies."""
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = self._repo_with_public_row(root)
            tree = self._tree(root)
            _create_public_skill(repo, self.PUBLIC_SKILL, self.PUBLIC_ROOTS)

            report = json.loads(run_checker(repo, tree).stdout)

            self.assertEqual(
                set(),
                _codes(report)
                & {
                    "ASSEMBLY_FIRST_LEVEL_ROOT_MISSING",
                    "ASSEMBLY_FILE_MAPPING",
                    "AXIS_ROOT_MISMATCH",
                    "AXIS_PREFIX_MISMATCH",
                    "MAPPING_ROOT_NOT_IN_CATALOG",
                    "REGISTRY_LABEL_NOT_IN_CATALOG",
                },
            )

    def test_public_skill_path_keys_are_checked_against_the_catalog(self):
        """`inspect_path_keys` walks every crwu-audit* directory, public axis included."""
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = self._repo_with_public_row(root)
            tree = self._tree(root)
            _create_public_skill(
                repo,
                self.PUBLIC_SKILL,
                self.PUBLIC_ROOTS + ("06-规则库/99-未收录目录/",),
            )

            report = json.loads(run_checker(repo, tree).stdout)

            self.assertEqual(
                ["06-规则库/99-未收录目录/"],
                [
                    item["path"]
                    for item in _findings(report, "KB_PATH_KEY_NOT_IN_CATALOG")
                ],
            )


if __name__ == "__main__":
    unittest.main()
