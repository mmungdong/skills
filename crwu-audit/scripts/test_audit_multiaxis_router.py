from pathlib import Path
import re
import unittest


# 源仓契约测试：据本文件位置上溯定位 skills 根（不硬编码仓库布局）。
# 运行时不需要本测试；已安装的技能副本内缺少同级技能时会显式 skip。
SKILLS_ROOT = Path(__file__).resolve().parents[2]  # skills/<skill>/scripts/<file> → skills 根
REPO_ROOT = SKILLS_ROOT.parent                     # 源仓根（仅用于相对路径展示）
AUDIT_SKILL_ROOT = SKILLS_ROOT / "crwu-audit"

EXPECTED_REFERENCE_FILES = (
    "00-input-and-route-profile.md",
    "01-report-id-resolution.md",
    "02-scope-classification.md",
    "03-asset-classification.md",
    "04-business-classification.md",
    "05-method-classification.md",
    "06-overlay-classification.md",
    "07-skill-registry.md",
    "08-union-dispatch-rules.md",
    "09-review-risk-classification.md",
    "10-capability-gap-proposal.md",
    "11-html-delivery-spec.md",
    "12-leaf-common-contract.md",
    "99-maintenance.md",
)

REQUIRED_ROUTER_TERMS = (
    "SeqNo",
    "ObjectId",
    "scope_types[]",
    "asset_types[]",
    "business_types[]",
    "methods[]",
    "overlays[]",
    "review_risk_class",
    "materiality",
    "skills_to_load",
    "02-scope-classification.md",
    "03-asset-classification.md",
    "04-business-classification.md",
    "05-method-classification.md",
    "06-overlay-classification.md",
    "07-skill-registry.md",
    "08-union-dispatch-rules.md",
)

REGISTRY_HEADER = ("axis", "label", "skill", "status", "load behavior")

# Stable rows only: business-axis names are mid-migration to crwu-audit-biz-* and
# are reported by the skill-maintainer mapping checker instead of being pinned here.
EXPECTED_REGISTRY_ROWS = (
    ("asset", "房地产", "crwu-audit-asset-realestate", "available", "load"),
    ("asset", "设备", "crwu-audit-asset-equipment", "pending", "record gap"),
    ("public", "通用准则", "crwu-audit-public-general-standards", "available", "load always"),
)

# Public-axis capabilities are report-shape independent. Every one of them must be
# reachable from the union algorithm without depending on any professional axis label.
UNCONDITIONAL_PUBLIC_SKILLS = ("crwu-audit-public-general-standards",)

DISPATCH_AXES = ("scope", "asset", "business", "method", "overlay", "public")

LEGACY_REGISTRY_SKILL = "crwu-audit-realestate-rent"
LEGACY_BUSINESS_PREFIX = "crwu-audit-business-"


def _markdown_cells(line):
    stripped = line.strip()
    if "|" not in stripped:
        return None
    cells = []
    for raw_cell in stripped.strip("|").split("|"):
        cell = raw_cell.strip()
        inline_code = re.fullmatch(r"`([^`]*)`", cell)
        if inline_code:
            cell = inline_code.group(1).strip()
        cells.append(cell.casefold())
    return tuple(cells)


def _is_markdown_separator(cells):
    return all(re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in cells)


def _registry_data_rows(text):
    lines = text.splitlines()
    for header_index, line in enumerate(lines):
        if _markdown_cells(line) != REGISTRY_HEADER:
            continue

        rows = []
        for candidate in lines[header_index + 1 :]:
            cells = _markdown_cells(candidate)
            if cells is None:
                if rows:
                    break
                continue
            if len(cells) != len(REGISTRY_HEADER):
                break
            if _is_markdown_separator(cells):
                continue
            rows.append(cells)
        return rows
    return None



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


