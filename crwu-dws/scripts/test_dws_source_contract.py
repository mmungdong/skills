from pathlib import Path
import glob
import unittest


# 源仓契约测试：据本文件位置上溯定位 skills 根与源仓根（不硬编码仓库布局）。
# 运行时不需要本测试；已安装副本内缺少同级技能或源仓文档时显式 skip（不静默通过）。
SKILLS_ROOT = Path(__file__).resolve().parents[2]  # skills/<skill>/scripts/<file> → skills 根
REPO_ROOT = SKILLS_ROOT.parent                     # 源仓根

# Active contracts that must never re-introduce a local knowledge-base root,
# a downloaded-body mirror, or a "publish gate" style local fallback.
# Router/DWS-side documents that are individually pinned.
PINNED_CONTRACT_FILES = [
    "README.md",
    "crwu-dws/SKILL.md",
    "crwu-dws/references/00-目录快照schema.md",
    "crwu-dws/references/01-审核下载与manifest规范.md",
    "crwu-dws/references/02-缓存与兜底查找规范.md",
    "crwu-audit/SKILL.md",
    "crwu-audit/references/10-capability-gap-proposal.md",
    "crwu-audit/references/99-maintenance.md",
    "crwu-audit/references/04-business-classification.md",
    "crwu-audit/references/12-leaf-common-contract.md",
    "crwu-audit-asset-realestate/SKILL.md",
    "crwu-audit-asset-realestate/references/01-kb-assembly.md",
    "crwu-audit-biz-asset-operation/SKILL.md",
    "crwu-audit-biz-asset-operation/references/02-review-focus.md",
    # Public-axis capabilities are not matched by _leaf_files() (which enumerates only
    # crwu-audit-asset-* / crwu-audit-biz-*), so they must be pinned explicitly or the
    # whole public axis would go unchecked.
    "crwu-audit-public-general-standards/SKILL.md",
    "crwu-audit-public-general-standards/references/00-applicability.md",
    "crwu-audit-public-general-standards/references/01-kb-assembly.md",
    "crwu-audit-public-general-standards/references/02-review-focus.md",
    "crwu-audit-datacheck/SKILL.md",
    "crwu-audit-optimize/SKILL.md",
    "crwu-audit-optimize/references/00-优化规范与文件落点.md",
    "crwu-audit-optimize/references/01-反馈定位与画像流程.md",
    "crwu-audit-skill-maintainer/SKILL.md",
    "crwu-audit-skill-maintainer/references/01-kb-source-discovery.md",
    "crwu-audit-skill-maintainer/references/02-child-skill-contract.md",
]
# 源仓文档（不在 skills 内）：只有源仓维护环境存在；已安装副本内缺失 → 相关断言 skip。
PINNED_SOURCE_REPO_FILES = [
    "docs/design-audit-live-kb-protocol.md",
    "docs/design-crwu-dws.md",
]


def _display(path: Path) -> str:
    """给断言消息用的短路径：技能内相对 skills 根，源仓文档相对源仓根。"""
    for root in (SKILLS_ROOT, REPO_ROOT):
        try:
            return str(path.relative_to(root))
        except ValueError:
            continue
    return str(path)


def _source_repo_docs() -> list[Path]:
    return [REPO_ROOT / rel for rel in PINNED_SOURCE_REPO_FILES if (REPO_ROOT / rel).is_file()]


def _leaf_files():
    """Every file of every asset/biz leaf, so the whole family is covered (not a sample)."""
    found = []
    for pattern in ("crwu-audit-asset-*", "crwu-audit-biz-*"):
        for leaf in sorted(SKILLS_ROOT.glob(pattern)):
            if leaf.is_dir():
                found.extend(sorted(leaf.rglob("*.md")))
    return found


ACTIVE_CONTRACT_FILES = [SKILLS_ROOT / rel for rel in PINNED_CONTRACT_FILES] + _leaf_files()
SOURCE_REPO_CONTRACT_FILES = _source_repo_docs()

FORBIDDEN_TERMS = [
    "CRWU_KB_ROOT",
    "M2-B",
    "全量镜像",
    "本地静态副本",
    "本地静态根",
    "维护/离线归档",
]

