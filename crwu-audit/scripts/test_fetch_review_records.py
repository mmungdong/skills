#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`fetch_review_records.py` 契约测试（阶段二按清单取回，只读守卫）。

自洽：只依赖本技能 `scripts/` 内脚本，构造临时 fixture，可随技能安装运行。
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "fetch_review_records.py"


def _run(*args) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), *args],
                          capture_output=True, text=True)


class FetchReviewRecordsContractTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.case = Path(self.tmp.name) / "case"
        self.src = Path(self.tmp.name) / "all"
        self.case.mkdir(parents=True)
        self.src.mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def _manifest(self, entries):
        p = self.case / "排除清单.json"
        p.write_text(json.dumps(entries, ensure_ascii=False), encoding="utf-8")
        return str(p)

    def test_fetches_allowlisted_files_and_writes_manifest(self):
        (self.src / "G15-4三级审核意见.docx").write_bytes(b"review" * 100)
        manifest = self._manifest([
            {"fileId": "f1", "name": "G15-4三级审核意见.docx", "sizeBytes": 600},
        ])
        r = _run("--case", str(self.case), "--manifest", manifest, "--source", str(self.src))
        self.assertEqual(0, r.returncode, r.stderr)
        out = self.case / "复核-人工" / "G15-4三级审核意见.docx"
        self.assertTrue(out.is_file())
        self.assertTrue((self.case / "复核-人工" / ".fetch-manifest.json").is_file())

    def test_size_mismatch_is_refused(self):
        (self.src / "A.docx").write_bytes(b"x" * 10)
        manifest = self._manifest([{"fileId": "f1", "name": "A.docx", "sizeBytes": 999}])
        r = _run("--case", str(self.case), "--manifest", manifest, "--source", str(self.src))
        self.assertEqual(0, r.returncode)  # 守卫不因单条失败而中止整体
        self.assertFalse((self.case / "复核-人工" / "A.docx").exists())
        res = json.loads((self.case / "复核-人工" / ".fetch-manifest.json").read_text(encoding="utf-8"))
        self.assertFalse(res["results"][0]["ok"])
        self.assertIn("字节数不符", res["results"][0]["reason"])

    def test_missing_source_file_is_recorded_not_fetched(self):
        manifest = self._manifest([{"fileId": "f1", "name": "不存在.docx", "sizeBytes": 1}])
        _run("--case", str(self.case), "--manifest", manifest, "--source", str(self.src))
        res = json.loads((self.case / "复核-人工" / ".fetch-manifest.json").read_text(encoding="utf-8"))
        self.assertFalse(res["results"][0]["ok"])
        self.assertIn("未找到", res["results"][0]["reason"])

    def test_output_must_not_be_inside_source_materials(self):
        (self.src / "A.docx").write_bytes(b"x" * 10)
        manifest = self._manifest([{"fileId": "f1", "name": "A.docx", "sizeBytes": 10}])
        r = _run("--case", str(self.case), "--manifest", manifest, "--source", str(self.src),
                 "--out", str(self.case / "材料-源" / "复核"))
        self.assertEqual(2, r.returncode, "落盘目录在材料-源内必须被拒绝")


if __name__ == "__main__":
    unittest.main(verbosity=2)