class AuditMultiaxisRouterContractTest(unittest.TestCase):
    def test_multiaxis_router_reference_set_exists(self):
        references_root = AUDIT_SKILL_ROOT / "references"
        expected = set(EXPECTED_REFERENCE_FILES)
        actual = {path.name for path in references_root.glob("*.md")}
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)

        self.assertEqual(
            expected,
            actual,
            f"multiaxis router reference set mismatch: missing={missing}, extra={extra}",
        )

    def test_root_router_declares_multiaxis_profile_and_reference_set(self):
        router_path = AUDIT_SKILL_ROOT / "SKILL.md"
        self.assertTrue(router_path.is_file(), f"missing root router: {router_path}")
        router_text = router_path.read_text(encoding="utf-8")

        missing = [term for term in REQUIRED_ROUTER_TERMS if term not in router_text]

        self.assertEqual([], missing, f"root router is missing contract terms: {missing}")

    def test_root_router_rejects_legacy_level_routing(self):
        router_path = AUDIT_SKILL_ROOT / "SKILL.md"
        self.assertTrue(router_path.is_file(), f"missing root router: {router_path}")
        router_text = router_path.read_text(encoding="utf-8")

        self.assertIsNone(
            re.search(r"\bL[12]\b", router_text, flags=re.IGNORECASE),
            "root router must not retain the active L1/L2 routing model",
        )

    def test_union_dispatch_rules_define_stable_unique_algorithm(self):
        rules_path = AUDIT_SKILL_ROOT / "references/08-union-dispatch-rules.md"
        self.assertTrue(rules_path.is_file(), f"missing union dispatch rules: {rules_path}")
        rules_text = rules_path.read_text(encoding="utf-8")
        algorithm = re.search(
            r"\bskills_to_load\s*=\s*stable_unique\s*\((?P<arguments>[\s\S]*?)\)",
            rules_text,
        )

        self.assertIsNotNone(
            algorithm,
            "union dispatch rules must define an executable stable_unique load algorithm",
        )
        arguments = algorithm.group("arguments")
        required_inputs = (
            "scope_skills",
            "asset_skills",
            "business_skills",
            "method_skills",
            "overlay_skills",
            "public_skills",
        )
        missing = [
            name
            for name in required_inputs
            if re.search(rf"\b{re.escape(name)}\b", arguments) is None
        ]

        self.assertEqual([], missing, f"stable union algorithm is missing inputs: {missing}")

    def test_union_dispatch_rules_load_four_skills_for_realestate_liquidation_auction(self):
        rules_path = AUDIT_SKILL_ROOT / "references/08-union-dispatch-rules.md"
        self.assertTrue(rules_path.is_file(), f"missing union dispatch rules: {rules_path}")
        rules_text = rules_path.read_text(encoding="utf-8")
        scenario_start = rules_text.find("房地产清算后拍卖处置")

        self.assertGreaterEqual(
            scenario_start,
            0,
            "union dispatch rules must include the realestate liquidation auction scenario",
        )
        scenario_body = rules_text[scenario_start : scenario_start + 1200]
        expected_skills = (
            "crwu-audit-asset-realestate",
            "crwu-audit-biz-judicial-liquidation-compensation",
            "crwu-audit-biz-transaction-disposal",
        )
        missing = [skill for skill in expected_skills if skill not in scenario_body]

        self.assertEqual(
            [],
            missing,
            f"realestate liquidation auction scenario is missing nearby skills: {missing}",
        )

    @_requires_skill_tree
    def test_axis_named_leaf_skills_replace_legacy_combined_skills(self):
        asset_leaf = SKILLS_ROOT / "crwu-audit-asset-realestate/SKILL.md"
        obsolete_skill_dirs = (
            SKILLS_ROOT / "crwu-audit-realestate",
            SKILLS_ROOT / "crwu-audit-realestate-rent",
        )
        remaining = [str(path.relative_to(REPO_ROOT)) for path in obsolete_skill_dirs if path.exists()]

        self.assertTrue(asset_leaf.is_file(), f"missing axis-named asset leaf: {asset_leaf}")
        self.assertEqual([], remaining, f"legacy combined skill directories remain: {remaining}")

    @_requires_skill_tree
    def test_leaf_skill_directories_use_axis_prefixes_only(self):
        approved = ("crwu-audit-asset-", "crwu-audit-biz-")
        offenders = sorted(
            child.name
            for child in SKILLS_ROOT.iterdir()
            if child.is_dir()
            and child.name.startswith("crwu-audit-")
            and not child.name.startswith(approved)
            and child.name
            not in {
                "crwu-audit",
                "crwu-audit-optimize",
                "crwu-audit-skill-maintainer",
                "crwu-audit-datacheck",
                "crwu-audit-public-general-standards",
            }
        )

        self.assertEqual([], offenders, f"crwu-audit leaf directories must use axis prefixes: {offenders}")

    def test_unconditional_public_skills_are_not_conditioned_on_professional_axes(self):
        rules_path = AUDIT_SKILL_ROOT / "references/08-union-dispatch-rules.md"
        router_path = AUDIT_SKILL_ROOT / "SKILL.md"
        self.assertTrue(rules_path.is_file(), f"missing union dispatch rules: {rules_path}")
        self.assertTrue(router_path.is_file(), f"missing router skill entry: {router_path}")
        rules_text = rules_path.read_text(encoding="utf-8")
        router_text = router_path.read_text(encoding="utf-8")

        public_expression = re.search(
            r"public_skills\s*=\s*(?P<expression>[\s\S]*?)\n\n",
            rules_text,
        )

        self.assertIsNotNone(
            public_expression,
            "union dispatch rules must define the public_skills expression",
        )
        expression = public_expression.group("expression")
        for skill in UNCONDITIONAL_PUBLIC_SKILLS:
            self.assertIn(
                skill,
                expression,
                f"public_skills expression must always include {skill}",
            )
            self.assertNotIn(
                f"{skill}] when",
                expression,
                f"{skill} must not be conditioned on materials or professional labels",
            )
        self.assertNotIn(
            "else []",
            expression.split("crwu-audit-public-general-standards", 1)[0],
            "unconditional public skills must be declared before any conditional branch",
        )

        # The router step that builds public_skills must state the unconditional rule too,
        # otherwise the algorithm and the runnable step can drift apart.
        self.assertIn(
            "crwu-audit-public-general-standards",
            router_text,
            "router SKILL.md must name the unconditional public skill in its public-capability step",
        )

    @_requires_skill_tree
    def test_public_skill_directory_and_references_exist(self):
        for skill in UNCONDITIONAL_PUBLIC_SKILLS:
            skill_dir = SKILLS_ROOT / skill
            self.assertTrue(skill_dir.is_dir(), f"missing public-axis skill directory: {skill}")
            skill_entry = skill_dir / "SKILL.md"
            self.assertTrue(skill_entry.is_file(), f"missing public-axis SKILL.md: {skill}")
            entry_text = skill_entry.read_text(encoding="utf-8")
            self.assertIn(
                f"name: {skill}",
                entry_text,
                f"{skill} frontmatter name must match its directory name",
            )
            self.assertIn(
                "仅经 `crwu-audit` router 编排调用，禁止单独调用",
                entry_text,
                f"{skill} must declare the router-only invocation gate",
            )
            for reference in ("00-applicability.md", "01-kb-assembly.md", "02-review-focus.md"):
                reference_path = skill_dir / "references" / reference
                self.assertTrue(
                    reference_path.is_file(),
                    f"{skill} is missing required reference: {reference}",
                )

    @_requires_skill_tree
    def test_active_contracts_do_not_reference_deleted_combined_skill(self):
        active_paths = (
            SKILLS_ROOT / "README.md",
            AUDIT_SKILL_ROOT / "SKILL.md",
            SKILLS_ROOT / "crwu-audit-asset-realestate/SKILL.md",
            SKILLS_ROOT / "crwu-audit-skill-maintainer/SKILL.md",
        )
        forbidden_skill = "crwu-audit-realestate-rent"
        violations = [
            str(path.relative_to(REPO_ROOT))
            for path in active_paths
            if path.is_file() and forbidden_skill in path.read_text(encoding="utf-8")
        ]

        self.assertEqual(
            [],
            violations,
            f"active contracts still reference {forbidden_skill}: {violations}",
        )

    def test_skill_registry_names_every_dispatch_axis(self):
        registry_path = AUDIT_SKILL_ROOT / "references/07-skill-registry.md"
        self.assertTrue(registry_path.is_file(), f"missing skill registry: {registry_path}")
        registry_text = registry_path.read_text(encoding="utf-8")
        registry_rows = _registry_data_rows(registry_text)

        self.assertIsNotNone(
            registry_rows,
            f"registry must contain the Markdown header: {' | '.join(REGISTRY_HEADER)}",
        )
        missing = [row for row in EXPECTED_REGISTRY_ROWS if row not in registry_rows]
        registered_skills = {row[2] for row in registry_rows}

        self.assertEqual([], missing, f"skill registry is missing required relationship rows: {missing}")
        self.assertNotIn(
            LEGACY_REGISTRY_SKILL,
            registered_skills,
            f"legacy combined skill remains registered: {LEGACY_REGISTRY_SKILL}",
        )
        axes = {row[0] for row in registry_rows}
        absent = [axis for axis in DISPATCH_AXES if axis not in axes]
        self.assertEqual([], absent, f"registry does not name every dispatch axis: {absent}")
        # Registry<->reality hygiene (a retired-prefix row still marked `available`, or an
        # available row whose skill directory does not exist) is owned by the skill
        # maintainer mapping checker, which reports it with per-row evidence:
        #   python3 <skills 根>/crwu-audit-skill-maintainer/scripts/check_audit_skill_mappings.py
        #   -> LEGACY_BUSINESS_PREFIX / AVAILABLE_SKILL_DIRECTORY_MISSING / REGISTRY_LABEL_NOT_IN_CATALOG
        # It is deliberately not duplicated here, so the in-flight migration has one owner.


if __name__ == "__main__":
    unittest.main()