# A contract still has to be able to *document* a retirement ("CRWU_KB_ROOT 已废止").
# Only lines that present the term as a usable source are violations.
RETIREMENT_NOTE_WORDS = (
    "废止", "弃用", "废弃", "不再", "禁止", "不得", "红线", "三不写",
    "字面", "lint", "协议", "硬编码", "旧树", "retired", "deprecated",
)


def _is_retirement_note(line):
    return any(word in line for word in RETIREMENT_NOTE_WORDS)



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


class DwsSourceContractTest(unittest.TestCase):
    def test_source_repo_docs_are_optional_outside_the_source_repo(self):
        """源仓文档（docs/）在已安装副本内不存在：显式 skip，不静默通过也不误报失败。"""
        if (REPO_ROOT / "docs").is_dir():
            self.assertEqual(
                len(PINNED_SOURCE_REPO_FILES),
                len(SOURCE_REPO_CONTRACT_FILES),
                "源仓环境下设计文档必须齐备",
            )
        else:
            self.skipTest("非源仓环境（无 docs/）：跳过源仓文档契约检查")

    @_requires_skill_tree
    def test_every_active_contract_file_exists(self):
        missing = [str(path) for path in ACTIVE_CONTRACT_FILES if not path.is_file()]

        self.assertEqual([], missing, f"active contract list points at missing files: {missing}")

    @_requires_skill_tree
    def test_active_contracts_do_not_offer_local_or_full_mirror_bodies(self):
        violations = []

        for contract_path in ACTIVE_CONTRACT_FILES + SOURCE_REPO_CONTRACT_FILES:
            relative_path = _display(contract_path)
            text = contract_path.read_text(encoding="utf-8")
            for lineno, line in enumerate(text.splitlines(), start=1):
                for term in FORBIDDEN_TERMS:
                    if term not in line:
                        continue
                    if _is_retirement_note(line):
                        continue
                    violations.append(f"{relative_path}:{lineno}: {term}")

        self.assertEqual([], violations, "\n".join(violations))

    @_requires_skill_tree
    def test_active_contracts_do_not_reference_a_local_kb_root_relative_path(self):
        """`KB/<rel>` addressed the retired local root; kb_tool owns the precise rule.

        `kb_tool.py validate --skill-root skills` distinguishes real `KB/<rel>` references
        from prose such as 『KB/知识库』 and from prohibition notes. Re-implementing a cruder
        text match here only produced false positives, so this test asserts the tool's
        verdict on the repository instead of scanning the text itself.
        """
        import subprocess
        import sys

        result = subprocess.run(
            [
                sys.executable,
                str(SKILLS_ROOT / "crwu-audit-skill-maintainer/scripts/kb_tool.py"),
                "validate",
                "--skill-root",
                str(SKILLS_ROOT),
            ],
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(
            0,
            result.returncode,
            f"kb_tool validate reported reference violations:\n{result.stdout}{result.stderr}",
        )

    @_requires_skill_tree
    def test_m2_supports_file_directory_and_mixed_manifest_entries(self):
        text = (SKILLS_ROOT / "crwu-dws/SKILL.md").read_text(encoding="utf-8")
        required_terms = [
            "单文件路径",
            "只下载该文件",
            "目录路径",
            "递归下载",
            "同一清单",
            "清单外零下载",
        ]

        for term in required_terms:
            with self.subTest(term=term):
                self.assertIn(term, text)

    # ---- v0.6：按 extension 分流的双取数通道 ----------------------------------
    #
    # 缺陷背景（2026-09-15 实测）：知识库文档的 nodeType 恒为 `file`，格式只在
    # `extension` 里；`dw. doc +export` 仅支持 `extension=adoc`。整改前 M2 对所有
    # 文档一律调用 `doc +export`，于是 25 个原生 `.md` 正文（整个 `03-评估方法/`）
    # 每次都必然失败、被记成 failure，且没有任何门禁发现——因为校验只看"路径键
    # 是否存在"，不看节点类型。以下断言把整改口径钉死。

    def _dws_docs(self) -> dict:
        names = [
            "SKILL.md",
            "references/00-目录快照schema.md",
            "references/01-审核下载与manifest规范.md",
            "references/02-缓存与兜底查找规范.md",
        ]
        return {
            name: (SKILLS_ROOT / "crwu-dws" / name).read_text(encoding="utf-8")
            for name in names
        }

    @_requires_skill_tree
    def test_whitelist_adds_read_only_drive_download(self):
        """候选通道必须显式列入只读白名单，且仍禁止一切写命令。"""
        text = self._dws_docs()["SKILL.md"]

        self.assertIn("`+download`", text, "drive +download 未进入只读白名单")
        self.assertIn("drive 域仅", text, "白名单未声明 drive 域边界")
        # 白名单必须保持"仅"的排他语义：drive 域只放行 +download 一个命令。
        drive_clause = next(
            line for line in text.splitlines() if "drive 域仅" in line
        )
        self.assertIn("+download", drive_clause)
        self.assertNotIn("+upload", drive_clause)
        self.assertNotIn("+move", drive_clause)
        self.assertNotIn("+delete", drive_clause)

    @_requires_skill_tree
    def test_channel_is_decided_by_extension_not_by_trial(self):
        """通道由 extension 判定；明令禁止"先 export 试失败再换通道"的试错取数。"""
        docs = self._dws_docs()
        skill = docs["SKILL.md"]

        # SKILL.md 必须给出分流表的三档判据。
        for term in ("`adoc`", "`md`", "`txt`", "`skipped`"):
            with self.subTest(term=term):
                self.assertIn(term, skill)

        # 试错取数必须被显式禁止（否则"必然失败"会被记成偶发 failure）。
        self.assertIn("试错", skill, "SKILL.md 未禁止试错式取数")
        self.assertRegex(
            skill,
            r"禁止[^\n]*试(错|一次)",
            "SKILL.md 未写明禁止试错式通道选择",
        )

        # references/01 必须给出同一张分流表与展开范围口径。
        m2 = docs["references/01-审核下载与manifest规范.md"]
        self.assertIn("dws drive +download", m2)
        self.assertIn("dws doc +export", m2)
        self.assertIn("channel", m2)

    @_requires_skill_tree
    def test_unsupported_extension_is_skipped_not_failed(self):
        """类型不支持是正常结论：必须记 skipped，禁止并入 failure。"""
        docs = self._dws_docs()
        skill = docs["SKILL.md"]
        m2 = docs["references/01-审核下载与manifest规范.md"]

        self.assertIn("skipped", skill)
        self.assertRegex(
            skill,
            r"skipped[^\n]*不(得|是)[^\n]*failure|不(得|是)[^\n]*failure[^\n]*skipped",
            "SKILL.md 未写明 skipped 不得计入 failure",
        )
        # 摘要口径必须把跳过与失败分开统计。
        self.assertIn("跳过", skill)
        self.assertIn("skipped", m2)
        self.assertRegex(
            m2,
            r"(不得|禁止)[^\n]*failure",
            "references/01 未写明 skipped 不得记为 failure",
        )
        # 明细表三态齐全：entry / skipped / failure。
        for kind in ('"kind": "entry"', '"kind": "skipped"', '"kind": "failure"'):
            with self.subTest(kind=kind):
                self.assertIn(kind, m2)

    @_requires_skill_tree
    def test_snapshot_and_node_index_carry_the_channel_discriminator(self):
        """extension/contentType 必须落快照与索引，否则 M2 快路径无法判通道。"""
        docs = self._dws_docs()
        snapshot = docs["references/00-目录快照schema.md"]
        index = docs["references/02-缓存与兜底查找规范.md"]

        for label, text in (("references/00", snapshot), ("references/02", index)):
            with self.subTest(doc=label):
                self.assertIn("extension", text, f"{label} 未记录 extension")
                self.assertIn("contentType", text, f"{label} 未记录 contentType")

        # 必须写明"缺失时补查 node-get、不按名称后缀猜"。
        self.assertIn("node-get", index, "references/02 未给出 extension 缺失时的补查口径")
        self.assertRegex(
            snapshot + index,
            r"不(推断|猜|按名称)",
            "未写明 extension 缺失时不得推断/猜测",
        )

    @_requires_skill_tree
    def test_type_field_is_not_used_as_a_format_discriminator(self):
        """nodeType 恒为 file，不得再当格式判据（整改前的错误假设）。"""
        snapshot = self._dws_docs()["references/00-目录快照schema.md"]

        self.assertRegex(
            snapshot,
            r"type[^\n]*(不承载格式|只表示节点形态)",
            "references/00 未写明 type 不承载格式信息",
        )
        # 渲染规则也必须按 extension 标注，而不是按 type。
        self.assertIn("ext:", snapshot, "目录树渲染未按 extension 标注")

    @_requires_skill_tree
    def test_asset_and_business_leaves_declare_a_first_level_directory_root(self):
        """Every asset/biz leaf must declare one exact recursive first-level root.

        Parses the assembly table row (cell-level) rather than substring matching, and the
        leaf must carry all four required references (not just the assembly table).
        """
        leaves = sorted(
            leaf for pattern in ("crwu-audit-asset-*", "crwu-audit-biz-*")
            for leaf in SKILLS_ROOT.glob(pattern) if leaf.is_dir()
        )
        self.assertNotEqual([], leaves, "expected at least one asset/biz leaf skill")

        required_references = (
            "00-applicability.md",
            "01-kb-assembly.md",
            "02-review-focus.md",
        )
        problems = []
        for leaf in leaves:
            name = leaf.name
            axis_root = "02-资产类型/" if name.startswith("crwu-audit-asset-") else "01-业务路线/"
            for reference in required_references:
                if not (leaf / "references" / reference).is_file():
                    problems.append(f"{name}: missing references/{reference}")
            assembly = leaf / "references" / "01-kb-assembly.md"
            if not assembly.is_file():
                continue

            rows = [
                [cell.strip().strip("`") for cell in line.strip().strip("|").split("|")]
                for line in assembly.read_text(encoding="utf-8").splitlines()
                if line.strip().startswith("|")
            ]
            header = next((r for r in rows if "kb_root" in r and "request_kind" in r), None)
            if header is None:
                problems.append(f"{name}: assembly has no first-level root table")
                continue
            index = {key: i for i, key in enumerate(header)}
            data = [
                r for r in rows
                if len(r) == len(header) and r[index["request_kind"]] in {"directory"}
            ]
            if len(data) != 1:
                problems.append(
                    f"{name}: expected exactly one directory root row, found {len(data)}"
                )
                continue
            row = data[0]
            kb_root = row[index["kb_root"]]
            label = row[index["canonical_label"]]
            if not kb_root.startswith(axis_root) or not kb_root.endswith("/"):
                problems.append(f"{name}: kb_root {kb_root!r} is not one {axis_root}<label>/ root")
            if kb_root.count("/") != 2:
                problems.append(f"{name}: kb_root {kb_root!r} is not a first-level root")
            if row[index["recursive"]] != "true":
                problems.append(f"{name}: recursive must be true")
            if row[index["required"]] != "true":
                problems.append(f"{name}: required must be true")
            if label not in kb_root:
                problems.append(f"{name}: canonical_label {label!r} not present in kb_root")
            if ".md" in kb_root:
                problems.append(f"{name}: kb_root must not carry the .md export suffix")

        self.assertEqual([], problems, "\n".join(problems))

    @_requires_skill_tree
    def test_legacy_combined_and_business_prefixed_skills_are_gone(self):
        offenders = sorted(
            path.name
            for pattern in ("crwu-audit-business-*",)
            for path in SKILLS_ROOT.glob(pattern)
            if path.is_dir()
        )
        self.assertEqual(
            [],
            offenders,
            f"legacy business-prefixed skill directories remain: {offenders}",
        )
        self.assertFalse(
            (SKILLS_ROOT / "crwu-audit-realestate-rent").exists(),
            "legacy combined skill crwu-audit-realestate-rent must stay deleted",
        )


if __name__ == "__main__":
    unittest.main()
